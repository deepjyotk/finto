"""merge_contest_tables

Revision ID: 64d2e647a9a2
Revises: f8a9b0c1d2e3, g1a2b3c4d5e6
Create Date: 2026-04-19 11:46:38.999874

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '64d2e647a9a2'
down_revision: Union[str, None] = ('f8a9b0c1d2e3', 'g1a2b3c4d5e6')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

