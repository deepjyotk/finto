"""add_pending_registrations_table

Revision ID: b4c5d6e7f8a9
Revises: a3f9e8d1b2c5
Create Date: 2025-12-28 20:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "b4c5d6e7f8a9"
down_revision: Union[str, None] = "a3f9e8d1b2c5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create pending_registrations table for OTP verification during registration."""
    op.create_table(
        "pending_registrations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.Text(), nullable=False, unique=True),
        sa.Column("username", sa.Text(), nullable=False),
        sa.Column("full_name", sa.Text(), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("otp_hash", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create indexes
    op.create_index(
        "idx_pending_registrations_email", "pending_registrations", ["email"]
    )
    op.create_index(
        "idx_pending_registrations_expires_at", "pending_registrations", ["expires_at"]
    )


def downgrade() -> None:
    """Drop pending_registrations table and its indexes."""
    op.drop_index(
        "idx_pending_registrations_expires_at", table_name="pending_registrations"
    )
    op.drop_index("idx_pending_registrations_email", table_name="pending_registrations")
    op.drop_table("pending_registrations")
