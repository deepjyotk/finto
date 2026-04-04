"""add chat_sessions table

Revision ID: e7e0b5f7c9d0
Revises: 26e16c887acd
Create Date: 2025-11-15 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "e7e0b5f7c9d0"
down_revision: Union[str, None] = "26e16c887acd"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    closed_reason_enum = postgresql.ENUM(
        "timeout",
        "user_new_chat",
        name="chat_session_closed_reason",
        create_type=False,
    )

    closed_reason_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "chat_sessions",
        sa.Column(
            "session_id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "last_activity_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("TRUE"), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_reason", closed_reason_enum, nullable=True),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["f_users.user_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("session_id"),
    )

    op.create_index(
        "idx_chat_sessions_active_expiry",
        "chat_sessions",
        ["expires_at"],
        postgresql_where=sa.text("is_active = TRUE"),
    )
    op.create_index(
        "idx_chat_sessions_user_active_expiry",
        "chat_sessions",
        ["user_id"],
        postgresql_where=sa.text("is_active = TRUE"),
    )
    op.create_index(
        "uq_chat_sessions_user_active",
        "chat_sessions",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("is_active = TRUE"),
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_chat_sessions_user_active")
    op.drop_index("idx_chat_sessions_user_active_expiry", table_name="chat_sessions")
    op.drop_index("idx_chat_sessions_active_expiry", table_name="chat_sessions")
    op.drop_table("chat_sessions")

    op.execute("DROP TYPE IF EXISTS chat_session_closed_reason")
