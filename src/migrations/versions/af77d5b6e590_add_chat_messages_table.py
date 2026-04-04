"""add_chat_messages_table

Revision ID: af77d5b6e590
Revises: 1edafd6f62a3
Create Date: 2025-11-30 17:53:49.026224

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "af77d5b6e590"
down_revision: Union[str, None] = "1edafd6f62a3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create enum type for chat_message_type
    op.execute(
        """
        DO $$ BEGIN
            CREATE TYPE chat_message_type AS ENUM ('User', 'AI');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """
    )

    # Create chat_messages table
    op.create_table(
        "chat_messages",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("seq_no", sa.BigInteger(), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "message_type",
            postgresql.ENUM("User", "AI", name="chat_message_type", create_type=False),
            nullable=False,
        ),
        sa.Column("reply_to_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("thread_root_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("edited_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["session_id"], ["chat_sessions.chat_session_id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["f_users.user_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["reply_to_id"], ["chat_messages.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["thread_root_id"], ["chat_messages.id"], ondelete="SET NULL"
        ),
        sa.UniqueConstraint(
            "session_id", "seq_no", name="uq_chat_messages_session_seq"
        ),
    )

    # Create indexes
    op.create_index(
        "idx_chat_messages_session_seq",
        "chat_messages",
        ["session_id", "seq_no"],
        unique=False,
    )
    op.create_index(
        "idx_chat_messages_session_created_at",
        "chat_messages",
        ["session_id", sa.text("created_at DESC")],
        unique=False,
    )


def downgrade() -> None:
    # Drop indexes
    op.drop_index("idx_chat_messages_session_created_at", table_name="chat_messages")
    op.drop_index("idx_chat_messages_session_seq", table_name="chat_messages")

    # Drop table
    op.drop_table("chat_messages")

    # Drop enum type
    op.execute("DROP TYPE IF EXISTS chat_message_type")
