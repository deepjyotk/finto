"""Repository: typed financial statement tables.

Tables
------
  f_income_statements  — annual + quarterly income statements
  f_balance_sheets     — annual + quarterly balance sheets
  f_cash_flows         — annual + quarterly cash flow statements

Each get_*() method returns rows in the legacy `{period, data}` dict format so
that callers (ticker_service, screener) do not need to change.  The `data` dict
uses human-readable display names that match the ANNUAL_METRICS / BALANCE_SHEET_METRICS
/ CASH_FLOW_METRICS lists in ticker_service.py.
"""

from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# ---------------------------------------------------------------------------
# Display-name maps (column_name → display label used by ticker_service)
# ---------------------------------------------------------------------------

_INCOME_DISPLAY: dict[str, str] = {
    "total_revenue": "Total Revenue",
    "cost_of_revenue": "Cost of Revenue",
    "gross_profit": "Gross Profit",
    "operating_expense": "Operating Expense",
    "operating_income": "Operating Income",
    "ebitda": "EBITDA",
    "interest_expense": "Interest Expense",
    "tax_provision": "Tax Provision",
    "pretax_income": "Pretax Income",
    "net_income": "Net Income",
    "basic_eps": "Basic EPS",
    "diluted_eps": "Diluted EPS",
    "total_expenses": "Total Expenses",
}

_BALANCE_DISPLAY: dict[str, str] = {
    "total_assets": "Total Assets",
    "current_assets": "Current Assets",
    "cash_and_cash_equivalents": "Cash And Cash Equivalents",
    "accounts_receivable": "Accounts Receivable",
    "inventory": "Inventory",
    "net_ppe": "Net PPE",
    "total_non_current_assets": "Total Non Current Assets",
    "goodwill": "Goodwill",
    "total_liabilities": "Total Liabilities Net Minority Interest",
    "current_liabilities": "Current Liabilities",
    "current_debt": "Current Debt",
    "accounts_payable": "Accounts Payable",
    "long_term_debt": "Long Term Debt",
    "total_debt": "Total Debt",
    "stockholders_equity": "Stockholders Equity",
    "common_stock_equity": "Common Stock Equity",
    "retained_earnings": "Retained Earnings",
    "working_capital": "Working Capital",
    "net_debt": "Net Debt",
}

_CASHFLOW_DISPLAY: dict[str, str] = {
    "operating_cash_flow": "Operating Cash Flow",
    "net_income_from_continuing_ops": "Net Income From Continuing Operations",
    "depreciation_and_amortization": "Depreciation And Amortization",
    "change_in_working_capital": "Change In Working Capital",
    "change_in_receivables": "Change In Receivables",
    "change_in_inventory": "Change In Inventory",
    "change_in_payable": "Change In Payable",
    "investing_cash_flow": "Investing Cash Flow",
    "capital_expenditure": "Capital Expenditure",
    "capital_expenditure_reported": "Capital Expenditure Reported",
    "purchase_of_ppe": "Purchase Of PPE",
    "sale_of_ppe": "Sale Of PPE",
    "purchase_of_investment": "Purchase Of Investment",
    "sale_of_investment": "Sale Of Investment",
    "financing_cash_flow": "Financing Cash Flow",
    "net_issuance_payments_of_debt": "Net Issuance Payments Of Debt",
    "long_term_debt_issuance": "Long Term Debt Issuance",
    "long_term_debt_payments": "Long Term Debt Payments",
    "common_stock_issuance": "Common Stock Issuance",
    "cash_dividends_paid": "Cash Dividends Paid",
    "free_cash_flow": "Free Cash Flow",
    "changes_in_cash": "Changes In Cash",
    "end_cash_position": "End Cash Position",
}

# Maps display name → (table, column) — used by get_metric_trend()
_METRIC_REGISTRY: dict[str, tuple[str, str]] = (
    {display: ("f_income_statements", col) for col, display in _INCOME_DISPLAY.items()}
    | {display: ("f_balance_sheets", col) for col, display in _BALANCE_DISPLAY.items()}
    | {display: ("f_cash_flows", col) for col, display in _CASHFLOW_DISPLAY.items()}
)
# Also register snake_case keys for convenience
_METRIC_REGISTRY.update({col: ("f_income_statements", col) for col in _INCOME_DISPLAY})
_METRIC_REGISTRY.update({col: ("f_balance_sheets", col) for col in _BALANCE_DISPLAY})
_METRIC_REGISTRY.update({col: ("f_cash_flows", col) for col in _CASHFLOW_DISPLAY})


def _row_to_dict(row, display_map: dict[str, str]) -> dict:
    """Convert a SQLAlchemy row to a {display_label: value} data dict."""
    return {
        display: float(val) if val is not None else None
        for col, display in display_map.items()
        if (val := getattr(row, col, None)) is not None
    }


