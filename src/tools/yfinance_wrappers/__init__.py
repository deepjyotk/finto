"""Simple YFinance wrapper functions for use in generated Python code.

These functions mirror the langchain tools but are plain Python functions
that can be called directly in generated code without the langchain tool wrapper.

Function Categories
-------------------
Each function is tagged with one of three categories:

  PORTFOLIO  – best suited for portfolio analysis (user's holdings context)
  SCREENER   – best suited for market-wide stock screening
  BOTH       – applicable in both portfolio and screener contexts

PORTFOLIO:
  get_dividends, get_capital_gains

SCREENER:
  get_earnings_estimate, get_revenue_estimate, get_earnings_history,
  get_eps_trend, get_eps_revisions, get_growth_estimates,
  get_major_holders, get_institutional_holders, get_mutualfund_holders,
  get_insider_purchases, get_insider_transactions

BOTH:
  get_balance_sheet, get_income_statement, get_cash_flow,
  get_financial_metric, get_ticker_price, get_last_close_price, get_ticker_info

SHAPE NOTE (critical for generated code):
  Estimate / ownership / insider helpers return yfinance as_dict=True payloads:
  COLUMN-ORIENTED dicts (column name -> {row_key: value}), NOT a list of row dicts.
  Always convert with pd.DataFrame(payload) before iterating rows. Never treat top-level
  keys (avg, Holder, Shares, …) as periods or holder names.
"""

import os
from typing import List, Optional

import pandas as pd
import yfinance as yf

from src.tools.common_utils import normalize_symbol

# ── DB helper ─────────────────────────────────────────────────────────────────


def _get_db_url() -> str | None:
    """Return a psycopg-compatible sync DB URL, or None if DATABASE_URL is not set."""
    raw = os.environ.get("DATABASE_URL", "")
    if not raw:
        return None
    return raw.replace("postgresql+asyncpg://", "postgresql://")


# Freq string → statement_type value stored in DB
_FREQ_TO_STMT: dict[str, str] = {"yearly": "annual", "quarterly": "quarterly"}

# Display name → CamelCase (tool output uses CamelCase for LLM compat)
_INCOME_DB_COLS = [
    ("total_revenue", "TotalRevenue"),
    ("cost_of_revenue", "CostOfRevenue"),
    ("gross_profit", "GrossProfit"),
    ("operating_expense", "OperatingExpense"),
    ("operating_income", "OperatingIncome"),
    ("ebitda", "EBITDA"),
    ("interest_expense", "InterestExpense"),
    ("tax_provision", "TaxProvision"),
    ("pretax_income", "PretaxIncome"),
    ("net_income", "NetIncome"),
    ("basic_eps", "BasicEPS"),
    ("diluted_eps", "DilutedEPS"),
    ("total_expenses", "TotalExpenses"),
]

_BALANCE_DB_COLS = [
    ("total_assets", "TotalAssets"),
    ("current_assets", "CurrentAssets"),
    ("cash_and_cash_equivalents", "CashAndCashEquivalents"),
    ("accounts_receivable", "AccountsReceivable"),
    ("inventory", "Inventory"),
    ("net_ppe", "NetPPE"),
    ("total_non_current_assets", "TotalNonCurrentAssets"),
    ("goodwill", "Goodwill"),
    ("total_liabilities", "TotalLiabilitiesNetMinorityInterest"),
    ("current_liabilities", "CurrentLiabilities"),
    ("current_debt", "CurrentDebt"),
    ("accounts_payable", "AccountsPayable"),
    ("long_term_debt", "LongTermDebt"),
    ("total_debt", "TotalDebt"),
    ("stockholders_equity", "StockholdersEquity"),
    ("common_stock_equity", "CommonStockEquity"),
    ("retained_earnings", "RetainedEarnings"),
    ("working_capital", "WorkingCapital"),
    ("net_debt", "NetDebt"),
]

_CASHFLOW_DB_COLS = [
    ("operating_cash_flow", "OperatingCashFlow"),
    ("net_income_from_continuing_ops", "NetIncomeFromContinuingOperations"),
    ("depreciation_and_amortization", "DepreciationAndAmortization"),
    ("change_in_working_capital", "ChangeInWorkingCapital"),
    ("change_in_receivables", "ChangeInReceivables"),
    ("change_in_inventory", "ChangeInInventory"),
    ("change_in_payable", "ChangeInPayable"),
    ("investing_cash_flow", "InvestingCashFlow"),
    ("capital_expenditure", "CapitalExpenditure"),
    ("capital_expenditure_reported", "CapitalExpenditureReported"),
    ("purchase_of_ppe", "PurchaseOfPPE"),
    ("sale_of_ppe", "SaleOfPPE"),
    ("purchase_of_investment", "PurchaseOfInvestment"),
    ("sale_of_investment", "SaleOfInvestment"),
    ("financing_cash_flow", "FinancingCashFlow"),
    ("net_issuance_payments_of_debt", "NetIssuancePaymentsOfDebt"),
    ("long_term_debt_issuance", "LongTermDebtIssuance"),
    ("long_term_debt_payments", "LongTermDebtPayments"),
    ("common_stock_issuance", "CommonStockIssuance"),
    ("cash_dividends_paid", "CashDividendsPaid"),
    ("free_cash_flow", "FreeCashFlow"),
    ("changes_in_cash", "ChangesInCash"),
    ("end_cash_position", "EndCashPosition"),
]

# Metric name (snake_case OR CamelCase) → (table, snake_col, camel_name)
# Used by get_financial_metric() for validated column routing.
_METRIC_LOOKUP: dict[str, tuple[str, str, str]] = {}
for _snake, _camel in _INCOME_DB_COLS:
    _METRIC_LOOKUP[_snake] = _METRIC_LOOKUP[_camel] = ("f_income_statements", _snake, _camel)
for _snake, _camel in _BALANCE_DB_COLS:
    _METRIC_LOOKUP[_snake] = _METRIC_LOOKUP[_camel] = ("f_balance_sheets", _snake, _camel)
for _snake, _camel in _CASHFLOW_DB_COLS:
    _METRIC_LOOKUP[_snake] = _METRIC_LOOKUP[_camel] = ("f_cash_flows", _snake, _camel)

# Per-statement alias dicts: snake_case OR CamelCase → CamelCase output key
# Used by get_balance_sheet / get_income_statement / get_cash_flow metrics param.
_INCOME_ALIASES: dict[str, str] = {
    **{camel: camel for _, camel in _INCOME_DB_COLS},
    **{snake: camel for snake, camel in _INCOME_DB_COLS},
}
_BALANCE_ALIASES: dict[str, str] = {
    **{camel: camel for _, camel in _BALANCE_DB_COLS},
    **{snake: camel for snake, camel in _BALANCE_DB_COLS},
}
_CASHFLOW_ALIASES: dict[str, str] = {
    **{camel: camel for _, camel in _CASHFLOW_DB_COLS},
    **{snake: camel for snake, camel in _CASHFLOW_DB_COLS},
}


