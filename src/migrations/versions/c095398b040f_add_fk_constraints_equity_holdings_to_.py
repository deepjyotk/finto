"""add_fk_constraints_equity_holdings_to_in_equities

Revision ID: c095398b040f
Revises: c3d4e5f6a7b8
Create Date: 2025-12-19 23:00:58.571553

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c095398b040f"
down_revision: Union[str, None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Rename isin column to company_name in equity_holdings_in
    op.alter_column(
        "equity_holdings_in",
        "isin",
        new_column_name="company_name",
    )


def downgrade() -> None:
    # Rename company_name back to isin
    op.alter_column(
        "equity_holdings_in",
        "company_name",
        new_column_name="isin",
    )
