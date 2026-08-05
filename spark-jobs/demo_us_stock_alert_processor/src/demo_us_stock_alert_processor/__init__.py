"""Spark Structured Streaming alert processor for the US stocks demo.

Consumes normalized price events from the ``demo-market-prices`` topic, stores
them in ``demo_us_stock_prices``, aggregates them into 1/5/15-minute windows and
writes rows into ``demo_us_stock_alerts`` for every active user rule whose
threshold the window's absolute move reaches.
"""