def _resolve_metric_filter(requested: list[str], aliases: dict[str, str]) -> set[str]:
    """Resolve snake_case or CamelCase metric names to a set of CamelCase keys."""
    return {aliases[m] for m in requested if m in aliases}


# ── Category sets (for runtime lookup by node utils) ──────────────────────────

PORTFOLIO_FUNCTIONS: frozenset[str] = frozenset(
    {
        "get_dividends",
        "get_capital_gains",
    }
)

SCREENER_FUNCTIONS: frozenset[str] = frozenset(
    {
        "get_earnings_estimate",
        "get_revenue_estimate",
        "get_earnings_history",
        "get_eps_trend",
        "get_eps_revisions",
        "get_growth_estimates",
        "get_major_holders",
        "get_institutional_holders",
        "get_mutualfund_holders",
        "get_insider_purchases",
        "get_insider_transactions",
    }
)

BOTH_FUNCTIONS: frozenset[str] = frozenset(
    {
        "get_balance_sheet",
        "get_income_statement",
        "get_cash_flow",
        "get_financial_metric",
        "get_ticker_price",
        "get_last_close_price",
        "get_ticker_info",
    }
)


def get_balance_sheet(
    symbol_names: "str | list[str]",
    freq: str = "yearly",
    metrics: "list[str] | None" = None,
    pretty: bool = False,
) -> dict:
    """Fetch balance sheet for one or more stocks — DB-first, yfinance fallback.

    Args:
        symbol_names: Single symbol string OR list of symbols.
                      e.g. "RELIANCE"  or  ["RELIANCE", "TCS", "INFY"]
        freq:         "yearly" (default) or "quarterly"
        metrics:      Optional list of fields to include (snake_case or CamelCase).
                      If omitted, all fields are returned.
                      e.g. ["total_assets", "TotalDebt", "net_debt"]
        pretty:       Ignored when data is served from DB (kept for API compat)

    Returns:
        Single symbol:    {"symbol": "RELIANCE", "balance_sheet": {"YYYY-MM-DD": {"TotalAssets": ...}}}
        Multiple symbols: {"balance_sheet": {"RELIANCE": {"YYYY-MM-DD": {...}}, "TCS": {...}}}
    """
    if not symbol_names:
        raise ValueError("symbol_names is required.")

    multi = isinstance(symbol_names, list)
    symbols_list = [s.strip().upper() for s in (symbol_names if multi else [symbol_names])]
    stmt_type = _FREQ_TO_STMT.get(freq, "annual")
    metric_filter = _resolve_metric_filter(metrics, _BALANCE_ALIASES) if metrics else None

    db_url = _get_db_url()
    if db_url:
        try:
            import psycopg

            with psycopg.connect(db_url) as conn:
                rows = conn.execute(
                    """
                    SELECT ie.symbol, bs.period,
                           total_assets, current_assets, cash_and_cash_equivalents,
                           accounts_receivable, inventory, net_ppe,
                           total_non_current_assets, goodwill, total_liabilities,
                           current_liabilities, current_debt, accounts_payable,
                           long_term_debt, total_debt, stockholders_equity,
                           common_stock_equity, retained_earnings, working_capital, net_debt
                    FROM   f_balance_sheets bs
                    JOIN   in_equities ie ON ie.id = bs.in_equity_id
                    WHERE  ie.symbol = ANY(%s) AND bs.statement_type = %s
                    ORDER  BY ie.symbol, bs.period DESC
                    """,
                    (symbols_list, stmt_type),
                ).fetchall()
            if rows:
                by_symbol: dict[str, dict] = {}
                counts: dict[str, int] = {}
                for row in rows:
                    sym = row[0]
                    if counts.get(sym, 0) >= 10:
                        continue
                    period_str = str(row[1])
                    data = {
                        camel: float(row[i + 2])
                        for i, (_, camel) in enumerate(_BALANCE_DB_COLS)
                        if row[i + 2] is not None
                    }
                    if metric_filter:
                        data = {k: v for k, v in data.items() if k in metric_filter}
                    by_symbol.setdefault(sym, {})[period_str] = data
                    counts[sym] = counts.get(sym, 0) + 1
                if multi:
                    return {"balance_sheet": by_symbol}
                return {
                    "symbol": symbols_list[0],
                    "balance_sheet": by_symbol.get(symbols_list[0], {}),
                }
        except Exception as e:
            print(f"[get_balance_sheet] DB fetch failed ({e}), falling back to yfinance")

    # yfinance fallback
    important_fields = {camel for _, camel in _BALANCE_DB_COLS}
    if metric_filter:
        important_fields &= metric_filter

    def _yf_fetch(sym: str) -> dict:
        try:
            data = yf.Ticker(normalize_symbol(sym)).get_balance_sheet(
                as_dict=True, pretty=pretty, freq=freq
            )
            if not isinstance(data, dict):
                return {}
            return {
                str(dk): {f: v for f, v in flds.items() if f in important_fields}
                for dk, flds in data.items()
            }
        except Exception as e:
            print(f"ERROR: Failed to fetch balance sheet for {sym} - {e}")
            return {}

    if multi:
        return {"balance_sheet": {sym: _yf_fetch(sym) for sym in symbols_list}}
    return {"symbol": symbols_list[0], "balance_sheet": _yf_fetch(symbols_list[0])}


