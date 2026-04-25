"""move f_ticker_info data into in_equities.company_metadata; drop f_ticker_info

Revision ID: l7m8n9o0p1q2
Revises: k5l6m7n8o9p0
Create Date: 2026-04-24

Adds JSONB `company_metadata` to `in_equities` (Yahoo / yfinance snapshot, same
shape as former `f_ticker_info.data`), backfills from `f_ticker_info` by NSE
symbol, then drops `f_ticker_info`.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "l7m8n9o0p1q2"
down_revision: Union[str, None] = "k5l6m7n8o9p0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "in_equities",
        sa.Column("company_metadata", postgresql.JSONB(), nullable=True),
    )

    op.execute(
        "CREATE INDEX ix_in_equities_company_metadata_gin "
        "ON in_equities USING gin(company_metadata)"
    )

    # Join on f_ticker_info.symbol = NSE symbol in in_equities
    op.execute(
        """
        UPDATE in_equities AS ie
        SET company_metadata = f.data,
            updated_at = now()
        FROM f_ticker_info AS f
        WHERE ie.symbol = f.symbol
        """
    )

    # Any rows that only line up on Yahoo-style symbol_ns (e.g. symbol column mismatch)
    op.execute(
        """
        UPDATE in_equities AS ie
        SET company_metadata = f.data,
            updated_at = now()
        FROM f_ticker_info AS f
        WHERE ie.company_metadata IS NULL
          AND split_part(f.symbol_ns, '.', 1) = ie.symbol
        """
    )

    op.execute("DROP INDEX IF EXISTS ix_ticker_info_data_gin")
    op.drop_index("ix_ticker_info_symbol_ns", table_name="f_ticker_info")
    op.drop_table("f_ticker_info")


def downgrade() -> None:
    op.create_table(
        "f_ticker_info",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("symbol", sa.Text(), nullable=False),
        sa.Column("symbol_ns", sa.Text(), nullable=False),
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
    op.create_index("ix_ticker_info_symbol_ns", "f_ticker_info", ["symbol_ns"])
    op.execute("CREATE INDEX ix_ticker_info_data_gin ON f_ticker_info USING gin(data)")

    op.execute(
        """
        INSERT INTO f_ticker_info (symbol, symbol_ns, data, updated_at)
        SELECT
            symbol,
            symbol || '.NS',
            company_metadata,
            updated_at
        FROM in_equities
        WHERE company_metadata IS NOT NULL
        """
    )

    op.execute("DROP INDEX IF EXISTS ix_in_equities_company_metadata_gin")
    op.drop_column("in_equities", "company_metadata")
