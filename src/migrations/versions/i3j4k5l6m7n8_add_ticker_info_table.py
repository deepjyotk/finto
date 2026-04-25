"""add f_ticker_info table

Revision ID: i3j4k5l6m7n8
Revises: h2b3c4d5e6f7
Create Date: 2026-04-24

Table: f_ticker_info
Stores latest yfinance ticker info snapshot for each NSE stock.
One row per symbol — updated whenever the fetch script runs.

All market/fundamental metrics live in the JSONB `data` column:
  {
    "marketCap": 19540000000000,
    "trailingPE": 24.3,
    "forwardPE": 21.1,
    "priceToBook": 2.1,
    "dividendYield": 0.0035,
    "returnOnEquity": 0.142,
    "returnOnAssets": 0.063,
    "debtToEquity": 38.2,
    "currentRatio": 1.4,
    "earningsGrowth": 0.18,
    "revenueGrowth": 0.09,
    "grossMargins": 0.48,
    "operatingMargins": 0.22,
    "profitMargins": 0.20,
    "beta": 0.92,
    "fiftyTwoWeekHigh": 1608.0,
    "fiftyTwoWeekLow": 1115.0,
    "sector": "Energy",
    "industry": "Oil & Gas Refining & Marketing",
    "fullTimeEmployees": 236334,
    ...
  }

LLM query examples:
  -- Stocks with P/E < 15:
  SELECT symbol_ns, (data->>'trailingPE')::numeric AS pe
  FROM f_ticker_info WHERE (data->>'trailingPE')::numeric < 15;

  -- Top 10 by market cap:
  SELECT symbol_ns, (data->>'marketCap')::numeric AS mktcap
  FROM f_ticker_info ORDER BY mktcap DESC LIMIT 10;
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "i3j4k5l6m7n8"
down_revision: Union[str, None] = "h2b3c4d5e6f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "f_ticker_info",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("symbol", sa.Text(), nullable=False),
        sa.Column("symbol_ns", sa.Text(), nullable=False),
        # Full yfinance info snapshot — all ratios, sector, employees, etc.
        sa.Column("data", postgresql.JSONB(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("symbol_ns", name="uq_ticker_info_symbol_ns"),
    )

    # B-tree for direct symbol lookups
    op.create_index("ix_ticker_info_symbol_ns", "f_ticker_info", ["symbol_ns"])

    # GIN for cross-stock screener queries:
    #   WHERE (data->>'trailingPE')::numeric < 20
    #   WHERE data->>'sector' = 'Technology'
    op.execute("CREATE INDEX ix_ticker_info_data_gin ON f_ticker_info USING gin(data)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_ticker_info_data_gin")
    op.drop_index("ix_ticker_info_symbol_ns", table_name="f_ticker_info")
    op.drop_table("f_ticker_info")