def get_income_statement(
    symbol_names: "str | list[str]",
    freq: str = "yearly",
    metrics: "list[str] | None" = None,
    pretty: bool = False,
) -> dict:
    """Fetch income statement for one or more stocks — DB-first, yfinance fallback.

    Args:
        symbol_names: Single symbol string OR list of symbols.
                      e.g. "RELIANCE"  or  ["RELIANCE", "TCS"]
        freq:         "yearly" (default) or "quarterly"
        metrics:      Optional list of fields to include (snake_case or CamelCase).
                      e.g. ["total_revenue", "NetIncome", "ebitda"]
        pretty:       Ignored when data is served from DB (kept for API compat)

    Returns:
        Single symbol:    {"symbol": "RELIANCE", "income_statement": {"YYYY-MM-DD": {"TotalRevenue": ...}}}
        Multiple symbols: {"income_statement": {"RELIANCE": {"YYYY-MM-DD": {...}}, "TCS": {...}}}
    """
    if not symbol_names:
        raise ValueError("symbol_names is required.")

    multi = isinstance(symbol_names, list)
    symbols_list = [s.strip().upper() for s in (symbol_names if multi else [symbol_names])]
    stmt_type = _FREQ_TO_STMT.get(freq, "annual")
    metric_filter = _resolve_metric_filter(metrics, _INCOME_ALIASES) if metrics else None

    db_url = _get_db_url()
    if db_url:
        try:
            import psycopg

            with psycopg.connect(db_url) as conn:
                rows = conn.execute(
                    """
                    SELECT ie.symbol, fs.period,
                           total_revenue, cost_of_revenue, gross_profit, operating_expense,
                           operating_income, ebitda, interest_expense, tax_provision,
                           pretax_income, net_income, basic_eps, diluted_eps, total_expenses
                    FROM   f_income_statements fs
                    JOIN   in_equities ie ON ie.id = fs.in_equity_id
                    WHERE  ie.symbol = ANY(%s) AND fs.statement_type = %s
                    ORDER  BY ie.symbol, fs.period DESC
                    """,
                    (symbols_list, stmt_type),
                ).fetchall()
            if rows:
                by_symbol: dict[str, dict] = {}
                counts: dict[str, int] = {}
                for row in rows:
                    sym = row[0]
                    if counts.get(sym, 0) >= 10:
                        continue
                    period_str = str(row[1])
                    data = {
                        camel: float(row[i + 2])
                        for i, (_, camel) in enumerate(_INCOME_DB_COLS)
                        if row[i + 2] is not None
                    }
                    if metric_filter:
                        data = {k: v for k, v in data.items() if k in metric_filter}
                    by_symbol.setdefault(sym, {})[period_str] = data
                    counts[sym] = counts.get(sym, 0) + 1
                if multi:
                    return {"income_statement": by_symbol}
                return {
                    "symbol": symbols_list[0],
                    "income_statement": by_symbol.get(symbols_list[0], {}),
                }
        except Exception as e:
            print(f"[get_income_statement] DB fetch failed ({e}), falling back to yfinance")

    # yfinance fallback
    important_fields = {camel for _, camel in _INCOME_DB_COLS}
    if metric_filter:
        important_fields &= metric_filter

    def _yf_fetch(sym: str) -> dict:
        try:
            data = yf.Ticker(normalize_symbol(sym)).get_income_stmt(
                as_dict=True, pretty=pretty, freq=freq
            )
            if not isinstance(data, dict):
                return {}
            return {
                str(dk): {f: v for f, v in flds.items() if f in important_fields}
                for dk, flds in data.items()
            }
        except Exception as e:
            print(f"ERROR: Failed to fetch income statement for {sym} - {e}")
            return {}

    if multi:
        return {"income_statement": {sym: _yf_fetch(sym) for sym in symbols_list}}
    return {"symbol": symbols_list[0], "income_statement": _yf_fetch(symbols_list[0])}


def get_cash_flow(
    symbol_names: "str | list[str]",
    freq: str = "yearly",
    metrics: "list[str] | None" = None,
    pretty: bool = False,
) -> dict:
    """Fetch cash flow statement for one or more stocks — DB-first, yfinance fallback.

    Args:
        symbol_names: Single symbol string OR list of symbols.
                      e.g. "RELIANCE"  or  ["RELIANCE", "TCS"]
        freq:         "yearly" (default) or "quarterly"
        metrics:      Optional list of fields to include (snake_case or CamelCase).
                      e.g. ["free_cash_flow", "OperatingCashFlow", "capital_expenditure"]
        pretty:       Ignored when data is served from DB (kept for API compat)

    Returns:
        Single symbol:    {"symbol": "RELIANCE", "cash_flow": {"YYYY-MM-DD": {"OperatingCashFlow": ...}}}
        Multiple symbols: {"cash_flow": {"RELIANCE": {"YYYY-MM-DD": {...}}, "TCS": {...}}}
    """
    if not symbol_names:
        raise ValueError("symbol_names is required.")

    multi = isinstance(symbol_names, list)
    symbols_list = [s.strip().upper() for s in (symbol_names if multi else [symbol_names])]
    stmt_type = _FREQ_TO_STMT.get(freq, "annual")
    metric_filter = _resolve_metric_filter(metrics, _CASHFLOW_ALIASES) if metrics else None

    db_url = _get_db_url()
    if db_url:
        try:
            import psycopg

            with psycopg.connect(db_url) as conn:
                rows = conn.execute(
                    """
                    SELECT ie.symbol, cf.period,
                           operating_cash_flow, net_income_from_continuing_ops,
                           depreciation_and_amortization, change_in_working_capital,
                           change_in_receivables, change_in_inventory, change_in_payable,
                           investing_cash_flow, capital_expenditure, capital_expenditure_reported,
                           purchase_of_ppe, sale_of_ppe, purchase_of_investment, sale_of_investment,
                           financing_cash_flow, net_issuance_payments_of_debt,
                           long_term_debt_issuance, long_term_debt_payments,
                           common_stock_issuance, cash_dividends_paid,
                           free_cash_flow, changes_in_cash, end_cash_position
                    FROM   f_cash_flows cf
                    JOIN   in_equities ie ON ie.id = cf.in_equity_id
                    WHERE  ie.symbol = ANY(%s) AND cf.statement_type = %s
                    ORDER  BY ie.symbol, cf.period DESC
                    """,
                    (symbols_list, stmt_type),
                ).fetchall()
            if rows:
                by_symbol: dict[str, dict] = {}
                counts: dict[str, int] = {}
                for row in rows:
                    sym = row[0]
                    if counts.get(sym, 0) >= 10:
                        continue
                    period_str = str(row[1])
                    data = {
                        camel: float(row[i + 2])
                        for i, (_, camel) in enumerate(_CASHFLOW_DB_COLS)
                        if row[i + 2] is not None
                    }
                    if metric_filter:
                        data = {k: v for k, v in data.items() if k in metric_filter}
                    by_symbol.setdefault(sym, {})[period_str] = data
                    counts[sym] = counts.get(sym, 0) + 1
                if multi:
                    return {"cash_flow": by_symbol}
                return {"symbol": symbols_list[0], "cash_flow": by_symbol.get(symbols_list[0], {})}
        except Exception as e:
            print(f"[get_cash_flow] DB fetch failed ({e}), falling back to yfinance")

    # yfinance fallback
    important_fields = {camel for _, camel in _CASHFLOW_DB_COLS}
    if metric_filter:
        important_fields &= metric_filter

    def _yf_fetch(sym: str) -> dict:
        try:
            data = yf.Ticker(normalize_symbol(sym)).get_cashflow(
                as_dict=True, pretty=pretty, freq=freq
            )
            if not isinstance(data, dict):
                return {}
            return {
                str(dk): {f: v for f, v in flds.items() if f in important_fields}
                for dk, flds in data.items()
            }
        except Exception as e:
            print(f"ERROR: Failed to fetch cash flow for {sym} - {e}")
            return {}

    if multi:
        return {"cash_flow": {sym: _yf_fetch(sym) for sym in symbols_list}}
    return {"symbol": symbols_list[0], "cash_flow": _yf_fetch(symbols_list[0])}


