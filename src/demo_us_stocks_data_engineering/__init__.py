"""US stocks data-engineering demo — market-data ingestion.

Standalone producer process that reads US stock trades (Alpaca WebSocket, or a
simulator when no credentials are configured), normalizes them, and publishes
them to the Redpanda topic ``demo-market-prices`` keyed by symbol.

Downstream, a Spark Structured Streaming job
(``spark-jobs/demo_us_stock_alert_processor``) consumes the topic, stores prices
and evaluates user alert rules.

Run with::

    make demo-us-stocks-producer
"""
