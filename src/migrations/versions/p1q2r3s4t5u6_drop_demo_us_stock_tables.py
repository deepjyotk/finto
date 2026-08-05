"""drop demo us stock tables from Supabase

Revision ID: p1q2r3s4t5u6
Revises: o0p1q2r3s4t5
Create Date: 2026-08-02

The US-stocks demo now stores everything in TimescaleDB, where the price table
is a hypertable and the OHLCV bars are continuous aggregates — neither of which
Supabase can host, since the project does not offer the TimescaleDB extension.
The schema lives in `finto/timescale/schema.sql`.

This migration removes what `o0p1q2r3s4t5` created. Apply it only after the
TimescaleDB flow has been verified end to end, because it is destructive: the
tick history and any alert rules still in Supabase are dropped, not migrated.
`f_users` is untouched.

    cd finto && uv run alembic upgrade head

`downgrade()` recreates the tables so the revision can be reversed, but it
cannot bring back the rows.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "p1q2r3s4t5u6"
down_revision: Union[str, None] = "o0p1q2r3s4t5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Alerts first: they carry a foreign key to the rules table.
    op.drop_table("demo_us_stock_alerts")
    op.drop_table("demo_us_stock_alert_rules")
    op.drop_table("demo_us_stock_prices")


def downgrade() -> None:
    op.create_table(
        "demo_us_stock_prices",
        sa.Column("event_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("event_id", sa.Text(), nullable=False),
        sa.Column("symbol", sa.Text(), nullable=False),
        sa.Column("price", sa.Numeric(precision=18, scale=6), nullable=False),
        sa.Column("volume", sa.BigInteger(), nullable=True),
        sa.Column("source", sa.Text(), server_default=sa.text("'alpaca'"), nullable=False),
        sa.Column(
            "ingested_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("event_time", "event_id"),
    )
    op.create_index(
        "idx_demo_us_stock_prices_symbol_time",
        "demo_us_stock_prices",
        ["symbol", sa.text("event_time DESC")],
    )

    op.create_table(
        "demo_us_stock_alert_rules",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("symbol", sa.Text(), nullable=False),
        sa.Column("window_seconds", sa.Integer(), nullable=False),
        sa.Column("percentage_threshold", sa.Numeric(precision=8, scale=4), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "window_seconds IN (60, 300, 900)",
            name="ck_demo_us_stock_alert_rules_window_seconds",
        ),
        sa.CheckConstraint(
            "percentage_threshold > 0",
            name="ck_demo_us_stock_alert_rules_percentage_threshold",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["f_users.user_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_demo_us_stock_rules_active_symbol",
        "demo_us_stock_alert_rules",
        ["symbol", "window_seconds"],
        postgresql_where=sa.text("is_active = TRUE"),
    )

    op.create_table(
        "demo_us_stock_alerts",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("rule_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("symbol", sa.Text(), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("opening_price", sa.Numeric(precision=18, scale=6), nullable=False),
        sa.Column("closing_price", sa.Numeric(precision=18, scale=6), nullable=False),
        sa.Column("percentage_change", sa.Numeric(precision=10, scale=4), nullable=False),
        sa.Column("threshold_percentage", sa.Numeric(precision=8, scale=4), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("is_read", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column(
            "triggered_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["rule_id"], ["demo_us_stock_alert_rules.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["f_users.user_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "rule_id",
            "window_start",
            "window_end",
            name="uq_demo_us_stock_alerts_rule_window",
        ),
    )
    op.create_index(
        "idx_demo_us_stock_alerts_user_time",
        "demo_us_stock_alerts",
        ["user_id", sa.text("triggered_at DESC")],
    )