def get_financial_metric(
    symbol_names: list[str],
    metric: str,
    freq: str = "yearly",
    periods: int = 5,
) -> dict:
    """Fetch a single financial metric for one or more stocks across periods.

    Reads from the typed financial tables (DB-first, no yfinance network call).
    Works across income statements, balance sheets, and cash flows — the table
    is chosen automatically based on the metric name.

    Args:
        symbol_names: One or more stock symbols, e.g. ["RELIANCE", "TCS"]
        metric:       snake_case column name ("net_income", "free_cash_flow") OR
                      CamelCase name ("NetIncome", "FreeCashFlow")
        freq:         "yearly" (default) or "quarterly"
        periods:      Number of most-recent periods to return per symbol (default 5)

    Returns:
        {
          "metric": "NetIncome",
          "freq":   "yearly",
          "data":   {
            "RELIANCE": {"2024-03-31": 179181000000, "2023-03-31": ...},
            "TCS":      {"2024-03-31": ...}
          }
        }

    Known metrics
    -------------
    Income:    total_revenue, cost_of_revenue, gross_profit, operating_expense,
               operating_income, ebitda, interest_expense, tax_provision,
               pretax_income, net_income, basic_eps, diluted_eps, total_expenses
    Balance:   total_assets, current_assets, cash_and_cash_equivalents,
               accounts_receivable, inventory, net_ppe, total_non_current_assets,
               goodwill, total_liabilities, current_liabilities, current_debt,
               accounts_payable, long_term_debt, total_debt, stockholders_equity,
               common_stock_equity, retained_earnings, working_capital, net_debt
    Cash Flow: operating_cash_flow, investing_cash_flow, financing_cash_flow,
               free_cash_flow, capital_expenditure, depreciation_and_amortization,
               change_in_working_capital, net_income_from_continuing_ops,
               changes_in_cash, end_cash_position  (and more)
    """
    resolved = _METRIC_LOOKUP.get(metric)
    if resolved is None:
        known = sorted(_METRIC_LOOKUP.keys())
        return {"error": f"Unknown metric '{metric}'. Known metrics: {known}"}

    table, col, camel = resolved
    stmt_type = _FREQ_TO_STMT.get(freq, "annual")
    symbols = [s.strip().upper() for s in symbol_names]

    db_url = _get_db_url()
    if db_url:
        try:
            import psycopg
            from psycopg import sql as pgsql

            # col and table come from the hardcoded _METRIC_LOOKUP — validated values
            query = pgsql.SQL(
                """
                SELECT ie.symbol, fs.period, fs.{col}
                FROM   {table} fs
                JOIN   in_equities ie ON ie.id = fs.in_equity_id
                WHERE  ie.symbol = ANY(%s)
                  AND  fs.statement_type = %s
                  AND  fs.{col} IS NOT NULL
                ORDER  BY ie.symbol, fs.period DESC
                """
            ).format(col=pgsql.Identifier(col), table=pgsql.Identifier(table))
            with psycopg.connect(db_url) as conn:
                rows = conn.execute(query, (symbols, stmt_type)).fetchall()

            data: dict[str, dict] = {}
            for sym, period, val in rows:
                if sym not in data:
                    data[sym] = {}
                if len(data[sym]) < periods:
                    data[sym][str(period)] = float(val)

            return {"metric": camel, "freq": freq, "data": data}

        except Exception as e:
            print(f"[get_financial_metric] DB fetch failed ({e})")
            return {"metric": camel, "freq": freq, "data": {}, "error": str(e)}

    return {"metric": camel, "freq": freq, "data": {}, "error": "DATABASE_URL not set"}


def get_dividends(symbol_name: str, period: str = "max") -> dict:
    """Fetch dividend payment history.

    Args:
        symbol_name: Stock ticker symbol
        period: Period to fetch (e.g., "1y", "5y", "max")

    Returns:
        {"symbol": t, "dividends": {...}} with clean date format (YYYY-MM-DD)
    """
    try:
        if not symbol_name:
            raise ValueError("Symbol name is required.")
        normalized_symbol = normalize_symbol(symbol_name.strip().upper())
        series = yf.Ticker(normalized_symbol).get_dividends(period=period)
        # Convert Series to dict: {date: value} with clean date format
        if hasattr(series, "to_dict"):
            div_dict = {}
            for k, v in series.to_dict().items():
                try:
                    # Try to format as YYYY-MM-DD
                    date_str = k.strftime("%Y-%m-%d")
                except (AttributeError, TypeError):
                    # Fallback if k is already a string
                    date_str = str(k).split(" ")[0]  # Extract just the date part
                div_dict[date_str] = float(v)
        else:
            div_dict = {}
        return {"symbol": symbol_name, "dividends": div_dict}
    except Exception as e:
        print(f"ERROR: Failed to fetch dividends for symbol: {symbol_name} - {e}")
        return {"symbol": symbol_name, "dividends": {}, "error": str(e)}


def get_capital_gains(symbol_name: str, period: str = "max") -> dict:
    """Fetch capital gains history.

    Args:
        symbol_name: Stock ticker symbol
        period: Period to fetch (e.g., "1y", "5y", "max")

    Returns:
        {"symbol": t, "capital_gains": {...}} with clean date format (YYYY-MM-DD)
    """
    try:
        if not symbol_name:
            print(f"ERROR: Symbol {symbol_name} is empty or None")
            raise ValueError("Symbol name is required.")
        normalized_symbol = normalize_symbol(symbol_name.strip().upper())
        series = yf.Ticker(normalized_symbol).get_capital_gains(period=period)
        # Convert Series to dict: {date: value} with clean date format
        if hasattr(series, "to_dict"):
            cg_dict = {}
            for k, v in series.to_dict().items():
                try:
                    # Try to format as YYYY-MM-DD
                    date_str = k.strftime("%Y-%m-%d")
                except (AttributeError, TypeError):
                    # Fallback if k is already a string
                    date_str = str(k).split(" ")[0]  # Extract just the date part
                cg_dict[date_str] = float(v)
        else:
            cg_dict = {}
        return {"symbol": symbol_name, "capital_gains": cg_dict}
    except Exception as e:
        print(f"ERROR: Failed to fetch capital gains for symbol: {symbol_name} - {e}")
        return {"symbol": symbol_name, "capital_gains": {}, "error": str(e)}


