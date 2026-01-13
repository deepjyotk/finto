"""add holding_syncs table

Revision ID: d5e6f7a8b9c0
Revises: b4c5d6e7f8a9
Create Date: 2026-01-02 10:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "d5e6f7a8b9c0"
down_revision: Union[str, None] = "b4c5d6e7f8a9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create holding_syncs table"""
    op.create_table(
        "holding_syncs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("synced_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "synced_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(["user_id"], ["f_users.user_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_holding_syncs_user_id"), "holding_syncs", ["user_id"], unique=False)
    op.create_index(
        op.f("ix_holding_syncs_synced_at"), "holding_syncs", ["synced_at"], unique=False
    )


def downgrade() -> None:
    """Drop holding_syncs table"""
    op.drop_index(op.f("ix_holding_syncs_synced_at"), table_name="holding_syncs")
    op.drop_index(op.f("ix_holding_syncs_user_id"), table_name="holding_syncs")
    op.drop_table("holding_syncs")
