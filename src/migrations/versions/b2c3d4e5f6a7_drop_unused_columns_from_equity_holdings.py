"""drop unused columns from equity_holdings_in (including timestamps)

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2025-12-17 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop columns if they exist (some may have been dropped in previous migrations)
    op.execute(
        """
        DO $$ 
        BEGIN
            ALTER TABLE equity_holdings_in DROP COLUMN IF EXISTS qty_discrepant;
            ALTER TABLE equity_holdings_in DROP COLUMN IF EXISTS qty_pledged_loan;
            ALTER TABLE equity_holdings_in DROP COLUMN IF EXISTS unrealized_pnl;
            ALTER TABLE equity_holdings_in DROP COLUMN IF EXISTS unrealized_pnl_pct;
            ALTER TABLE equity_holdings_in DROP COLUMN IF EXISTS created_at;
            ALTER TABLE equity_holdings_in DROP COLUMN IF EXISTS updated_at;
        END $$;
        """
    )


def downgrade() -> None:
    op.add_column(
        "equity_holdings_in",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.add_column(
        "equity_holdings_in",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.add_column(
        "equity_holdings_in",
        sa.Column(
            "unrealized_pnl_pct", sa.Numeric(precision=10, scale=4), nullable=False
        ),
    )
    op.add_column(
        "equity_holdings_in",
        sa.Column("unrealized_pnl", sa.Numeric(precision=20, scale=4), nullable=False),
    )
    op.add_column(
        "equity_holdings_in",
        sa.Column("qty_pledged_loan", sa.Integer(), nullable=False),
    )
    op.add_column(
        "equity_holdings_in",
        sa.Column("qty_discrepant", sa.Integer(), nullable=False),
    )