def get_earnings_estimate(symbol_name: str) -> dict:
    """Fetch earnings estimates.

    Args:
        symbol_name: Stock ticker symbol

    Returns:
        {"symbol": t, "earnings_estimate": {...}}. COLUMN-ORIENTED (yfinance as_dict):
        top-level keys are metrics (avg, low, high, yearAgoEps, numberOfAnalysts, growth);
        each value is {period: number} for periods like 0q, +1q, 0y, +1y.
        Do NOT iterate .items() as if keys were periods. Parse with:
        est = pd.DataFrame(result["earnings_estimate"]); then for period, row in est.iterrows():
        use float(row["avg"]), row.get("growth"), etc.
    """
    try:
        if not symbol_name:
            print(f"ERROR: Symbol {symbol_name} is empty or None")
            raise ValueError("Symbol name is required.")
        normalized_symbol = normalize_symbol(symbol_name.strip().upper())
        data = yf.Ticker(normalized_symbol).get_earnings_estimate(as_dict=True)
        return {
            "symbol": symbol_name,
            "earnings_estimate": data if data is not None else {},
        }
    except Exception as e:
        print(f"ERROR: Failed to fetch earnings estimate for symbol: {symbol_name} - {e}")
        return {"symbol": symbol_name, "earnings_estimate": {}, "error": str(e)}


def get_revenue_estimate(symbol_name: str) -> dict:
    """Fetch revenue estimates.

    Args:
        symbol_name: Stock ticker symbol

    Returns:
        {"symbol": t, "revenue_estimate": {...}}. COLUMN-ORIENTED (yfinance as_dict):
        top-level keys are metrics (avg, low, high, numberOfAnalysts, yearAgoRevenue, growth);
        each value is {period: number} for 0q, +1q, 0y, +1y.
        Do NOT iterate .items() as if keys were periods. Parse with:
        rev = pd.DataFrame(result["revenue_estimate"]); then for period, row in rev.iterrows(): ...
    """
    try:
        if not symbol_name:
            print(f"ERROR: Symbol {symbol_name} is empty or None")
            raise ValueError("Symbol name is required.")
        normalized_symbol = normalize_symbol(symbol_name.strip().upper())
        # as_dict=True avoids returning a pandas DataFrame (truth-value ambiguous in callers).
        data = yf.Ticker(normalized_symbol).get_revenue_estimate(as_dict=True)
        return {
            "symbol": symbol_name,
            "revenue_estimate": data if data is not None else {},
        }
    except Exception as e:
        print(f"ERROR: Failed to fetch revenue estimate for symbol: {symbol_name} - {e}")
        return {"symbol": symbol_name, "revenue_estimate": {}, "error": str(e)}


def get_earnings_history(symbol_name: str) -> dict:
    """Fetch earnings history.

    Args:
        symbol_name: Stock ticker symbol

    Returns:
        {"symbol": t, "earnings_history": {...}}. COLUMN-ORIENTED (yfinance as_dict):
        top-level keys are metrics (epsActual, epsEstimate, epsDifference, surprisePercent);
        each value maps date-string -> value. Parse with:
        hist = pd.DataFrame(result["earnings_history"]); iterate hist.iterrows().
    """
    try:
        if not symbol_name:
            print(f"ERROR: Symbol {symbol_name} is empty or None")
            raise ValueError("Symbol name is required.")

        normalized_symbol = normalize_symbol(symbol_name.strip().upper())
        data = yf.Ticker(normalized_symbol).get_earnings_history(as_dict=True)

        # Convert Timestamp keys to strings in nested dictionaries
        if isinstance(data, dict):
            history_dict = {}
            for metric, dates_dict in data.items():
                if isinstance(dates_dict, dict):
                    history_dict[metric] = {str(k): v for k, v in dates_dict.items()}
                else:
                    history_dict[metric] = dates_dict
        else:
            history_dict = data if data is not None else {}

        return {"symbol": symbol_name, "earnings_history": history_dict}
    except Exception as e:
        print(f"ERROR: Failed to fetch earnings history for symbol: {symbol_name} - {e}")
        return {"symbol": symbol_name, "earnings_history": {}, "error": str(e)}


def get_eps_trend(symbol_name: str) -> dict:
    """Fetch EPS trend data.

    Args:
        symbol_name: Stock ticker symbol

    Returns:
        {"symbol": t, "eps_trend": {...}}. COLUMN-ORIENTED (yfinance as_dict):
        top-level keys are lookback columns (current, 7daysAgo, 30daysAgo, 60daysAgo, 90daysAgo);
        values map period -> estimate. Parse with: trend = pd.DataFrame(result["eps_trend"]).
    """
    try:
        if not symbol_name:
            print(f"ERROR: Symbol {symbol_name} is empty or None")
            raise ValueError("Symbol name is required.")
        normalized_symbol = normalize_symbol(symbol_name.strip().upper())
        data = yf.Ticker(normalized_symbol).get_eps_trend(as_dict=True)

        # Convert Timestamp keys to strings if needed
        if isinstance(data, dict):
            eps_dict = {str(k): v for k, v in data.items()}
        else:
            eps_dict = data if data is not None else {}

        return {"symbol": symbol_name, "eps_trend": eps_dict}
    except Exception as e:
        print(f"ERROR: Failed to fetch EPS trend for symbol: {symbol_name} - {e}")
        return {"symbol": symbol_name, "eps_trend": {}, "error": str(e)}


def get_eps_revisions(symbol_name: str) -> dict:
    """Fetch EPS revisions data.

    Args:
        symbol_name: Stock ticker symbol

    Returns:
        {"symbol": t, "eps_revisions": {...}}. COLUMN-ORIENTED (yfinance as_dict):
        top-level keys are revision metrics; values map period -> value.
        Parse with: rev = pd.DataFrame(result["eps_revisions"]); iterate rev.iterrows().
    """
    try:
        if not symbol_name:
            print(f"ERROR: Symbol {symbol_name} is empty or None")
            raise ValueError("Symbol name is required.")
        normalized_symbol = normalize_symbol(symbol_name.strip().upper())
        data = yf.Ticker(normalized_symbol).get_eps_revisions(as_dict=True)
        return {
            "symbol": symbol_name,
            "eps_revisions": data if data is not None else {},
        }
    except Exception as e:
        print(f"ERROR: Failed to fetch EPS revisions for symbol: {symbol_name} - {e}")
        return {"symbol": symbol_name, "eps_revisions": {}, "error": str(e)}


