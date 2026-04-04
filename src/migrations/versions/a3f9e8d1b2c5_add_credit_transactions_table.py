"""add_credit_transactions_table

Revision ID: a3f9e8d1b2c5
Revises: 817b2afc547c
Create Date: 2025-12-28 18:15:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "a3f9e8d1b2c5"
down_revision: Union[str, None] = "817b2afc547c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create credit_transactions table for tracking all credit operations."""
    op.create_table(
        "credit_transactions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("transaction_type", sa.String(length=50), nullable=False),
        sa.Column("balance_before", sa.Integer(), nullable=False),
        sa.Column("balance_after", sa.Integer(), nullable=False),
        sa.Column("model_name", sa.String(length=100), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("usd_cost", sa.Numeric(precision=10, scale=6), nullable=True),
        sa.Column("request_id", sa.String(length=255), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["f_users.user_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create indexes for better query performance
    op.create_index("ix_credit_transactions_user_id", "credit_transactions", ["user_id"])
    op.create_index("ix_credit_transactions_request_id", "credit_transactions", ["request_id"])
    op.create_index("ix_credit_transactions_created_at", "credit_transactions", ["created_at"])
    op.create_index(
        "ix_credit_transactions_user_created",
        "credit_transactions",
        ["user_id", "created_at"],
    )


def downgrade() -> None:
    """Drop credit_transactions table and its indexes."""
    op.drop_index("ix_credit_transactions_user_created", table_name="credit_transactions")
    op.drop_index("ix_credit_transactions_created_at", table_name="credit_transactions")
    op.drop_index("ix_credit_transactions_request_id", table_name="credit_transactions")
    op.drop_index("ix_credit_transactions_user_id", table_name="credit_transactions")
    op.drop_table("credit_transactions")
