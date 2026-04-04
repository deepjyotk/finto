"""add whatsapp_cache table

Revision ID: baabf7e08baf
Revises: 00feae39281d
Create Date: 2025-01-27 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "baabf7e08baf"
down_revision: Union[str, None] = "00feae39281d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create whatsapp_cache table
    op.create_table(
        "whatsapp_cache",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("temporary_code", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["f_users.user_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create indexes
    op.create_index("ix_whatsapp_cache_temporary_code", "whatsapp_cache", ["temporary_code"])
    op.create_index("ix_whatsapp_cache_created_at", "whatsapp_cache", ["created_at"])


def downgrade() -> None:
    # Drop table
    op.drop_table("whatsapp_cache")