def get_growth_estimates(symbol_name: str) -> dict:
    """Fetch growth estimates.

    Args:
        symbol_name: Stock ticker symbol

    Returns:
        {"symbol": t, "growth_estimates": {...}}. COLUMN-ORIENTED (yfinance as_dict):
        top-level keys are stockTrend and indexTrend; each maps period (0q, +1q, 0y, +1y, LTG) -> float|None.
        Parse with: g = pd.DataFrame(result["growth_estimates"]); then for period, row in g.iterrows():
        use row["stockTrend"], row["indexTrend"] (values are decimals, e.g. 0.0785 = 7.85%).
    """
    try:
        if not symbol_name:
            print(f"ERROR: Symbol {symbol_name} is empty or None")
            raise ValueError("Symbol name is required.")
        normalized_symbol = normalize_symbol(symbol_name.strip().upper())
        data = yf.Ticker(normalized_symbol).get_growth_estimates(as_dict=True)

        # Convert NaN values to None for JSON serialization
        if isinstance(data, dict):
            growth_dict = {}
            for trend_key, trend_data in data.items():
                if isinstance(trend_data, dict):
                    growth_dict[trend_key] = {
                        k: (None if (isinstance(v, float) and v != v) else v)
                        for k, v in trend_data.items()
                    }
                else:
                    growth_dict[trend_key] = trend_data
        else:
            growth_dict = data if data is not None else {}

        return {"symbol": symbol_name, "growth_estimates": growth_dict}
    except Exception as e:
        print(f"ERROR: Failed to fetch growth estimates for symbol: {symbol_name} - {e}")
        return {"symbol": symbol_name, "growth_estimates": {}, "error": str(e)}


def get_major_holders(symbol_name: str) -> dict:
    """Fetch major holders information.

    Args:
        symbol_name: Stock ticker symbol

    Returns:
        {"symbol": t, "major_holders": {...}}. COLUMN-ORIENTED (yfinance as_dict):
        typically {"Value": {"insidersPercentHeld": ..., "institutionsPercentHeld": ...,
        "institutionsFloatPercentHeld": ..., "institutionsCount": ...}}.
        Read via result["major_holders"].get("Value", {}) or pd.DataFrame(result["major_holders"]).
    """
    try:
        if not symbol_name:
            print(f"ERROR: Symbol {symbol_name} is empty or None")
            raise ValueError("Symbol name is required.")
        normalized_symbol = normalize_symbol(symbol_name.strip().upper())
        data = yf.Ticker(normalized_symbol).get_major_holders(as_dict=True)
        return {
            "symbol": symbol_name,
            "major_holders": data if data is not None else {},
        }
    except Exception as e:
        print(f"ERROR: Failed to fetch major holders for symbol: {symbol_name} - {e}")
        return {"symbol": symbol_name, "major_holders": {}, "error": str(e)}


def get_institutional_holders(symbol_name: str) -> dict:
    """Fetch institutional holders information.

    Args:
        symbol_name: Stock ticker symbol

    Returns:
        {"symbol": t, "institutional_holders": {...}}. COLUMN-ORIENTED (yfinance as_dict):
        top-level keys are columns (Date Reported, Holder, pctHeld, Shares, Value, pctChange);
        each value is {row_index: cell}. Do NOT iterate .items() treating keys as holder names.
        Parse with: holders = pd.DataFrame(result["institutional_holders"]);
        then for _, row in holders.iterrows(): use row["Holder"], row["Shares"], row["Value"].
    """
    try:
        if not symbol_name:
            print(f"ERROR: Symbol {symbol_name} is empty or None")
            raise ValueError("Symbol name is required.")
        normalized_symbol = normalize_symbol(symbol_name.strip().upper())
        data = yf.Ticker(normalized_symbol).get_institutional_holders(as_dict=True)
        return {
            "symbol": symbol_name,
            "institutional_holders": data if data is not None else {},
        }
    except Exception as e:
        print(f"ERROR: Failed to fetch institutional holders for symbol: {symbol_name} - {e}")
        return {"symbol": symbol_name, "institutional_holders": {}, "error": str(e)}


def get_mutualfund_holders(symbol_name: str) -> dict:
    """Fetch mutual fund holders information.

    Args:
        symbol_name: Stock ticker symbol

    Returns:
        {"symbol": t, "mutualfund_holders": {...}}. COLUMN-ORIENTED (yfinance as_dict):
        top-level keys are columns (Holder, Shares, Value, …); values are {row_index: cell}.
        Parse with: mf = pd.DataFrame(result["mutualfund_holders"]); iterate mf.iterrows().
    """
    try:
        if not symbol_name:
            print(f"ERROR: Symbol {symbol_name} is empty or None")
            raise ValueError("Symbol name is required.")
        normalized_symbol = normalize_symbol(symbol_name.strip().upper())
        data = yf.Ticker(normalized_symbol).get_mutualfund_holders(as_dict=True)
        return {
            "symbol": symbol_name,
            "mutualfund_holders": data if data is not None else {},
        }
    except Exception as e:
        print(f"ERROR: Failed to fetch mutual fund holders for symbol: {symbol_name} - {e}")
        return {"symbol": symbol_name, "mutualfund_holders": {}, "error": str(e)}


def get_insider_purchases(symbol_name: str) -> dict:
    """Fetch insider purchase transactions.

    Args:
        symbol_name: Stock ticker symbol

    Returns:
        {"symbol": t, "insider_purchases": {...}}. COLUMN-ORIENTED (yfinance as_dict):
        top-level keys are table columns; values are {row_index: cell}.
        Parse with: purchases = pd.DataFrame(result["insider_purchases"]); iterate purchases.iterrows().
    """
    try:
        if not symbol_name:
            print(f"ERROR: Symbol {symbol_name} is empty or None")
            raise ValueError("Symbol name is required.")
        normalized_symbol = normalize_symbol(symbol_name.strip().upper())
        data = yf.Ticker(normalized_symbol).get_insider_purchases(as_dict=True)
        return {
            "symbol": symbol_name,
            "insider_purchases": data if data is not None else {},
        }
    except Exception as e:
        print(f"ERROR: Failed to fetch insider purchases for symbol: {symbol_name} - {e}")
        return {"symbol": symbol_name, "insider_purchases": {}, "error": str(e)}


