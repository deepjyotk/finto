"""drop unused columns from zerodha_equity_holdings_in

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2025-12-17 14:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("zerodha_equity_holdings_in", "qty_discrepant")
    op.drop_column("zerodha_equity_holdings_in", "qty_pledged_loan")
    op.drop_column("zerodha_equity_holdings_in", "unrealized_pnl")
    op.drop_column("zerodha_equity_holdings_in", "unrealized_pnl_pct")


def downgrade() -> None:
    op.add_column(
        "zerodha_equity_holdings_in",
        sa.Column("unrealized_pnl_pct", sa.Numeric(precision=10, scale=4), nullable=False),
    )
    op.add_column(
        "zerodha_equity_holdings_in",
        sa.Column("unrealized_pnl", sa.Numeric(precision=20, scale=4), nullable=False),
    )
    op.add_column(
        "zerodha_equity_holdings_in",
        sa.Column("qty_pledged_loan", sa.Integer(), nullable=False),
    )
    op.add_column(
        "zerodha_equity_holdings_in",
        sa.Column("qty_discrepant", sa.Integer(), nullable=False),
    )
