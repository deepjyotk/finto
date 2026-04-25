"""key financial statements by in_equities.id

Revision ID: m8n9o0p1q2r3
Revises: l7m8n9o0p1q2
Create Date: 2026-04-24

Replace duplicated `symbol` and `symbol_ns` columns on f_financial_statements
with the canonical `in_equity_id` foreign key.

Rows that cannot be matched to `in_equities` (after normalizing symbol) are
removed so the migration can complete; see NOTICE in the DB log for a count.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "m8n9o0p1q2r3"
down_revision: Union[str, None] = "l7m8n9o0p1q2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "f_financial_statements",
        sa.Column("in_equity_id", postgresql.UUID(as_uuid=True), nullable=True),
    )

    # Backfill: match on normalized NSE symbol. Loader/yfinance can leave stray
    # spaces or case drift; in_equities may not be strictly uppercased.
    op.execute(
        """
        UPDATE f_financial_statements AS fs
        SET in_equity_id = ie.id
        FROM in_equities AS ie
        WHERE fs.in_equity_id IS NULL
          AND upper(btrim(ie.symbol)) = upper(btrim(COALESCE(fs.symbol, '')))
          AND btrim(COALESCE(fs.symbol, '')) != ''
        """
    )
    op.execute(
        """
        UPDATE f_financial_statements AS fs
        SET in_equity_id = ie.id
        FROM in_equities AS ie
        WHERE fs.in_equity_id IS NULL
          AND btrim(COALESCE(fs.symbol_ns, '')) != ''
          AND upper(btrim(ie.symbol))
            = split_part(upper(btrim(COALESCE(fs.symbol_ns, ''))), '.', 1)
        """
    )
    # Orphan financial rows: delisted / never in in_equities — no FK to attach.
    op.execute(
        r"""
        DO $orphan$
        DECLARE
            n int;
        BEGIN
            DELETE FROM f_financial_statements WHERE in_equity_id IS NULL;
            GET DIAGNOSTICS n = ROW_COUNT;
            IF n > 0 THEN
                RAISE NOTICE
                    'm8n9o0p1q2r3: removed % f_financial_statements rows (no in_equities match)', n;
            END IF;
        END $orphan$;
        """
    )

    op.drop_index("ix_fin_symbol_type_period", table_name="f_financial_statements")
    op.drop_constraint(
        "uq_pnl_symbol_type_period",
        "f_financial_statements",
        type_="unique",
    )

    op.alter_column("f_financial_statements", "in_equity_id", nullable=False)
    op.create_foreign_key(
        op.f("fk_f_financial_statements_in_equity_id_in_equities"),
        "f_financial_statements",
        "in_equities",
        ["in_equity_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_unique_constraint(
        "uq_fin_equity_type_period",
        "f_financial_statements",
        ["in_equity_id", "statement_type", "period"],
    )
    op.create_index(
        "ix_fin_equity_type_period",
        "f_financial_statements",
        ["in_equity_id", "statement_type", "period"],
    )

    op.drop_column("f_financial_statements", "symbol_ns")
    op.drop_column("f_financial_statements", "symbol")


def downgrade() -> None:
    op.add_column(
        "f_financial_statements",
        sa.Column("symbol", sa.Text(), nullable=True),
    )
    op.add_column(
        "f_financial_statements",
        sa.Column("symbol_ns", sa.Text(), nullable=True),
    )

    op.execute(
        """
        UPDATE f_financial_statements AS fs
        SET symbol = ie.symbol,
            symbol_ns = ie.symbol || '.NS'
        FROM in_equities AS ie
        WHERE fs.in_equity_id = ie.id
        """
    )

    op.alter_column("f_financial_statements", "symbol", nullable=False)
    op.alter_column("f_financial_statements", "symbol_ns", nullable=False)

    op.drop_index("ix_fin_equity_type_period", table_name="f_financial_statements")
    op.drop_constraint(
        "uq_fin_equity_type_period",
        "f_financial_statements",
        type_="unique",
    )
    op.drop_constraint(
        op.f("fk_f_financial_statements_in_equity_id_in_equities"),
        "f_financial_statements",
        type_="foreignkey",
    )
    op.drop_column("f_financial_statements", "in_equity_id")

    op.create_unique_constraint(
        "uq_pnl_symbol_type_period",
        "f_financial_statements",
        ["symbol_ns", "statement_type", "period"],
    )
    op.create_index(
        "ix_fin_symbol_type_period",
        "f_financial_statements",
        ["symbol_ns", "statement_type", "period"],
    )
