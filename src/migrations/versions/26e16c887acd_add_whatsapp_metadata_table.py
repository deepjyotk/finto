"""add_whatsapp_metadata_table

Revision ID: 26e16c887acd
Revises: baabf7e08baf
Create Date: 2025-11-12 19:03:12.464569

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "26e16c887acd"
down_revision: Union[str, None] = "baabf7e08baf"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create whatsapp_metadata table
    op.create_table(
        "whatsapp_metadata",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_e164", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["f_users.user_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_e164", name="uq_whatsapp_metadata_user_e164"),
    )

    # Create indexes
    op.create_index("ix_whatsapp_metadata_user_id", "whatsapp_metadata", ["user_id"])
    op.create_index("ix_whatsapp_metadata_user_e164", "whatsapp_metadata", ["user_e164"])


def downgrade() -> None:
    # Drop table
    op.drop_table("whatsapp_metadata")

