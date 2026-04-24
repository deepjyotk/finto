"""Repository: financial statements from f_financial_statements (JSONB schema)."""

from __future__ import annotations

from datetime import date

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class FinancialStatementsRepo:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def get_statements(
        self,
        symbol_ns: str,
        statement_type: str,      # 'annual' | 'quarterly'
        limit_periods: int = 12,
    ) -> list[dict]:
        """
        Return JSONB rows for one symbol, one statement type, newest-first.

        Each row: {"period": date, "data": {"Net Income": 179181000000, ...}}

        Uses ix_fin_symbol_type_period for a fast index scan — touches only
        the relevant rows for this stock, no full table scan.

        Example query an LLM would generate from this table:
            SELECT period, data->>'Net Income' AS net_income
            FROM f_financial_statements
            WHERE symbol_ns = 'RELIANCE.NS' AND statement_type = 'annual'
            ORDER BY period DESC LIMIT 5;
        """
        stmt = text(
            """
            SELECT period, data
            FROM   f_financial_statements
            WHERE  symbol_ns      = :symbol_ns
              AND  statement_type = :stmt_type
            ORDER  BY period DESC
            LIMIT  :lim
            """
        )
        result = await self._s.execute(
            stmt,
            {"symbol_ns": symbol_ns, "stmt_type": statement_type, "lim": limit_periods},
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

        Uses the GIN index (ix_pnl_data_gin) to quickly find rows where the
        metric key exists, then the B-tree for period filtering.

        Example: Net Income trend for a basket of stocks over 5 years.
        Equivalent LLM query:
            SELECT symbol_ns, period, (data->>'Net Income')::numeric AS value
            FROM f_financial_statements
            WHERE statement_type = 'annual'
              AND period >= '2020-01-01'
              AND symbol_ns = ANY(ARRAY['RELIANCE.NS', 'TCS.NS'])
              AND data ? 'Net Income'
            ORDER BY symbol_ns, period;
        """
        stmt = text(
            """
            SELECT symbol_ns,
                   period,
                   (data ->> :metric)::numeric AS value
            FROM   f_financial_statements
            WHERE  statement_type = :stmt_type
              AND  period        >= :since
              AND  symbol_ns      = ANY(:syms)
              AND  data           ? :metric
            ORDER  BY symbol_ns, period
            """
        )
        result = await self._s.execute(
            stmt,
            {
                "metric": metric,
                "stmt_type": statement_type,
                "since": since,
                "syms": symbols_ns,
            },
        )
        return [{"symbol_ns": r.symbol_ns, "period": r.period, "value": r.value}
                for r in result]

