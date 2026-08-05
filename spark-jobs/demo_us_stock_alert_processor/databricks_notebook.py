# Databricks notebook source
# MAGIC %md
# MAGIC # demo_us_stock_alert_processor
# MAGIC
# MAGIC Databricks entrypoint for the US stocks data-engineering demo. It runs the
# MAGIC exact same `job.run()` used locally — only the Spark session differs, since
# MAGIC Databricks provides one.
# MAGIC
# MAGIC ## Setup
# MAGIC
# MAGIC 1. Attach to a cluster running DBR 16.x (Spark 4.0, Python 3.12).
# MAGIC 2. `%pip install psycopg[binary]` — the Kafka connector ships with DBR, so
# MAGIC    `spark.jars.packages` is not needed here.
# MAGIC 3. Fill in the widgets below, or set the same names as cluster env vars.
# MAGIC
# MAGIC `DEMO_US_STOCK_SPARK_MASTER` is forced empty so the notebook reuses the
# MAGIC cluster's session instead of trying to start a local one.
# MAGIC
# MAGIC `TIMESCALE_DATABASE_URL` must point at a TimescaleDB the cluster can
# MAGIC reach; a local docker container is not reachable from Databricks.

# COMMAND ----------

# MAGIC %pip install "psycopg[binary]>=3.2.0"

# COMMAND ----------

import os
import sys

# Point at the job package checked out alongside this notebook (e.g. via Repos).
_PACKAGE_ROOT = os.path.join(os.path.dirname(os.path.abspath("__file__")), "src")
if _PACKAGE_ROOT not in sys.path:
    sys.path.insert(0, _PACKAGE_ROOT)

# COMMAND ----------

dbutils.widgets.text("timescale_database_url", "", "TIMESCALE_DATABASE_URL")
dbutils.widgets.text("kafka_bootstrap_servers", "", "Redpanda bootstrap servers")
dbutils.widgets.text("kafka_topic", "demo-market-prices", "Kafka topic")
dbutils.widgets.text(
    "checkpoint_root",
    "dbfs:/FileStore/demo_us_stock_alert_processor/checkpoints",
    "Checkpoint root",
)
dbutils.widgets.text("watermark", "30 seconds", "Watermark")
dbutils.widgets.dropdown("starting_offsets", "latest", ["latest", "earliest"], "Starting offsets")

# COMMAND ----------

for widget_name, env_name in (
    ("timescale_database_url", "TIMESCALE_DATABASE_URL"),
    ("kafka_bootstrap_servers", "DEMO_US_STOCK_KAFKA_BOOTSTRAP_SERVERS"),
    ("kafka_topic", "DEMO_US_STOCK_KAFKA_TOPIC"),
    ("checkpoint_root", "DEMO_US_STOCK_CHECKPOINT_ROOT"),
    ("watermark", "DEMO_US_STOCK_WATERMARK"),
    ("starting_offsets", "DEMO_US_STOCK_STARTING_OFFSETS"),
):
    value = dbutils.widgets.get(widget_name).strip()
    if value:
        os.environ[env_name] = value

# Reuse the cluster's SparkSession rather than creating a local[*] one.
os.environ["DEMO_US_STOCK_SPARK_MASTER"] = ""

# COMMAND ----------

from demo_us_stock_alert_processor import job  # noqa: E402

job.main()