def get_insider_transactions(symbol_name: str) -> dict:
    """Fetch all insider transactions.

    Args:
        symbol_name: Stock ticker symbol

    Returns:
        {"symbol": t, "insider_transactions": {...}}. COLUMN-ORIENTED (yfinance as_dict):
        top-level keys are columns (Shares, Value, Insider, Position, Transaction, Start Date, Ownership, …);
        each value is {row_index: cell}. Do NOT treat the dict as one transaction or read Name/Title/Date keys.
        Parse with: txs = pd.DataFrame(result["insider_transactions"]);
        then for _, row in txs.head(5).iterrows(): use row["Insider"], row["Position"],
        row["Transaction"], row["Start Date"], row["Shares"], row.get("Value").
    """
    try:
        if not symbol_name:
            print(f"ERROR: Symbol {symbol_name} is empty or None")
            raise ValueError("Symbol name is required.")
        normalized_symbol = normalize_symbol(symbol_name.strip().upper())
        data = yf.Ticker(normalized_symbol).get_insider_transactions(as_dict=True)
        return {
            "symbol": symbol_name,
            "insider_transactions": data if data is not None else {},
        }
    except Exception as e:
        print(f"ERROR: Failed to fetch insider transactions for symbol: {symbol_name} - {e}")
        return {"symbol": symbol_name, "insider_transactions": {}, "error": str(e)}


def get_ticker_price(
    symbol_name: str,
    period: str = "1d",
    interval: str = "1d",
    adjust_mode: str = "auto",
    prepost: bool = False,
    repair: bool = False,
    timeout: Optional[float] = 10.0,
) -> dict:
    """Fetch historical price data for a ticker.

    Args:
        symbol_name: Stock ticker symbol (e.g., "RELIANCE", "AAPL")
        period: Period to fetch (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max) (default: 1d)
        interval: Data interval (1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h, 1d, 5d, 1wk, 1mo, 3mo) (default: 1d)
        adjust_mode: "auto", "back", or "none" for price adjustment (default: auto)
        prepost: Include pre/post market data (default: False)
        repair: Attempt to fix data errors (default: False)
        timeout: Request timeout in seconds (default: 10.0)

    Returns:
        {"symbol": symbol_name, "prices": {...}, "period": period, "interval": interval}
    """

    if not symbol_name:
        print(f"ERROR: Symbol {symbol_name} is empty or None")
        raise ValueError("Symbol name is required.")
    normalized_symbol = normalize_symbol(symbol_name.strip().upper())
    # Map adjust_mode to yfinance parameters
    auto_adjust = adjust_mode == "auto"
    back_adjust = adjust_mode == "back"

    try:
        hist = yf.Ticker(normalized_symbol).history(
            period=period,
            interval=interval,
            auto_adjust=auto_adjust,
            back_adjust=back_adjust,
            prepost=prepost,
            repair=repair,
            timeout=timeout,
        )

        if hist.empty:
            return {"symbol": symbol_name, "prices": {}, "message": "No data available"}

        # Convert to dict mapping date -> close price
        price_dict = {}
        for idx, row in hist.iterrows():
            # idx is the date index, convert to string
            try:
                date_str = idx.strftime("%Y-%m-%d")  # type: ignore
            except AttributeError:
                date_str = str(idx)
            price_dict[date_str] = float(row["Close"])

        return {
            "symbol": symbol_name,
            "prices": price_dict,
            "period": period,
            "interval": interval,
        }
    except Exception as e:
        print(f"ERROR: Failed to fetch ticker price for symbol: {symbol_name} - {e}")
        return {"symbol": symbol_name, "prices": {}, "message": str(e)}


def get_last_close_price(symbol_name: str) -> dict:
    """Fetch the most recent close price for a ticker.

    Args:
        symbol_name: Stock ticker symbol (e.g., "AAPL", "RELIANCE")

    Returns:
        {"symbol": symbol_name, "last_close_price": last_close_price, "date": date}
    """
    if not symbol_name:
        print(f"ERROR: Symbol {symbol_name} is empty or None")
        raise ValueError("Symbol name is required.")

    normalized_symbol = normalize_symbol(symbol_name.strip().upper())
    try:
        ticker = yf.Ticker(normalized_symbol)
        # Get last 5 days to ensure we have data
        hist = ticker.history(period="5d")

        if hist.empty:
            return {
                "symbol": symbol_name,
                "last_close_price": None,
                "date": None,
                "error": "No price data available",
            }

        # Get the last row
        last_date = hist.index[-1]
        last_close = float(hist["Close"].iloc[-1])
        try:
            date_str = last_date.strftime("%Y-%m-%d")  # type: ignore
        except AttributeError:
            date_str = str(last_date)

        return {"symbol": symbol_name, "last_close_price": last_close, "date": date_str}
    except Exception as e:
        print(f"ERROR: Failed to fetch last close price for symbol: {symbol_name} - {e}")
        return {
            "symbol": symbol_name,
            "last_close_price": None,
            "date": None,
            "error": str(e),
        }


