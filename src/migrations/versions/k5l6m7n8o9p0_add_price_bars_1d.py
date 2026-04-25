"""add price_bars_1d table

Revision ID: k5l6m7n8o9p0
Revises: j4k5l6m7n8o9
Create Date: 2026-04-24

Daily OHLCV bars keyed by in_equities.id (no denormalized symbol).
One row per (equity, trade_date); only dates returned by the daily feed
(trading sessions) are stored.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "k5l6m7n8o9p0"
down_revision: Union[str, None] = "j4k5l6m7n8o9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "price_bars_1d",
        sa.Column(
            "in_equity_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("open", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column("high", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column("low", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column("close", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column("volume", sa.BigInteger(), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["in_equity_id"],
            ["in_equities.id"],
            name=op.f("fk_price_bars_1d_in_equity_id_in_equities"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("in_equity_id", "trade_date", name=op.f("pk_price_bars_1d")),
    )
    op.create_index(
        op.f("ix_price_bars_1d_trade_date"),
        "price_bars_1d",
        ["trade_date"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_price_bars_1d_trade_date"), table_name="price_bars_1d")
    op.drop_table("price_bars_1d")
