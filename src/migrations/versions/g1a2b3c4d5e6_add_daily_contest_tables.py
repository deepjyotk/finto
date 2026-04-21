"""add daily contest tables

Revision ID: g1a2b3c4d5e6
Revises: b4c5d6e7f8a9
Create Date: 2026-04-19

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "g1a2b3c4d5e6"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "f_daily_contests",
        sa.Column(
            "contest_id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("contest_date", sa.Date(), nullable=False),
        sa.Column("nifty_open", sa.Float(), nullable=True),
        sa.Column("nifty_close", sa.Float(), nullable=True),
        sa.Column("nifty_return_pct", sa.Float(), nullable=True),
        sa.Column(
            "is_settled",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("contest_id"),
    )
    op.create_index("ix_f_daily_contests_contest_date", "f_daily_contests", ["contest_date"], unique=True)

    op.create_table(
        "f_contest_picks",
        sa.Column(
            "pick_id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("contest_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("stock_1", sa.Text(), nullable=False),
        sa.Column("stock_2", sa.Text(), nullable=False),
        sa.Column("stock_3", sa.Text(), nullable=False),
        sa.Column("stock_4", sa.Text(), nullable=False),
        sa.Column("stock_5", sa.Text(), nullable=False),
        sa.Column("stock_1_entry_price", sa.Float(), nullable=True),
        sa.Column("stock_2_entry_price", sa.Float(), nullable=True),
        sa.Column("stock_3_entry_price", sa.Float(), nullable=True),
        sa.Column("stock_4_entry_price", sa.Float(), nullable=True),
        sa.Column("stock_5_entry_price", sa.Float(), nullable=True),
        sa.Column("portfolio_return_pct", sa.Float(), nullable=True),
        sa.Column("excess_return_pct", sa.Float(), nullable=True),
        sa.Column("rank", sa.Integer(), nullable=True),
        sa.Column("stock_1_return_pct", sa.Float(), nullable=True),
        sa.Column("stock_2_return_pct", sa.Float(), nullable=True),
        sa.Column("stock_3_return_pct", sa.Float(), nullable=True),
        sa.Column("stock_4_return_pct", sa.Float(), nullable=True),
        sa.Column("stock_5_return_pct", sa.Float(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("pick_id"),
        sa.ForeignKeyConstraint(["contest_id"], ["f_daily_contests.contest_id"]),
        sa.ForeignKeyConstraint(["user_id"], ["f_users.user_id"]),
        sa.UniqueConstraint("contest_id", "user_id", name="uq_contest_user"),
    )
    op.create_index("ix_f_contest_picks_contest_id", "f_contest_picks", ["contest_id"])
    op.create_index("ix_f_contest_picks_user_id", "f_contest_picks", ["user_id"])


def downgrade() -> None:
    op.drop_table("f_contest_picks")
    op.drop_table("f_daily_contests")