class FinancialStatementsRepo:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    # ── income statements ────────────────────────────────────────────────

    async def get_income_statements(
        self,
        in_equity_id: UUID,
        statement_type: str,  # 'annual' | 'quarterly'
        limit_periods: int = 12,
    ) -> list[dict]:
        """
        Return JSONB rows for one equity, one statement type, newest-first.

        Each row: {"period": date, "data": {"Net Income": 179181000000, ...}}

        Uses ix_income_equity_type_period for a fast index scan.
        Returns rows in {period, data} format with display-name keys.
        """
        result = await self._s.execute(
            text(
                """
                SELECT period,
                       total_revenue, cost_of_revenue, gross_profit, operating_expense,
                       operating_income, ebitda, interest_expense, tax_provision,
                       pretax_income, net_income, basic_eps, diluted_eps, total_expenses
                FROM   f_income_statements
                WHERE  in_equity_id   = :eid
                  AND  statement_type = :stype
                ORDER  BY period DESC
                LIMIT  :lim
                """
            ),
            {"eid": in_equity_id, "stype": statement_type, "lim": limit_periods},
        )
        return [{"period": r.period, "data": _row_to_dict(r, _INCOME_DISPLAY)} for r in result]

    # ── balance sheets ────────────────────────────────────────────────────

    async def get_balance_sheets(
        self,
        in_equity_id: UUID,
        statement_type: str,  # 'annual' | 'quarterly'
        limit_periods: int = 12,
    ) -> list[dict]:
        """Return balance sheet rows newest-first. Uses ix_balance_equity_type_period."""
        result = await self._s.execute(
            text(
                """
                SELECT period,
                       total_assets, current_assets, cash_and_cash_equivalents,
                       accounts_receivable, inventory, net_ppe,
                       total_non_current_assets, goodwill, total_liabilities,
                       current_liabilities, current_debt, accounts_payable,
                       long_term_debt, total_debt, stockholders_equity,
                       common_stock_equity, retained_earnings, working_capital, net_debt
                FROM   f_balance_sheets
                WHERE  in_equity_id   = :eid
                  AND  statement_type = :stype
                ORDER  BY period DESC
                LIMIT  :lim
                """
            ),
            {"eid": in_equity_id, "stype": statement_type, "lim": limit_periods},
        )
        return [{"period": r.period, "data": _row_to_dict(r, _BALANCE_DISPLAY)} for r in result]

    # ── cash flows ────────────────────────────────────────────────────────

    async def get_cash_flows(
        self,
        in_equity_id: UUID,
        statement_type: str,  # 'annual' | 'quarterly'
        limit_periods: int = 12,
    ) -> list[dict]:
        """Return cash flow rows newest-first. Uses ix_cashflow_equity_type_period."""
        result = await self._s.execute(
            text(
                """
                SELECT period,
                       operating_cash_flow, net_income_from_continuing_ops,
                       depreciation_and_amortization, change_in_working_capital,
                       change_in_receivables, change_in_inventory, change_in_payable,
                       investing_cash_flow, capital_expenditure, capital_expenditure_reported,
                       purchase_of_ppe, sale_of_ppe, purchase_of_investment, sale_of_investment,
                       financing_cash_flow, net_issuance_payments_of_debt,
                       long_term_debt_issuance, long_term_debt_payments,
                       common_stock_issuance, cash_dividends_paid,
                       free_cash_flow, changes_in_cash, end_cash_position
                FROM   f_cash_flows
                WHERE  in_equity_id   = :eid
                  AND  statement_type = :stype
                ORDER  BY period DESC
                LIMIT  :lim
                """
            ),
            {"eid": in_equity_id, "stype": statement_type, "lim": limit_periods},
        )
        return [{"period": r.period, "data": _row_to_dict(r, _CASHFLOW_DISPLAY)} for r in result]

    # ── cross-stock metric trend ──────────────────────────────────────────

    async def get_metric_trend(
        self,
        symbols_ns: list[str],
        metric: str,
        statement_type: str,
        since: date,
    ) -> list[dict]:
        """
        Cross-stock single-metric trend across multiple stocks.

        `metric` may be a display name ("Net Income") or a snake_case column
        name ("net_income") — both are resolved via _METRIC_REGISTRY.
        Uses the partial B-tree index on the relevant column for annual queries.
        """
        resolved = _METRIC_REGISTRY.get(metric)
        if resolved is None:
            return []

        table, col = resolved
        symbols = [s.upper().strip().removesuffix(".NS") for s in symbols_ns]

        result = await self._s.execute(
            text(
                f"""
                SELECT ie.symbol || '.NS' AS symbol_ns,
                       fs.period,
                       fs.{col}           AS value
                FROM   {table} AS fs
                JOIN   in_equities AS ie ON ie.id = fs.in_equity_id
                WHERE  fs.statement_type = :stype
                  AND  fs.period        >= :since
                  AND  ie.symbol         = ANY(:syms)
                  AND  fs.{col}         IS NOT NULL
                ORDER  BY symbol_ns, fs.period
                """
            ),
            {"stype": statement_type, "since": since, "syms": symbols},
        )
        return [
            {"symbol_ns": r.symbol_ns, "period": r.period, "value": float(r.value)} for r in result
        ]
