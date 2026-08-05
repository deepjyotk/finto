"""US stocks data-engineering demo models — stored in TimescaleDB.

Fully isolated from existing Arthik portfolio, AI, notification and alert
functionality, and from the Supabase database itself. The only shared value is
``f_users.user_id``, carried here as a plain UUID column.

These tables are created by ``finto/timescale/schema.sql``, not by Alembic:
``demo_us_stock_prices`` and ``demo_us_stock_alerts`` are hypertables and the
OHLCV bars are continuous aggregates, none of which SQLAlchemy can express. The
mappings below exist so the API can query them, and must be kept in step with
that file.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.timescale_base import TimescaleBase

# Aggregation windows offered by the demo, in seconds.
DEMO_US_STOCK_WINDOW_SECONDS: tuple[int, ...] = (60, 300, 900)


@dataclass(frozen=True)
class ChartWindowSpec:
    """How one chart window is served: which relation, at which granularity.

    The durations are ``timedelta`` rather than interval literals because they
    are sent as bound parameters, and the driver maps ``timedelta`` to
    PostgreSQL ``interval`` directly.
    """

    granularity: str
    """Human-readable bucket size echoed back to the client, e.g. "1 minute"."""

    lookback: timedelta
    """How far back from now() the query reaches."""

    relation: str | None
    """Continuous aggregate to read, or None to bucket raw ticks on the fly."""

    bucket_width: timedelta | None
    """time_bucket() width, only used when ``relation`` is None."""


# Fixed server-side mapping from the window a client asks for to the relation
# that answers it. The client sends a key, never a table or view name, so this
# dict is the only place a relation name is ever chosen.
DEMO_US_STOCK_CHART_WINDOWS: dict[str, ChartWindowSpec] = {
    # A one-minute view of per-second ticks is finer than the smallest
    # continuous aggregate, so it buckets the hypertable directly.
    "1min": ChartWindowSpec(
        granularity="1 second",
        lookback=timedelta(minutes=1),
        relation=None,
        bucket_width=timedelta(seconds=1),
    ),
    "1h": ChartWindowSpec(
        granularity="1 minute",
        lookback=timedelta(hours=1),
        relation="demo_us_stock_price_bars_1m",
        bucket_width=None,
    ),
    "1d": ChartWindowSpec(
        granularity="5 minutes",
        lookback=timedelta(days=1),
        relation="demo_us_stock_price_bars_5m",
        bucket_width=None,
    ),
    "1mo": ChartWindowSpec(
        granularity="1 day",
        lookback=timedelta(days=30),
        relation="demo_us_stock_price_bars_1d",
        bucket_width=None,
    ),
}

DEMO_US_STOCK_DEFAULT_SYMBOL = "TSLA"
DEMO_US_STOCK_DEFAULT_CHART_WINDOW = "1h"


class DemoUsStockPrice(TimescaleBase):
    """Raw normalized market-price event, written by the Spark streaming job.

    Hypertable partitioned on ``event_time``, which is why it leads the primary
    key: a hypertable requires the partitioning column in every unique
    constraint. The key also makes a replayed Kafka offset a no-op.
    """

    __tablename__ = "demo_us_stock_prices"
    __table_args__ = (
        Index(
            "idx_demo_us_stock_prices_symbol_time",
            "symbol",
            text("event_time DESC"),
        ),
    )

    event_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    event_id: Mapped[str] = mapped_column(Text, primary_key=True)
    symbol: Mapped[str] = mapped_column(Text, nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(precision=18, scale=6), nullable=False)
    volume: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    source: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'simulator'"))
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


# Alert rule directions: window open→close must move in this direction.
DEMO_US_STOCK_ALERT_DIRECTIONS: tuple[str, ...] = ("up", "down")


class DemoUsStockAlertRule(TimescaleBase):
    """A user-created price-movement rule, e.g. "AAPL moves up 2% within 5 minutes".

    ``user_id`` holds a Supabase ``f_users.user_id`` but carries no foreign key,
    because that table lives in a different database. The API only ever writes
    the authenticated user's id, and every read is scoped by it.
    """

    __tablename__ = "demo_us_stock_alert_rules"
    __table_args__ = (
        CheckConstraint(
            "window_seconds IN (60, 300, 900)",
            name="ck_demo_us_stock_alert_rules_window_seconds",
        ),
        CheckConstraint(
            "percentage_threshold > 0",
            name="ck_demo_us_stock_alert_rules_percentage_threshold",
        ),
        CheckConstraint(
            "direction IN ('up', 'down')",
            name="ck_demo_us_stock_alert_rules_direction",
        ),
        Index("idx_demo_us_stock_rules_user", "user_id", text("created_at DESC")),
        Index(
            "idx_demo_us_stock_rules_active_symbol",
            "symbol",
            "window_seconds",
            postgresql_where=text("is_active = TRUE"),
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    symbol: Mapped[str] = mapped_column(Text, nullable=False)
    window_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    percentage_threshold: Mapped[Decimal] = mapped_column(
        Numeric(precision=8, scale=4), nullable=False
    )
    direction: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'up'"))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class DemoUsStockAlert(TimescaleBase):
    """A triggered alert instance, written by the Spark streaming job.

    Hypertable partitioned on ``window_start``. Both keys include that column
    because a hypertable cannot have a unique constraint without it — hence the
    composite primary key rather than ``id`` alone. The unique constraint on
    ``(rule_id, window_start, window_end)`` is what keeps Spark retries from
    producing duplicate alerts for the same window.
    """

    __tablename__ = "demo_us_stock_alerts"
    __table_args__ = (
        UniqueConstraint(
            "rule_id",
            "window_start",
            "window_end",
            name="uq_demo_us_stock_alerts_rule_window",
        ),
        Index(
            "idx_demo_us_stock_alerts_user_time",
            "user_id",
            text("triggered_at DESC"),
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    rule_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("demo_us_stock_alert_rules.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    symbol: Mapped[str] = mapped_column(Text, nullable=False)
    window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    opening_price: Mapped[Decimal] = mapped_column(Numeric(precision=18, scale=6), nullable=False)
    closing_price: Mapped[Decimal] = mapped_column(Numeric(precision=18, scale=6), nullable=False)
    percentage_change: Mapped[Decimal] = mapped_column(
        Numeric(precision=10, scale=4), nullable=False
    )
    threshold_percentage: Mapped[Decimal] = mapped_column(
        Numeric(precision=8, scale=4), nullable=False
    )
    message: Mapped[str] = mapped_column(Text, nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    triggered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
