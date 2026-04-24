"""rename f_pnl_statements to f_financial_statements

Revision ID: j4k5l6m7n8o9
Revises: i3j4k5l6m7n8
Create Date: 2026-04-24

f_pnl_statements was a poor name — the table stores income statements,
balance sheets, AND cash flow statements (not just P&L).
Renaming to f_financial_statements along with its indexes.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "j4k5l6m7n8o9"
down_revision: Union[str, None] = "i3j4k5l6m7n8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.rename_table("f_pnl_statements", "f_financial_statements")

    # Rename indexes to match new table name
    op.execute("ALTER INDEX ix_pnl_symbol_type_period RENAME TO ix_fin_symbol_type_period")
    op.execute("ALTER INDEX ix_pnl_data_gin          RENAME TO ix_fin_data_gin")


def downgrade() -> None:
    op.execute("ALTER INDEX ix_fin_data_gin          RENAME TO ix_pnl_data_gin")
    op.execute("ALTER INDEX ix_fin_symbol_type_period RENAME TO ix_pnl_symbol_type_period")
    op.rename_table("f_financial_statements", "f_pnl_statements")
