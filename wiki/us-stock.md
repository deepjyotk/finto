Yes — that’s right.

**Producer → Redpanda/Kafka → Spark Structured Streaming → TimescaleDB**

In TimescaleDB:
- **Hypertables** for raw prices (`demo_us_stock_prices`) and alerts
- **Continuous aggregates** for OHLCV bars (plus `time_bucket()` when bucketing raw ticks on the fly)