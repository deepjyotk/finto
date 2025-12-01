"""create_new_chat_sessions_table

Revision ID: 1edafd6f62a3
Revises: 42390efeb096
Create Date: 2025-11-30 13:57:27.869169

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "1edafd6f62a3"
down_revision: Union[str, None] = "42390efeb096"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "chat_sessions",
        sa.Column(
            "chat_session_id",
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
        sa.ForeignKeyConstraint(["user_id"], ["f_users.user_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("chat_session_id"),
    )


def downgrade() -> None:
    op.drop_table("chat_sessions")
