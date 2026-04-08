"""add google oauth fields to f_users

Revision ID: f8a9b0c1d2e3
Revises: d5e6f7a8b9c0
Create Date: 2026-04-07

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f8a9b0c1d2e3"
down_revision: Union[str, None] = "d5e6f7a8b9c0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("f_users", sa.Column("google_id", sa.Text(), nullable=True))
    op.add_column(
        "f_users",
        sa.Column(
            "auth_provider",
            sa.Text(),
            server_default=sa.text("'local'"),
            nullable=False,
        ),
    )
    op.create_index(op.f("ix_f_users_google_id"), "f_users", ["google_id"], unique=True)
    op.alter_column("f_users", "password_hash", existing_type=sa.Text(), nullable=True)


def downgrade() -> None:
    op.alter_column("f_users", "password_hash", existing_type=sa.Text(), nullable=False)
    op.drop_index(op.f("ix_f_users_google_id"), table_name="f_users")
    op.drop_column("f_users", "auth_provider")
    op.drop_column("f_users", "google_id")
