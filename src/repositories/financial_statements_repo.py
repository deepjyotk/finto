"""Repository: financial statements from f_financial_statements (JSONB schema)."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class FinancialStatementsRepo:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def get_statements(
        self,
        in_equity_id: UUID,
        statement_type: str,  # 'annual' | 'quarterly'
        limit_periods: int = 12,
    ) -> list[dict]:
        """
        Return JSONB rows for one equity, one statement type, newest-first.

        Each row: {"period": date, "data": {"Net Income": 179181000000, ...}}

        Uses ix_fin_equity_type_period for a fast index scan — touches only
        the relevant rows for this stock, no full table scan.

        Example query an LLM would generate from this table:
            SELECT period, data->>'Net Income' AS net_income
            FROM f_financial_statements
            WHERE in_equity_id = '<in_equities.id>' AND statement_type = 'annual'
            ORDER BY period DESC LIMIT 5;
        """
        stmt = text(
            """
            SELECT period, data
            FROM   f_financial_statements
            WHERE  in_equity_id   = :in_equity_id
              AND  statement_type = :stmt_type
            ORDER  BY period DESC
            LIMIT  :lim
            """
        )
        result = await self._s.execute(
            stmt,
            {"in_equity_id": in_equity_id, "stmt_type": statement_type, "lim": limit_periods},
        )
        return [{"period": r.period, "data": r.data} for r in result]

    async def get_metric_trend(
        self,
        symbols_ns: list[str],
        metric: str,
        statement_type: str,
        since: date,
    ) -> list[dict]:
        """
        Cross-stock metric trend — extracts one metric from JSONB for multiple stocks.

        Uses the GIN index (ix_fin_data_gin) to quickly find rows where the
        metric key exists, then the B-tree for period filtering.

        Example: Net Income trend for a basket of stocks over 5 years.
        Equivalent LLM query:
            SELECT ie.symbol || '.NS' AS symbol_ns,
                   fs.period,
                   (fs.data->>'Net Income')::numeric AS value
            FROM f_financial_statements AS fs
            JOIN in_equities AS ie ON ie.id = fs.in_equity_id
            WHERE fs.statement_type = 'annual'
              AND fs.period >= '2020-01-01'
              AND ie.symbol = ANY(ARRAY['RELIANCE', 'TCS'])
              AND fs.data ? 'Net Income'
            ORDER BY symbol_ns, fs.period;
        """
        symbols = [s.upper().strip().removesuffix(".NS") for s in symbols_ns]
        stmt = text(
            """
            SELECT ie.symbol || '.NS' AS symbol_ns,
                   fs.period,
                   (fs.data ->> :metric)::numeric AS value
            FROM   f_financial_statements AS fs
            JOIN   in_equities AS ie ON ie.id = fs.in_equity_id
            WHERE  fs.statement_type = :stmt_type
              AND  fs.period        >= :since
              AND  ie.symbol         = ANY(:syms)
              AND  fs.data           ? :metric
            ORDER  BY symbol_ns, fs.period
            """
        )
        result = await self._s.execute(
            stmt,
            {
                "metric": metric,
                "stmt_type": statement_type,
                "since": since,
                "syms": symbols,
            },
        )
        return [{"symbol_ns": r.symbol_ns, "period": r.period, "value": r.value} for r in result]
