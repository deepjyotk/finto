"""add_credits_left_to_users

Revision ID: 817b2afc547c
Revises: c095398b040f
Create Date: 2025-12-28 17:29:51.068319

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "817b2afc547c"
down_revision: Union[str, None] = "c095398b040f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create user_credits table."""
    from sqlalchemy.dialects import postgresql

    op.create_table(
        "user_credits",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("credits_left", sa.Integer(), nullable=False, server_default="5000"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["f_users.user_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
    )

    # Create index on user_id for faster lookups (optional since it's PK, but explicit)
    op.create_index("ix_user_credits_user_id", "user_credits", ["user_id"], unique=True)


def downgrade() -> None:
    """Drop user_credits table."""
    op.drop_index("ix_user_credits_user_id", table_name="user_credits")
    op.drop_table("user_credits")
