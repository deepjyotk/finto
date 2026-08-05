"""Repository: bulk data loading for the stock screener.

Loads all data needed by the screener in a small number of DB round-trips
rather than making per-symbol yfinance network calls.

Tables used
-----------
  in_equities          — equity universe + company_metadata (yfinance-style JSONB)
  f_income_statements  — annual typed income rows (total_revenue, ebitda, …)
  f_balance_sheets     — annual typed balance rows (total_debt, stockholders_equity, …)

Display-name keys returned in the `data` dicts match those in
`financial_statements_repo._INCOME_DISPLAY` / `_BALANCE_DISPLAY` so that
screener filter helpers can use them directly.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# ---------------------------------------------------------------------------
# Column → display-name maps (subset used by screener only)
# ---------------------------------------------------------------------------

_INCOME_DISPLAY: dict[str, str] = {
    "total_revenue": "Total Revenue",
    "operating_income": "Operating Income",
    "ebitda": "EBITDA",
    "interest_expense": "Interest Expense",
    "net_income": "Net Income",
    "basic_eps": "Basic EPS",
}

_BALANCE_DISPLAY: dict[str, str] = {
    "total_assets": "Total Assets",
    "current_assets": "Current Assets",
    "cash_and_cash_equivalents": "Cash And Cash Equivalents",
    "total_liabilities": "Total Liabilities Net Minority Interest",
    "current_liabilities": "Current Liabilities",
    "current_debt": "Current Debt",
    "long_term_debt": "Long Term Debt",
    "total_debt": "Total Debt",
    "stockholders_equity": "Stockholders Equity",
    "working_capital": "Working Capital",
}

_INCOME_COLS = ", ".join(_INCOME_DISPLAY.keys())
_BALANCE_COLS = ", ".join(_BALANCE_DISPLAY.keys())


def _income_row_to_dict(row) -> dict:
    return {
        display: float(val)
        for col, display in _INCOME_DISPLAY.items()
        if (val := getattr(row, col, None)) is not None
    }


def _balance_row_to_dict(row) -> dict:
    return {
        display: float(val)
        for col, display in _BALANCE_DISPLAY.items()
        if (val := getattr(row, col, None)) is not None
    }


class ScreenerRepo:
    """Bulk data loader for the stock screener.

    All methods perform a single SQL round-trip regardless of universe size,
    using window functions (ROW_NUMBER) for top-N-per-group queries.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    # ── public ───────────────────────────────────────────────────────────────

    async def load_equities_with_metadata(self) -> list[dict]:
        """Return all equity rows with their company_metadata JSONB snapshot.

        Returns
        -------
        list of dicts with keys:
            id           : UUID
            symbol       : str (bare NSE symbol, e.g. "RELIANCE")
            company_metadata : dict | None  (yfinance-style info snapshot)
        """
        result = await self._s.execute(
            text(
                """
                SELECT id, symbol, company_metadata
                FROM   in_equities
                ORDER  BY symbol
                """
            )
        )
        return [
            {
                "id": row.id,
                "symbol": row.symbol,
                "info": row.company_metadata or {},
            }
            for row in result
        ]

    async def load_latest_income_rows(
        self,
        equity_ids: list[UUID],
        n_periods: int = 2,
    ) -> dict[UUID, list[dict]]:
        """Bulk-load the latest *n_periods* annual income rows per equity.

        Returns
        -------
        dict mapping equity UUID → list of row dicts (newest first), where each
        row dict has key ``"data"`` containing ``{display_name: float}`` entries.

        Uses a window function so only one SQL round-trip is needed for all IDs.
        """
        if not equity_ids:
            return {}

        result = await self._s.execute(
            text(
                f"""
                SELECT in_equity_id, period, {_INCOME_COLS}
                FROM (
                    SELECT in_equity_id, period, {_INCOME_COLS},
                           ROW_NUMBER() OVER (
                               PARTITION BY in_equity_id
                               ORDER BY period DESC
                           ) AS rn
                    FROM   f_income_statements
                    WHERE  in_equity_id = ANY(:ids)
                      AND  statement_type = 'annual'
                ) ranked
                WHERE rn <= :n
                ORDER BY in_equity_id, period DESC
                """
            ),
            {"ids": equity_ids, "n": n_periods},
        )

        out: dict[UUID, list[dict]] = {}
        for row in result:
            eid = row.in_equity_id
            out.setdefault(eid, []).append({"data": _income_row_to_dict(row)})
        return out

    async def load_latest_balance_rows(
        self,
        equity_ids: list[UUID],
        n_periods: int = 1,
    ) -> dict[UUID, list[dict]]:
        """Bulk-load the latest *n_periods* annual balance sheet rows per equity.

        Returns
        -------
        dict mapping equity UUID → list of row dicts (newest first), where each
        row dict has key ``"data"`` containing ``{display_name: float}`` entries.
        """
        if not equity_ids:
            return {}

        result = await self._s.execute(
            text(
                f"""
                SELECT in_equity_id, period, {_BALANCE_COLS}
                FROM (
                    SELECT in_equity_id, period, {_BALANCE_COLS},
                           ROW_NUMBER() OVER (
                               PARTITION BY in_equity_id
                               ORDER BY period DESC
                           ) AS rn
                    FROM   f_balance_sheets
                    WHERE  in_equity_id = ANY(:ids)
                      AND  statement_type = 'annual'
                ) ranked
                WHERE rn <= :n
                ORDER BY in_equity_id, period DESC
                """
            ),
            {"ids": equity_ids, "n": n_periods},
        )

        out: dict[UUID, list[dict]] = {}
        for row in result:
            eid = row.in_equity_id
            out.setdefault(eid, []).append({"data": _balance_row_to_dict(row)})
        return out
