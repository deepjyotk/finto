from pathlib import Path

import pandas as pd
import yfinance as yf
from langchain.tools import tool


def _df_to_dict_safe(df):
    """Helper to safely convert DataFrame to a dict (records)."""
    if df is None:
        return {}
    if isinstance(df, dict):
        return df
    if hasattr(df, "to_dict"):
        return df.to_dict(orient="records")
    return {}


# 1️⃣ Major Holders
@tool("get_major_holders")
def get_major_holders(symbol_name: str) -> dict:
    """Return major shareholders for the given symbol name."""
    if not symbol_name:
        raise ValueError("Symbol name is required.")
    t = symbol_name.strip().upper()
    try:
        data = yf.Ticker(t).get_major_holders(as_dict=True)
        return {"symbol": t, "major_holders": data}
    except Exception as e:
        raise RuntimeError(f"Error fetching major holders for '{t}': {e}") from e


# 2️⃣ Institutional Holders
@tool("get_institutional_holders")
def get_institutional_holders(symbol_name: str) -> dict:
    """Return institutional holders for the given symbol name."""
    if not symbol_name:
        raise ValueError("Symbol name is required.")
    t = symbol_name.strip().upper()
    try:
        df = yf.Ticker(t).get_institutional_holders(as_dict=False)
        return {"symbol": t, "institutional_holders": _df_to_dict_safe(df)}
    except Exception as e:
        raise RuntimeError(f"Error fetching institutional holders for '{t}': {e}") from e


# 3️⃣ Mutual Fund Holders
@tool("get_mutualfund_holders")
def get_mutualfund_holders(symbol_name: str) -> dict:
    """Return mutual fund holders for the given symbol name."""
    if not symbol_name:
        raise ValueError("Symbol name is required.")
    t = symbol_name.strip().upper()
    try:
        df = yf.Ticker(t).get_mutualfund_holders(as_dict=False)
        return {"symbol": t, "mutualfund_holders": _df_to_dict_safe(df)}
    except Exception as e:
        raise RuntimeError(f"Error fetching mutual fund holders for '{t}': {e}") from e


# 4️⃣ Insider Purchases
@tool("get_insider_purchases")
def get_insider_purchases(symbol_name: str) -> dict:
    """Return insider purchase transactions for the given ticker."""
    if not symbol_name:
        raise ValueError("Symbol name is required.")
    t = symbol_name.strip().upper()
    try:
        df = yf.Ticker(t).get_insider_purchases(as_dict=False)
        return {"symbol": t, "insider_purchases": _df_to_dict_safe(df)}
    except Exception as e:
        raise RuntimeError(f"Error fetching insider purchases for '{t}': {e}") from e


# 5️⃣ Insider Transactions
@tool("get_insider_transactions")
def get_insider_transactions(symbol_name: str) -> dict:
    """Return insider transactions (sales, purchases, option exercises, etc.) for the given ticker."""
    if not symbol_name:
        raise ValueError("Symbol name is required.")
    t = symbol_name.strip().upper()
    try:
        df = yf.Ticker(t).get_insider_transactions(as_dict=False)
        return {"symbol": t, "insider_transactions": _df_to_dict_safe(df)}
    except Exception as e:
        raise RuntimeError(f"Error fetching insider transactions for '{t}': {e}") from e

    # 1️⃣ Dividends


@tool("get_dividends")
def get_dividends(symbol_name: str, period: str = "max") -> dict:
    """Fetch dividend payment history for a given ticker."""
    if not symbol_name:
        raise ValueError("Symbol name is required.")
    t = symbol_name.strip().upper()
    try:
        series = yf.Ticker(t).get_dividends(period=period)
        return {"symbol": t, "dividends": _df_to_dict_safe(series)}
    except Exception as e:
        raise RuntimeError(f"Error fetching dividends for {t}: {e}") from e


# 2️⃣ Capital Gains
@tool
def get_capital_gains(symbol_name: str, period: str = "max") -> dict:
    """Fetch capital gain distribution history (for funds/ETFs)."""
    if not symbol_name:
        raise ValueError("Symbol name is required.")
    t = symbol_name.strip().upper()
    try:
        series = yf.Ticker(t).get_capital_gains(period=period)
        return {"symbol": t, "capital_gains": _df_to_dict_safe(series)}
    except Exception as e:
        raise RuntimeError(f"Error fetching capital gains for {t}: {e}") from e


# 3️⃣ Balance Sheet
@tool("get_balance_sheet")
def get_balance_sheet(symbol_name: str, freq: str = "yearly", pretty: bool = False) -> dict:
    """Fetch balance sheet (yearly or quarterly)."""
    if not symbol_name:
        raise ValueError("Symbol name is required.")
    t = symbol_name.strip().upper()
    try:
        df = yf.Ticker(t).get_balance_sheet(as_dict=False, pretty=pretty, freq=freq)
        return {"symbol": t, "balance_sheet": _df_to_dict_safe(df)}
    except Exception as e:
        raise RuntimeError(f"Error fetching balance sheet for {t}: {e}") from e


# 4️⃣ Cash Flow
@tool("get_cash_flow")
def get_cash_flow(symbol_name: str, freq: str = "yearly", pretty: bool = False) -> dict:
    """Fetch cash flow statement (yearly or quarterly)."""
    if not symbol_name:
        raise ValueError("Symbol name is required.")
    t = symbol_name.strip().upper()
    try:
        df = yf.Ticker(t).get_cash_flow(as_dict=False, pretty=pretty, freq=freq)
        return {"symbol": t, "cash_flow": _df_to_dict_safe(df)}
    except Exception as e:
        raise RuntimeError(f"Error fetching cash flow for {t}: {e}") from e


