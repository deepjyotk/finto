"""TimescaleDB writes and reads for the alert processor.

All statements run on the Spark driver from inside ``foreachBatch``, using
psycopg directly. That avoids the Postgres JDBC jar entirely and, more
importantly, lets both sinks use ``ON CONFLICT DO NOTHING`` — which is what makes
a replayed Kafka offset harmless.

Both target tables are hypertables, so their conflict targets lead with the
partitioning column; see ``finto/timescale/schema.sql``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Iterable, Sequence
from uuid import UUID

import psycopg

logger = logging.getLogger(__name__)

INSERT_PRICE_SQL = """
INSERT INTO demo_us_stock_prices
    (event_time, event_id, symbol, price, volume, source)
VALUES (%s, %s, %s, %s, %s, %s)
ON CONFLICT (event_time, event_id) DO NOTHING
"""

SELECT_ACTIVE_RULES_SQL = """
SELECT id, user_id, symbol, percentage_threshold, direction
FROM demo_us_stock_alert_rules
WHERE is_active = TRUE
  AND window_seconds = %s
"""

INSERT_ALERT_SQL = """
INSERT INTO demo_us_stock_alerts
    (rule_id, user_id, symbol, window_start, window_end,
     opening_price, closing_price, percentage_change, threshold_percentage, message)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
ON CONFLICT (rule_id, window_start, window_end) DO NOTHING
"""


@dataclass(frozen=True)
class AlertRule:
    """An active rule loaded from TimescaleDB for one window size."""

    rule_id: UUID
    user_id: UUID
    symbol: str
    percentage_threshold: Decimal
    direction: str  # "up" or "down"


def rule_matches(percentage_change: Decimal, rule: AlertRule) -> bool:
    """Return True when the window move satisfies the rule's direction and threshold."""
    if rule.direction == "up":
        return percentage_change >= rule.percentage_threshold
    if rule.direction == "down":
        return percentage_change <= -rule.percentage_threshold
    return False


def insert_prices(dsn: str, rows: Sequence[tuple[Any, ...]]) -> int:
    """Insert raw price events, ignoring ones already stored.

    Returns the number of rows the statement reported as written.
    """
    if not rows:
        return 0
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.executemany(INSERT_PRICE_SQL, rows)
            return cur.rowcount if cur.rowcount and cur.rowcount > 0 else 0


def load_active_rules(dsn: str, window_seconds: int) -> dict[str, list[AlertRule]]:
    """Return active rules for ``window_seconds``, grouped by symbol."""
    grouped: dict[str, list[AlertRule]] = {}
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(SELECT_ACTIVE_RULES_SQL, (window_seconds,))
            for rule_id, user_id, symbol, threshold, direction in cur.fetchall():
                grouped.setdefault(symbol, []).append(
                    AlertRule(
                        rule_id=rule_id,
                        user_id=user_id,
                        symbol=symbol,
                        percentage_threshold=Decimal(str(threshold)),
                        direction=str(direction),
                    )
                )
    return grouped


def insert_alerts(dsn: str, rows: Sequence[tuple[Any, ...]]) -> int:
    """Insert triggered alerts, skipping any that already exist for the window."""
    if not rows:
        return 0
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.executemany(INSERT_ALERT_SQL, rows)
            return cur.rowcount if cur.rowcount and cur.rowcount > 0 else 0


def as_utc(value: datetime) -> datetime:
    """Return ``value`` as a timezone-aware UTC datetime.

    Collecting a Spark ``TimestampType`` yields a *naive* datetime in the
    driver's local timezone, regardless of ``spark.sql.session.timeZone``.
    Handing that to psycopg stores it verbatim into a TIMESTAMPTZ column, which
    PostgreSQL reads in the session timezone — shifting every row by the
    driver's UTC offset and making recent ticks look hours old to the chart's
    ``now() - interval`` filters. ``astimezone`` interprets a naive value as
    local time, which is exactly what it is, and is a no-op for aware values.
    """
    return value.astimezone(timezone.utc)


def build_price_rows(records: Iterable[Any]) -> list[tuple[Any, ...]]:
    """Convert Spark ``Row`` objects into positional tuples for ``INSERT_PRICE_SQL``."""
    return [
        (
            as_utc(record["event_time"]),
            record["event_id"],
            record["symbol"],
            record["price"],
            record["volume"],
            record["source"],
        )
        for record in records
    ]


def window_label(window_seconds: int) -> str:
    """Human phrasing for a window size, e.g. 300 -> "5 minutes"."""
    minutes = window_seconds // 60
    return "1 minute" if minutes == 1 else f"{minutes} minutes"


def format_threshold(threshold: Decimal) -> str:
    """Render a NUMERIC(8,4) threshold without trailing zeros: 3.0000 -> "3"."""
    normalized = threshold.normalize()
    # normalize() turns e.g. 3.0000 into 3E+0; quantizing back avoids exponents.
    if normalized == normalized.to_integral_value():
        return str(normalized.to_integral_value())
    return format(normalized, "f")


def build_alert_message(
    symbol: str,
    percentage_change: Decimal,
    window_seconds: int,
    threshold: Decimal,
    direction: str,
) -> str:
    """Compose the user-facing alert text for a directional rule match."""
    move_word = "up" if direction == "up" else "down"
    return (
        f"{symbol} moved {move_word} {abs(percentage_change):.2f}% during the last "
        f"{window_label(window_seconds)}.\n"
        f"Your configured {direction} threshold was {format_threshold(threshold)}%."
    )


def build_alert_rows(
    aggregated: Iterable[Any],
    rules_by_symbol: dict[str, list[AlertRule]],
    window_seconds: int,
) -> list[tuple[Any, ...]]:
    """Match completed windows against active rules and build alert insert tuples.

    ``aggregated`` rows carry ``symbol``, ``window_start``, ``window_end``,
    ``opening_price`` and ``closing_price``.
    """
    rows: list[tuple[Any, ...]] = []
    for record in aggregated:
        symbol = record["symbol"]
        rules = rules_by_symbol.get(symbol)
        if not rules:
            continue

        opening = Decimal(str(record["opening_price"]))
        closing = Decimal(str(record["closing_price"]))
        if opening <= 0:
            continue

        percentage_change = ((closing - opening) / opening) * Decimal(100)
        window_start: datetime = as_utc(record["window_start"])
        window_end: datetime = as_utc(record["window_end"])

        for rule in rules:
            if not rule_matches(percentage_change, rule):
                continue
            rows.append(
                (
                    rule.rule_id,
                    rule.user_id,
                    symbol,
                    window_start,
                    window_end,
                    opening,
                    closing,
                    percentage_change.quantize(Decimal("0.0001")),
                    rule.percentage_threshold,
                    build_alert_message(
                        symbol=symbol,
                        percentage_change=percentage_change,
                        window_seconds=window_seconds,
                        threshold=rule.percentage_threshold,
                        direction=rule.direction,
                    ),
                )
            )
    return rows
