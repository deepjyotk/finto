"""rename_chat_sessions_to_whatsapp_chat_sessions

Revision ID: 42390efeb096
Revises: e7e0b5f7c9d0
Create Date: 2025-11-30 13:56:54.702407

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "42390efeb096"
down_revision: Union[str, None] = "e7e0b5f7c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Rename the enum type
    op.execute(
        "ALTER TYPE chat_session_closed_reason RENAME TO whatsapp_chat_session_closed_reason"
    )

    # Rename the table
    op.rename_table("chat_sessions", "whatsapp_chat_sessions")

    # Rename columns
    op.alter_column("whatsapp_chat_sessions", "session_id", new_column_name="whatsapp_session_id")
    op.alter_column("whatsapp_chat_sessions", "started_at", new_column_name="whatsapp_started_at")
    op.alter_column(
        "whatsapp_chat_sessions",
        "last_activity_at",
        new_column_name="whatsapp_last_activity_at",
    )
    op.alter_column("whatsapp_chat_sessions", "expires_at", new_column_name="whatsapp_expires_at")
    op.alter_column("whatsapp_chat_sessions", "is_active", new_column_name="whatsapp_is_active")
    op.alter_column("whatsapp_chat_sessions", "closed_at", new_column_name="whatsapp_closed_at")
    op.alter_column(
        "whatsapp_chat_sessions",
        "closed_reason",
        new_column_name="whatsapp_closed_reason",
    )
    op.alter_column("whatsapp_chat_sessions", "metadata", new_column_name="whatsapp_metadata")

    # Drop and recreate indexes with new names and column references
    op.drop_index("idx_chat_sessions_active_expiry", table_name="whatsapp_chat_sessions")
    op.drop_index("idx_chat_sessions_user_active_expiry", table_name="whatsapp_chat_sessions")
    op.drop_index("uq_chat_sessions_user_active", table_name="whatsapp_chat_sessions")

    op.create_index(
        "idx_whatsapp_chat_sessions_active_expiry",
        "whatsapp_chat_sessions",
        ["whatsapp_expires_at"],
        postgresql_where=sa.text("whatsapp_is_active = TRUE"),
    )
    op.create_index(
        "idx_whatsapp_chat_sessions_user_active_expiry",
        "whatsapp_chat_sessions",
        ["user_id"],
        postgresql_where=sa.text("whatsapp_is_active = TRUE"),
    )
    op.create_index(
        "uq_whatsapp_chat_sessions_user_active",
        "whatsapp_chat_sessions",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("whatsapp_is_active = TRUE"),
    )


def downgrade() -> None:
    # Drop new indexes
    op.drop_index("uq_whatsapp_chat_sessions_user_active", table_name="whatsapp_chat_sessions")
    op.drop_index(
        "idx_whatsapp_chat_sessions_user_active_expiry",
        table_name="whatsapp_chat_sessions",
    )
    op.drop_index("idx_whatsapp_chat_sessions_active_expiry", table_name="whatsapp_chat_sessions")

    # Recreate old indexes
    op.create_index(
        "idx_chat_sessions_active_expiry",
        "whatsapp_chat_sessions",
        ["whatsapp_expires_at"],
        postgresql_where=sa.text("whatsapp_is_active = TRUE"),
    )
    op.create_index(
        "idx_chat_sessions_user_active_expiry",
        "whatsapp_chat_sessions",
        ["user_id"],
        postgresql_where=sa.text("whatsapp_is_active = TRUE"),
    )
    op.create_index(
        "uq_chat_sessions_user_active",
        "whatsapp_chat_sessions",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("whatsapp_is_active = TRUE"),
    )

    # Rename columns back
    op.alter_column("whatsapp_chat_sessions", "whatsapp_metadata", new_column_name="metadata")
    op.alter_column(
        "whatsapp_chat_sessions",
        "whatsapp_closed_reason",
        new_column_name="closed_reason",
    )
    op.alter_column("whatsapp_chat_sessions", "whatsapp_closed_at", new_column_name="closed_at")
    op.alter_column("whatsapp_chat_sessions", "whatsapp_is_active", new_column_name="is_active")
    op.alter_column("whatsapp_chat_sessions", "whatsapp_expires_at", new_column_name="expires_at")
    op.alter_column(
        "whatsapp_chat_sessions",
        "whatsapp_last_activity_at",
        new_column_name="last_activity_at",
    )
    op.alter_column("whatsapp_chat_sessions", "whatsapp_started_at", new_column_name="started_at")
    op.alter_column("whatsapp_chat_sessions", "whatsapp_session_id", new_column_name="session_id")

    # Rename the table back
    op.rename_table("whatsapp_chat_sessions", "chat_sessions")

    # Rename the enum type back
    op.execute(
        "ALTER TYPE whatsapp_chat_session_closed_reason RENAME TO chat_session_closed_reason"
    )
