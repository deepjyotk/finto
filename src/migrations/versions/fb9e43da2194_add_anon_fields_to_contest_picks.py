"""add_anon_fields_to_contest_picks

Revision ID: fb9e43da2194
Revises: 64d2e647a9a2
Create Date: 2026-04-19 14:12:47.436146

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'fb9e43da2194'
down_revision: Union[str, None] = '64d2e647a9a2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('f_contest_picks', sa.Column('anon_id', sa.Text(), nullable=True))
    op.add_column('f_contest_picks', sa.Column('display_name', sa.Text(), nullable=True))
    op.add_column('f_contest_picks', sa.Column('ip_address', sa.Text(), nullable=True))
    op.alter_column('f_contest_picks', 'user_id', existing_type=sa.UUID(), nullable=True)
    op.create_index('ix_f_contest_picks_anon_id', 'f_contest_picks', ['anon_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_f_contest_picks_anon_id', table_name='f_contest_picks')
    op.alter_column('f_contest_picks', 'user_id', existing_type=sa.UUID(), nullable=False)
    op.drop_column('f_contest_picks', 'ip_address')
    op.drop_column('f_contest_picks', 'display_name')
    op.drop_column('f_contest_picks', 'anon_id')