# 5️⃣ Income Statement
@tool("get_income_statement")
def get_income_statement(symbol_name: str, freq: str = "yearly", pretty: bool = False) -> dict:
    """Fetch income statement (yearly, quarterly, or trailing)."""
    if not symbol_name:
        raise ValueError("Symbol name is required.")
    t = symbol_name.strip().upper()
    try:
        df = yf.Ticker(t).get_income_stmt(as_dict=False, pretty=pretty, freq=freq)
        cols_2022 = [c for c in df.columns if pd.to_datetime(str(c)).year == 2022]
        pd.set_option("display.float_format", "{:,.0f}".format)
        df_2022 = df[cols_2022]
        if df is not None and not df.empty:
            filepath = (
                Path(__file__).parent.parent.parent / f"income_statement_{t}_{freq}_2022.xlsx"
            )
            df_2022.to_excel(filepath)
        return {"symbol": t, "income_statement": _df_to_dict_safe(df)}
    except Exception as e:
        raise RuntimeError(f"Error fetching income statement for {t}: {e}") from e


# 6️⃣ Earnings Estimates
@tool("get_earnings_estimate")
def get_earnings_estimate(symbol_name: str) -> dict:
    """Fetch earnings estimates for upcoming quarters and years."""
    if not symbol_name:
        raise ValueError("Symbol name is required.")
    t = symbol_name.strip().upper()
    try:
        data = yf.Ticker(t).get_earnings_estimate(as_dict=True)
        return {"symbol": t, "earnings_estimate": _df_to_dict_safe(data)}
    except Exception as e:
        raise RuntimeError(f"Error fetching earnings estimate for {t}: {e}") from e


# 7️⃣ Revenue Estimates
@tool("get_revenue_estimate")
def get_revenue_estimate(symbol_name: str) -> dict:
    """Fetch revenue estimates for upcoming quarters and years."""
    if not symbol_name:
        raise ValueError("Symbol name is required.")
    t = symbol_name.strip().upper()
    try:
        data = yf.Ticker(t).get_revenue_estimate(as_dict=True)
        return {"symbol": t, "revenue_estimate": _df_to_dict_safe(data)}
    except Exception as e:
        raise RuntimeError(f"Error fetching revenue estimate for {t}: {e}") from e


# 8️⃣ Earnings History
@tool("get_earnings_history")
def get_earnings_history(symbol_name: str) -> dict:
    """Fetch past earnings results (EPS actual vs. estimate)."""
    if not symbol_name:
        raise ValueError("Symbol name is required.")
    t = symbol_name.strip().upper()
    try:
        data = yf.Ticker(t).get_earnings_history(as_dict=True)
        return {"symbol": t, "earnings_history": _df_to_dict_safe(data)}
    except Exception as e:
        raise RuntimeError(f"Error fetching earnings history for {t}: {e}") from e


# 9️⃣ EPS Trend
@tool("get_eps_trend")
def get_eps_trend(symbol_name: str) -> dict:
    """Fetch historical EPS trend data (current vs 7, 30, 60, 90 days ago)."""
    if not symbol_name:
        raise ValueError("Symbol name is required.")
    t = symbol_name.strip().upper()
    try:
        data = yf.Ticker(t).get_eps_trend(as_dict=True)
        return {"symbol": t, "eps_trend": _df_to_dict_safe(data)}
    except Exception as e:
        raise RuntimeError(f"Error fetching EPS trend for {t}: {e}") from e


# 🔟 EPS Revisions
@tool
def get_eps_revisions(symbol_name: str) -> dict:
    """Fetch EPS revisions (up/down changes last 7 & 30 days)."""
    if not symbol_name:
        raise ValueError("Symbol name is required.")
    t = symbol_name.strip().upper()
    try:
        data = yf.Ticker(t).get_eps_revisions(as_dict=True)
        return {"symbol": t, "eps_revisions": _df_to_dict_safe(data)}
    except Exception as e:
        raise RuntimeError(f"Error fetching EPS revisions for {t}: {e}") from e


# 11️⃣ Growth Estimates
@tool("get_growth_estimates")
def get_growth_estimates(symbol_name: str) -> dict:
    """Fetch growth estimates (stock, sector, industry, index comparisons)."""
    if not symbol_name:
        raise ValueError("Symbol name is required.")
    t = symbol_name.strip().upper()
    try:
        data = yf.Ticker(t).get_growth_estimates(as_dict=True)
        return {"symbol": t, "growth_estimates": _df_to_dict_safe(data)}
    except Exception as e:
        raise RuntimeError(f"Error fetching growth estimates for {t}: {e}") from e


# 12️⃣ Earnings (actual trailing or yearly data)
@tool("get_earnings")
def get_earnings(symbol_name: str, freq: str = "yearly") -> dict:
    """Fetch trailing or yearly earnings data."""
    if not symbol_name:
        raise ValueError("Symbol name is required.")
    t = symbol_name.strip().upper()
    try:
        data = yf.Ticker(t).get_earnings(as_dict=True, freq=freq)
        return {"symbol": t, "earnings": _df_to_dict_safe(data)}
    except Exception as e:
        raise RuntimeError(f"Error fetching earnings for {t}: {e}") from e
