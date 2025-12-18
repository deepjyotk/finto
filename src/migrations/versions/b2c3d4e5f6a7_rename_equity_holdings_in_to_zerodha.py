"""rename equity_holdings_in to zerodha_equity_holdings_in

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2025-12-17 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.rename_table("equity_holdings_in", "zerodha_equity_holdings_in")


def downgrade() -> None:
    op.rename_table("zerodha_equity_holdings_in", "equity_holdings_in")
