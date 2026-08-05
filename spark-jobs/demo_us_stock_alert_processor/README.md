# demo_us_stock_alert_processor

Spark Structured Streaming job for the US stocks data-engineering demo. It
consumes normalized price events from the Redpanda topic `demo-market-prices`,
stores them in **TimescaleDB**, aggregates them into fixed windows, and writes an
alert whenever a window's absolute percentage move reaches a user's configured
threshold.

The OHLCV bars the chart API serves are *not* produced here — they are
TimescaleDB continuous aggregates over `demo_us_stock_prices`, refreshed by the
database itself. See `finto/timescale/schema.sql`.

## Why this is a separate uv project

The Arthik backend pins `requires-python = ">=3.13"`, but PySpark's Python
worker has an unfixed socket-cleanup bug on Python 3.12/3.13 in every stable
release. This project pins **Python 3.12** so the Spark environment is fully
isolated from the backend's, and 3.12 also matches the Databricks runtime the
job is meant to be deployed to.

The job never spawns a Python worker anyway — there are no UDFs and no RDD
operations, and all writes happen in `foreachBatch`, which runs on the driver.

## Pipeline

```text
demo-market-prices (Kafka/Redpanda)
        |
        +-- prices query      -> demo_us_stock_prices (hypertable)
        |                            |
        |                            +-- demo_us_stock_price_bars_1m  \
        |                            +-- demo_us_stock_price_bars_5m   > continuous
        |                            +-- demo_us_stock_price_bars_1d  /   aggregates
        +-- 60s window query  -\
        +-- 300s window query  -> demo_us_stock_alerts (per matching rule)
        +-- 900s window query -/
```

For each completed window, per symbol:

```text
opening_price     = min_by(price, event_time)   # first tick in the window
closing_price     = max_by(price, event_time)   # last tick in the window
percentage_change = ((closing_price - opening_price) / opening_price) * 100
```

An alert is written when `ABS(percentage_change) >= rule.percentage_threshold`
for an active rule matching the symbol and window size.

`min_by`/`max_by` are used rather than `first`/`last` because `first`/`last`
have no defined ordering inside a streaming aggregation.

## Idempotency

Both sinks use `ON CONFLICT DO NOTHING`:

- `demo_us_stock_prices` is keyed on `(event_time, event_id)`
- `demo_us_stock_alerts` is unique on `(rule_id, window_start, window_end)`

So a Spark restart replaying offsets cannot produce duplicate prices or a second
alert for the same rule and window.

## Prerequisites

- **Java 17 or 21** on `PATH` (Spark 4.0 does not support Java 22+). The
  `Makefile` auto-selects Java 21 via `/usr/libexec/java_home -v 21` on macOS.
- Redpanda and TimescaleDB running: `make demo-us-stocks-infra-up` from `finto/`.
- `TIMESCALE_DATABASE_URL` in `finto/.env` (loaded automatically).
- Internet access on the first run, to fetch the
  `spark-sql-kafka-0-10` connector from Maven Central.

## Running locally

```bash
# from finto/
make demo-us-stocks-infra-up
make demo-us-stocks-topic
make demo-us-stocks-producer   # in one terminal
make demo-us-stocks-spark      # in another
```

Or directly:

```bash
cd spark-jobs/demo_us_stock_alert_processor
make run
```

## Configuration

All read from the environment (or `finto/.env`):

| Variable | Default | Purpose |
| --- | --- | --- |
| `TIMESCALE_DATABASE_URL` | required | TimescaleDB connection string |
| `DEMO_US_STOCK_KAFKA_BOOTSTRAP_SERVERS` | `localhost:19092` | Redpanda brokers |
| `DEMO_US_STOCK_KAFKA_TOPIC` | `demo-market-prices` | Source topic |
| `DEMO_US_STOCK_CHECKPOINT_ROOT` | `./.checkpoints` | Streaming checkpoint root |
| `DEMO_US_STOCK_WATERMARK` | `30 seconds` | Late-data tolerance; also the delay before a window is emitted |
| `DEMO_US_STOCK_STARTING_OFFSETS` | `latest` | `latest` or `earliest` |
| `DEMO_US_STOCK_MAX_OFFSETS_PER_TRIGGER` | `5000` | Kafka records per micro-batch |
| `DEMO_US_STOCK_SPARK_MASTER` | `local[*]` | Unset this on Databricks |

Because a window is only emitted once the watermark passes its end, expect the
first alerts roughly `window_seconds + watermark` after the producer starts.

## Deploying to Databricks

`databricks_notebook.py` is the deployable entrypoint. Import it as a notebook
(or add it to a job as a Python file), attach it to a cluster running DBR 16.x,
and set the same environment variables as cluster env vars or notebook widgets.
It calls the same `job.run()` used locally; only the Spark session differs
(Databricks provides one, so `DEMO_US_STOCK_SPARK_MASTER` must be left unset).
