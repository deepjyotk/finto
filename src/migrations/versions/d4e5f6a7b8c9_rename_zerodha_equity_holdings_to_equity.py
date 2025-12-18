"""rename zerodha_equity_holdings_in to equity_holdings_in

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2025-12-17 15:00:00.000000

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.rename_table("zerodha_equity_holdings_in", "equity_holdings_in")


def downgrade() -> None:
    op.rename_table("equity_holdings_in", "zerodha_equity_holdings_in")
