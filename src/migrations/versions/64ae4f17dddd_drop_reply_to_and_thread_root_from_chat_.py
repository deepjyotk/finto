"""drop_reply_to_and_thread_root_from_chat_messages

Revision ID: 64ae4f17dddd
Revises: af77d5b6e590
Create Date: 2025-11-30 22:27:32.082598

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "64ae4f17dddd"
down_revision: Union[str, None] = "af77d5b6e590"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop foreign key constraints first (using IF EXISTS for safety)
    op.execute(
        """
        DO $$ 
        BEGIN
            IF EXISTS (
                SELECT 1 FROM pg_constraint 
                WHERE conname = 'chat_messages_reply_to_id_fkey'
            ) THEN
                ALTER TABLE chat_messages DROP CONSTRAINT chat_messages_reply_to_id_fkey;
            END IF;

            IF EXISTS (
                SELECT 1 FROM pg_constraint 
                WHERE conname = 'chat_messages_thread_root_id_fkey'
            ) THEN
                ALTER TABLE chat_messages DROP CONSTRAINT chat_messages_thread_root_id_fkey;
            END IF;
        END $$;
        """
    )
    # Drop the columns
    op.drop_column("chat_messages", "reply_to_id")
    op.drop_column("chat_messages", "thread_root_id")


def downgrade() -> None:
    # Re-add the columns
    op.add_column(
        "chat_messages",
        sa.Column("reply_to_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "chat_messages",
        sa.Column("thread_root_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    # Re-add the foreign key constraints
    op.create_foreign_key(
        "chat_messages_reply_to_id_fkey",
        "chat_messages",
        "chat_messages",
        ["reply_to_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "chat_messages_thread_root_id_fkey",
        "chat_messages",
        "chat_messages",
        ["thread_root_id"],
        ["id"],
        ondelete="SET NULL",
    )
