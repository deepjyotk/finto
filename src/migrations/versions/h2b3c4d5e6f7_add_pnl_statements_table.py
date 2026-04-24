"""add f_pnl_statements table (JSONB schema)

Revision ID: h2b3c4d5e6f7
Revises: 64d2e647a9a2
Create Date: 2026-04-24

Table: f_pnl_statements
Stores annual + quarterly income statements fetched from yfinance for all
NSE-listed equities. One row per (symbol_ns, statement_type, period) with
all metrics packed into a JSONB column.

Example row:
  symbol_ns      = 'RELIANCE.NS'
  statement_type = 'annual'
  period         = 2024-03-31
  data           = {"Total Revenue": 899328000000, "Net Income": 179181000000,
                    "EBITDA": 285432000000, "Basic EPS": 26.5, ...}

~10x fewer rows than EAV (80K vs 800K). LLM-generated queries are simple:
  SELECT symbol_ns, (data->>'Net Income')::numeric AS net_income
  FROM f_pnl_statements
  WHERE statement_type = 'annual' AND period = '2024-03-31'

Index strategy:
  1. B-tree on (symbol_ns, statement_type, period)  — fast single-stock page load
  2. GIN on data                                    — fast `data ? 'metric'` and
                                                       `data @> '{"key":...}'` screener queries
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "h2b3c4d5e6f7"
down_revision: Union[str, None] = "fb9e43da2194"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "f_financial_statements",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("symbol", sa.Text(), nullable=False),
        sa.Column("symbol_ns", sa.Text(), nullable=False),
        # 'annual' | 'quarterly'
        sa.Column("statement_type", sa.Text(), nullable=False),
        # Period end date (e.g. 2024-03-31)
        sa.Column("period", sa.Date(), nullable=False),
        # All metrics for this period: {"Net Income": 179181000000, "Total Revenue": ...}
        sa.Column("data", postgresql.JSONB(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "symbol_ns", "statement_type", "period",
            name="uq_pnl_symbol_type_period",
        ),
    )

    # ── Index 1: single-stock page (most common query) ───────────────────
    # Covers: WHERE symbol_ns = X AND statement_type = Y ORDER BY period DESC LIMIT N
    op.create_index(
        "ix_fin_symbol_type_period",
        "f_financial_statements",
        ["symbol_ns", "statement_type", "period"],
    )

    # ── Index 2: GIN on JSONB data ────────────────────────────────────────────────
    # Enables efficient cross-stock screener queries like:
    #   WHERE data ? 'Net Income'          (stock has this metric)
    #   WHERE (data->>'Net Income')::numeric > 1e10
    op.execute(
        "CREATE INDEX ix_fin_data_gin ON f_financial_statements USING gin(data)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_fin_data_gin")
    op.drop_index("ix_fin_symbol_type_period", table_name="f_financial_statements")
    op.drop_table("f_financial_statements")
