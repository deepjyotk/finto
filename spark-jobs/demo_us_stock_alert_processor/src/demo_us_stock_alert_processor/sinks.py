"""``foreachBatch`` handlers for the alert processor.

These run on the Spark driver, so no Python worker is spawned and psycopg can be
used directly. Micro-batches are small in this demo (a handful of ticks per
second), so collecting them to the driver is deliberate rather than a shortcut
around a distributed write.
"""

from __future__ import annotations

import logging
from typing import Callable

from pyspark.sql import DataFrame

from demo_us_stock_alert_processor.db import (
    build_alert_rows,
    build_price_rows,
    insert_alerts,
    insert_prices,
    load_active_rules,
)

logger = logging.getLogger(__name__)

BatchHandler = Callable[[DataFrame, int], None]


def make_price_sink(dsn: str) -> BatchHandler:
    """Build a handler that stores validated price events."""

    def write_prices(batch_df: DataFrame, batch_id: int) -> None:
        records = batch_df.collect()
        if not records:
            return
        written = insert_prices(dsn, build_price_rows(records))
        logger.info(
            "prices batch %s: %s events received, %s stored (duplicates ignored)",
            batch_id,
            len(records),
            written,
        )

    return write_prices


def make_alert_sink(dsn: str, window_seconds: int) -> BatchHandler:
    """Build a handler that evaluates completed windows against active rules."""

    def evaluate_windows(batch_df: DataFrame, batch_id: int) -> None:
        records = batch_df.collect()
        if not records:
            return

        rules_by_symbol = load_active_rules(dsn, window_seconds)
        if not rules_by_symbol:
            logger.info(
                "window %ss batch %s: %s completed windows, no active rules",
                window_seconds,
                batch_id,
                len(records),
            )
            return

        rows = build_alert_rows(records, rules_by_symbol, window_seconds)
        written = insert_alerts(dsn, rows)
        logger.info(
            "window %ss batch %s: %s completed windows, %s matched rules, %s alerts stored",
            window_seconds,
            batch_id,
            len(records),
            len(rows),
            written,
        )

    return evaluate_windows