def get_last_close_prices_batch(symbol_names: List[str], period: str = "5d") -> dict:
    """Batch-fetch last close prices for many symbols in minimal Yahoo Finance round-trips.

    yfinance supports multi-ticker download: one ``yf.download`` call retrieves OHLC for all
    symbols (``threads=True`` uses parallel HTTP). Prefer this for **whole-portfolio** current
    price tasks instead of calling ``get_last_close_price`` in a loop — sequential per-ticker
    requests often trigger empty responses or throttling from Yahoo.

    Args:
        symbol_names: Symbols as stored in the portfolio (e.g. ``TCS``, ``RELIANCE.NS``).
        period: History window passed to yfinance (default ``5d`` for recent sessions).

    Returns:
        {
          "results": [{"symbol": str, "last_close_price": float | None, "date": str | None,
                       "error": str | None}],
          "ok_count": int,
          "fail_count": int,
          "failed_symbols": [str],
          "note": str,
        }
    """
    cleaned: List[str] = [str(s).strip() for s in symbol_names if s is not None and str(s).strip()]
    empty_out = {
        "results": [],
        "ok_count": 0,
        "fail_count": 0,
        "failed_symbols": [],
        "note": "No symbols provided.",
    }
    if not cleaned:
        return empty_out

    uniq_norm: List[str] = []
    seen: set[str] = set()
    raw_for_norm: dict[str, str] = {}
    for raw in cleaned:
        norm = normalize_symbol(raw.upper())
        raw_for_norm[norm] = raw
        if norm not in seen:
            seen.add(norm)
            uniq_norm.append(norm)

    note_extra = ""
    try:
        data = yf.download(
            uniq_norm,
            period=period,
            interval="1d",
            group_by="ticker",
            auto_adjust=False,
            threads=True,
            progress=False,
            prepost=False,
        )
    except Exception as e:
        return {
            "results": [
                {
                    "symbol": raw_for_norm.get(n, n),
                    "last_close_price": None,
                    "date": None,
                    "error": str(e),
                }
                for n in uniq_norm
            ],
            "ok_count": 0,
            "fail_count": len(uniq_norm),
            "failed_symbols": [raw_for_norm.get(n, n) for n in uniq_norm],
            "note": f"Batch download raised an exception: {e}",
        }

    if data is None or (hasattr(data, "empty") and data.empty):
        return {
            "results": [
                {
                    "symbol": raw_for_norm.get(n, n),
                    "last_close_price": None,
                    "date": None,
                    "error": "Empty batch response",
                }
                for n in uniq_norm
            ],
            "ok_count": 0,
            "fail_count": len(uniq_norm),
            "failed_symbols": [raw_for_norm.get(n, n) for n in uniq_norm],
            "note": "Yahoo returned no rows for the batch price request.",
        }

    def _last_close_for_ticker(
        norm_key: str,
    ) -> tuple[Optional[float], Optional[str], Optional[str]]:
        try:
            s = None
            if isinstance(data.columns, pd.MultiIndex):
                close_key = (norm_key, "Close")
                if close_key in data.columns:
                    s = data[close_key].dropna()
                else:
                    for lv0 in data.columns.get_level_values(0).unique():
                        cand = (lv0, "Close")
                        if cand in data.columns and str(lv0).upper() == norm_key.upper():
                            s = data[cand].dropna()
                            break
                    if s is None:
                        return None, None, "Close column missing in batch frame"
            else:
                if "Close" in data.columns:
                    s = data["Close"].dropna()
                else:
                    return None, None, "Close column missing (single-ticker frame)"

            if s is None or s.empty:
                return None, None, "No close data"
            last_date = s.index[-1]
            val = float(s.iloc[-1])
            try:
                date_str = last_date.strftime("%Y-%m-%d")  # type: ignore[attr-defined]
            except AttributeError:
                date_str = str(last_date)
            return val, date_str, None
        except Exception as ex:
            return None, None, str(ex)

    close_by_norm: dict[str, tuple[Optional[float], Optional[str], Optional[str]]] = {}
    for n in uniq_norm:
        close_by_norm[n] = _last_close_for_ticker(n)

    results: List[dict] = []
    ok_count = 0
    fail_count = 0
    failed_symbols: List[str] = []

    for raw in cleaned:
        norm = normalize_symbol(raw.upper())
        price, dt, err = close_by_norm.get(norm, (None, None, "missing batch key"))
        row = {
            "symbol": raw,
            "last_close_price": price,
            "date": dt,
            "error": err,
        }
        results.append(row)
        if price is not None:
            ok_count += 1
        else:
            fail_count += 1
            failed_symbols.append(raw)

    uniq_failed = list(dict.fromkeys(failed_symbols))
    if fail_count > ok_count and ok_count > 0:
        note_extra = (
            "Many symbols failed while some succeeded — often sequential throttling or sparse "
            "Yahoo data; use this batch function instead of per-symbol get_last_close_price loops."
        )
    elif fail_count == len(results) and results:
        note_extra = (
            "All symbols failed in batch — check exchange suffix (.NS/.BO) or ticker validity."
        )

    return {
        "results": results,
        "ok_count": ok_count,
        "fail_count": fail_count,
        "failed_symbols": uniq_failed,
        "note": note_extra.strip(),
    }


def get_ticker_info(symbol: str) -> dict:
    """Fetch comprehensive ticker information with 24+ stable metrics.

    Returns key financial metrics for valuation, growth, profitability, financial health, dividends, and price.

    Args:
        symbol: Stock ticker symbol (e.g., "AAPL", "RELIANCE.NS")

    Returns:
        {"symbol": t, "marketCap": ..., "trailingPE": ..., ...} containing:

        Valuation metrics:
        - trailingPE, forwardPE, priceToBook, priceToSalesTrailing12Months, enterpriseValue, marketCap

        Growth metrics:
        - revenueGrowth, earningsGrowth, earningsQuarterlyGrowth

        Profitability metrics:
        - profitMargins, grossMargins, operatingMargins, returnOnEquity, returnOnAssets

        Financial Health metrics:
        - debtToEquity, currentRatio, quickRatio, totalDebt, totalCash

        Dividend metrics:
        - dividendYield, payoutRatio, dividendRate

        Price metrics:
        - currentPrice, fiftyTwoWeekHigh, fiftyTwoWeekLow

    Example:
        info = get_ticker_info("AAPL")
        market_cap = info.get("marketCap")
        pe = info.get("trailingPE")
        revenue_growth = info.get("revenueGrowth")

    Note:
        For many Indian NSE symbols (.NS), Yahoo often omits growth/ROE/trailingPE in ``info``.
        For screening, combine with ``get_income_statement`` / ``get_balance_sheet`` or estimates
        when keys are missing — absent keys are not errors.
    """
    if not symbol:
        raise ValueError("Symbol is required")

    # Allowed and stable keys only
    allowed_keys = {
        # Valuation
        "trailingPE",
        "forwardPE",
        "priceToBook",
        "priceToSalesTrailing12Months",
        "enterpriseValue",
        "marketCap",
        # Growth
        "revenueGrowth",
        "earningsGrowth",
        "earningsQuarterlyGrowth",
        # Profitability
        "profitMargins",
        "grossMargins",
        "operatingMargins",
        "returnOnEquity",
        "returnOnAssets",
        # Financial Health
        "debtToEquity",
        "currentRatio",
        "quickRatio",
        "totalDebt",
        "totalCash",
        # Dividends
        "dividendYield",
        "payoutRatio",
        "dividendRate",
        # Price Stats
        "currentPrice",
        "fiftyTwoWeekHigh",
        "fiftyTwoWeekLow",
    }

    symbol_upper = symbol.strip().upper()

    # DB-first: query company_metadata JSONB from in_equities
    db_url = _get_db_url()
    if db_url:
        try:
            import psycopg

            with psycopg.connect(db_url) as conn:
                row = conn.execute(
                    "SELECT company_metadata FROM in_equities WHERE symbol = %s",
                    (symbol_upper,),
                ).fetchone()
            if row and row[0]:
                raw_meta = row[0]  # psycopg returns JSONB as dict automatically
                if isinstance(raw_meta, dict) and raw_meta:
                    result = {"symbol": symbol}
                    result.update({k: v for k, v in raw_meta.items() if k in allowed_keys})
                    return result
        except Exception as e:
            print(f"[get_ticker_info] DB fetch failed ({e}), falling back to yfinance")

    # yfinance fallback
    try:
        normalized_symbol = normalize_symbol(symbol_upper)
        ticker = yf.Ticker(normalized_symbol)
        info = ticker.info

        result = {"symbol": symbol}
        if isinstance(info, dict):
            filtered_info = {k: v for k, v in info.items() if k in allowed_keys}
            result.update(filtered_info)

        return result
    except Exception as e:
        print(f"ERROR: Failed to fetch ticker info for {symbol}: {str(e)}")
        return {"symbol": symbol, "error": str(e)}
