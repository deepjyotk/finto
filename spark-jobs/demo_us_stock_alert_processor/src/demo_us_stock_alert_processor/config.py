"""Configuration for the demo alert processor, read from the environment.

Values are shared with the Arthik backend through ``finto/.env`` so the job, the
producer and the API agree on the Redpanda topic and the TimescaleDB instance
without duplicating configuration.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

# Aggregation windows the demo supports, matching the CHECK constraint on
# demo_us_stock_alert_rules.window_seconds.
WINDOW_SECONDS: tuple[int, ...] = (60, 300, 900)

# spark-sql-kafka is not bundled with the pyspark wheel; Spark 4.0.x is Scala 2.13.
KAFKA_CONNECTOR_PACKAGE = "org.apache.spark:spark-sql-kafka-0-10_2.13:4.0.1"


def load_env() -> None:
    """Load ``finto/.env`` if present, without clobbering real environment vars.

    The job lives at ``finto/spark-jobs/demo_us_stock_alert_processor``, so the
    backend's dotenv file is three directories up.
    """
    env_file = Path(__file__).resolve().parents[4] / ".env"
    if env_file.is_file():
        load_dotenv(env_file, override=False)


def normalize_database_url(url: str) -> str:
    """Strip a SQLAlchemy driver suffix so psycopg accepts the DSN.

    The backend stores ``postgresql://...`` but converts it to
    ``postgresql+asyncpg://...`` at runtime; tolerate either form here.

    ``host.docker.internal`` is not rewritten: whether the job runs on the host
    or in a container is the operator's choice, expressed in the URL.
    """
    for prefix, replacement in (
        ("postgresql+asyncpg://", "postgresql://"),
        ("postgresql+psycopg://", "postgresql://"),
        ("postgres://", "postgresql://"),
    ):
        if url.startswith(prefix):
            return replacement + url[len(prefix) :]
    return url


@dataclass(frozen=True)
class JobConfig:
    """Resolved settings for one run of the streaming job."""

    timescale_url: str
    kafka_bootstrap_servers: str
    kafka_topic: str
    checkpoint_root: str
    watermark: str
    starting_offsets: str
    max_offsets_per_trigger: str
    spark_master: str | None
    window_seconds: tuple[int, ...] = field(default=WINDOW_SECONDS)

    def checkpoint_path(self, query_name: str) -> str:
        """Checkpoint location for a named query, one directory per query."""
        return str(Path(self.checkpoint_root).expanduser() / query_name)


def load_config() -> JobConfig:
    """Build a :class:`JobConfig` from the environment, validating what's required."""
    load_env()

    timescale_url = os.getenv("TIMESCALE_DATABASE_URL", "").strip()
    if not timescale_url:
        raise ValueError(
            "TIMESCALE_DATABASE_URL is not set. Add it to finto/.env or export it before "
            "running the job. Start the database with `make demo-us-stocks-infra-up`."
        )

    # On Databricks the session already exists, so master must stay unset.
    spark_master = os.getenv("DEMO_US_STOCK_SPARK_MASTER", "local[*]").strip() or None

    return JobConfig(
        timescale_url=normalize_database_url(timescale_url),
        kafka_bootstrap_servers=os.getenv(
            "DEMO_US_STOCK_KAFKA_BOOTSTRAP_SERVERS", "localhost:19092"
        ),
        kafka_topic=os.getenv("DEMO_US_STOCK_KAFKA_TOPIC", "demo-market-prices"),
        checkpoint_root=os.getenv("DEMO_US_STOCK_CHECKPOINT_ROOT", ".checkpoints"),
        watermark=os.getenv("DEMO_US_STOCK_WATERMARK", "30 seconds"),
        starting_offsets=os.getenv("DEMO_US_STOCK_STARTING_OFFSETS", "latest"),
        max_offsets_per_trigger=os.getenv("DEMO_US_STOCK_MAX_OFFSETS_PER_TRIGGER", "5000"),
        spark_master=spark_master,
    )
