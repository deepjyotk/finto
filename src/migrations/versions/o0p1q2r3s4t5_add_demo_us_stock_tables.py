"""add demo us stock data-engineering tables

Revision ID: o0p1q2r3s4t5
Revises: n9o0p1q2r3s4
Create Date: 2026-08-01

Tables for the isolated US-stocks data-engineering demo. The only reference to
existing Arthik data is `f_users.user_id`.

`demo_us_stock_prices` stays a regular PostgreSQL table: the Supabase project
does not offer the TimescaleDB extension, so `create_hypertable` is skipped per
the PRD fallback.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "o0p1q2r3s4t5"
down_revision: Union[str, None] = "n9o0p1q2r3s4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
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
        sa.PrimaryKeyConstraint("event_time", "event_id", name=op.f("pk_demo_us_stock_prices")),
    )
    op.execute(
        "CREATE INDEX idx_demo_us_stock_prices_symbol_time "
        "ON demo_us_stock_prices (symbol, event_time DESC)"
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
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["f_users.user_id"],
            name=op.f("fk_demo_us_stock_alert_rules_user_id_f_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_demo_us_stock_alert_rules")),
    )
    op.execute(
        "CREATE INDEX idx_demo_us_stock_rules_active_symbol "
        "ON demo_us_stock_alert_rules (symbol, window_seconds) "
        "WHERE is_active = TRUE"
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
        sa.ForeignKeyConstraint(
            ["rule_id"],
            ["demo_us_stock_alert_rules.id"],
            name=op.f("fk_demo_us_stock_alerts_rule_id_demo_us_stock_alert_rules"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["f_users.user_id"],
            name=op.f("fk_demo_us_stock_alerts_user_id_f_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_demo_us_stock_alerts")),
        sa.UniqueConstraint(
            "rule_id",
            "window_start",
            "window_end",
            name="uq_demo_us_stock_alerts_rule_window",
        ),
    )
    op.execute(
        "CREATE INDEX idx_demo_us_stock_alerts_user_time "
        "ON demo_us_stock_alerts (user_id, triggered_at DESC)"
    )


def downgrade() -> None:
    op.drop_table("demo_us_stock_alerts")
    op.drop_table("demo_us_stock_alert_rules")
    op.drop_table("demo_us_stock_prices")
