"""demo_us_stock_alert_processor — Spark Structured Streaming entrypoint.

Runs four streaming queries over the same Kafka source:

1. store validated, deduplicated price events in ``demo_us_stock_prices``
2-4. aggregate 60s / 300s / 900s windows per symbol and evaluate user rules

Each query keeps its own checkpoint directory, so they progress independently.

All writes land in TimescaleDB. ``demo_us_stock_prices`` is a hypertable, and
the continuous aggregates that back the chart API are refreshed by TimescaleDB
itself — this job never writes the OHLCV bars.
"""

from __future__ import annotations

import logging
import sys

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import (
    DoubleType,
    LongType,
    StringType,
    StructField,
    StructType,
    TimestampType,
)

from demo_us_stock_alert_processor.config import (
    KAFKA_CONNECTOR_PACKAGE,
    JobConfig,
    load_config,
)
from demo_us_stock_alert_processor.sinks import make_alert_sink, make_price_sink

logger = logging.getLogger(__name__)

APP_NAME = "demo_us_stock_alert_processor"

# Wire format published by src/demo_us_stocks_data_engineering/schemas.py.
EVENT_SCHEMA = StructType(
    [
        StructField("event_id", StringType(), nullable=False),
        StructField("symbol", StringType(), nullable=False),
        StructField("price", DoubleType(), nullable=False),
        StructField("volume", LongType(), nullable=True),
        StructField("event_time", TimestampType(), nullable=False),
        StructField("source", StringType(), nullable=True),
    ]
)


def build_spark_session(config: JobConfig) -> SparkSession:
    """Create (or reuse) the Spark session.

    ``spark.jars.packages`` has to be set on the builder because PySpark passes
    it to the launcher before the JVM starts. On Databricks the session already
    exists and ``DEMO_US_STOCK_SPARK_MASTER`` is left unset, so neither the
    master nor the package is applied.
    """
    builder = SparkSession.builder.appName(APP_NAME)
    if config.spark_master:
        builder = builder.master(config.spark_master).config(
            "spark.jars.packages", KAFKA_CONNECTOR_PACKAGE
        )
    builder = builder.config("spark.sql.session.timeZone", "UTC").config(
        "spark.sql.shuffle.partitions", "4"
    )
    return builder.getOrCreate()


def read_price_events(spark: SparkSession, config: JobConfig) -> DataFrame:
    """Read the topic and return validated, typed price events.

    Invalid records are dropped here so neither the price sink nor the window
    aggregations have to defend against them.
    """
    raw = (
        spark.readStream.format("kafka")
        .option("kafka.bootstrap.servers", config.kafka_bootstrap_servers)
        .option("subscribe", config.kafka_topic)
        .option("startingOffsets", config.starting_offsets)
        .option("maxOffsetsPerTrigger", config.max_offsets_per_trigger)
        .option("failOnDataLoss", "false")
        .load()
    )

    return (
        raw.select(F.from_json(F.col("value").cast("string"), EVENT_SCHEMA).alias("event"))
        .select("event.*")
        .where(
            F.col("event_id").isNotNull()
            & F.col("symbol").isNotNull()
            & F.col("event_time").isNotNull()
            & F.col("price").isNotNull()
            & (F.col("price") > 0)
        )
        .withColumn("source", F.coalesce(F.col("source"), F.lit("alpaca")))
    )


def start_price_query(events: DataFrame, config: JobConfig):
    """Persist deduplicated price events."""
    deduplicated = events.withWatermark(
        "event_time", config.watermark
    ).dropDuplicatesWithinWatermark(["event_id"])

    return (
        deduplicated.writeStream.queryName("demo_us_stock_prices")
        .outputMode("append")
        .option("checkpointLocation", config.checkpoint_path("prices"))
        .foreachBatch(make_price_sink(config.timescale_url))
        .start()
    )


def start_window_query(events: DataFrame, config: JobConfig, window_seconds: int):
    """Aggregate one window size per symbol and evaluate matching rules.

    ``min_by``/``max_by`` give the first and last price by event time;
    ``first``/``last`` have no defined ordering in a streaming aggregation.
    Append mode means only windows the watermark has passed are emitted, so every
    row handed to the sink represents a completed window.
    """
    aggregated = (
        events.withWatermark("event_time", config.watermark)
        .groupBy(
            F.window(F.col("event_time"), f"{window_seconds} seconds").alias("window"),
            F.col("symbol"),
        )
        .agg(
            F.expr("min_by(price, event_time)").alias("opening_price"),
            F.expr("max_by(price, event_time)").alias("closing_price"),
        )
        .select(
            F.col("symbol"),
            F.col("window.start").alias("window_start"),
            F.col("window.end").alias("window_end"),
            F.col("opening_price"),
            F.col("closing_price"),
        )
    )

    return (
        aggregated.writeStream.queryName(f"demo_us_stock_alerts_{window_seconds}s")
        .outputMode("append")
        .option("checkpointLocation", config.checkpoint_path(f"window_{window_seconds}s"))
        .foreachBatch(make_alert_sink(config.timescale_url, window_seconds))
        .start()
    )


def run() -> None:
    """Start every query and block until one of them terminates."""
    config = load_config()
    spark = build_spark_session(config)
    spark.sparkContext.setLogLevel("WARN")

    logger.info(
        "starting %s — topic=%s brokers=%s windows=%s watermark=%s offsets=%s",
        APP_NAME,
        config.kafka_topic,
        config.kafka_bootstrap_servers,
        config.window_seconds,
        config.watermark,
        config.starting_offsets,
    )

    events = read_price_events(spark, config)

    start_price_query(events, config)
    for window_seconds in config.window_seconds:
        start_window_query(events, config, window_seconds)

    spark.streams.awaitAnyTermination()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        stream=sys.stdout,
    )
    try:
        run()
    except KeyboardInterrupt:
        logger.info("%s interrupted", APP_NAME)


if __name__ == "__main__":
    main()
