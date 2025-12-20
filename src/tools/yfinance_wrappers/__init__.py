"""Simple YFinance wrapper functions for use in generated Python code.

These functions mirror the langchain tools but are plain Python functions
that can be called directly in generated code without the langchain tool wrapper.
"""

import re
from typing import Optional

import yfinance as yf

INDIAN_EXCHANGE_SUFFIXES = {"NS", "BO"}


def normalize_symbol(symbol: str, default_exchange: str = "NS") -> str:
    if not symbol:
        raise ValueError("Symbol is required")

    s = symbol.strip().upper()

    # If exchange suffix already exists, keep it
    if "." in s and s.split(".")[1] in INDIAN_EXCHANGE_SUFFIXES:
        return s

    # Heuristic: assume Indian equity and default to NSE
    if re.fullmatch(r"[A-Z][A-Z0-9&\-]{1,20}", s):
        normalized = f"{s}.{default_exchange}"
        return normalized

    return s


def get_balance_sheet(symbol_name: str, freq: str = "yearly", pretty: bool = False) -> dict:
    """Fetch balance sheet (yearly or quarterly).

    Args:
        symbol_name: Stock ticker symbol (e.g., "AAPL", "RELIANCE")
        freq: "yearly" or "quarterly"
        pretty: If True, format column names nicely

    Returns:
        {"symbol": t, "balance_sheet": {...}}
    """
    try:
        if not symbol_name:
            print(f"ERROR: Symbol {symbol_name} is empty or None")
            raise ValueError("Symbol name is required.")
        normalized_symbol = normalize_symbol(symbol_name.strip().upper())
        data = yf.Ticker(normalized_symbol).get_balance_sheet(
            as_dict=True, pretty=pretty, freq=freq
        )

        # Convert Timestamp keys to strings if data is a dict
        if isinstance(data, dict):
            balance_sheet = {str(k): v for k, v in data.items()}
        else:
            balance_sheet = data

        return {"symbol": symbol_name, "balance_sheet": balance_sheet}
    except Exception as e:
        print(f"ERROR: Failed to fetch balance sheet for symbol: {symbol_name} - {e}")
        return {"symbol": symbol_name, "balance_sheet": {}, "error": str(e)}


def get_income_statement(symbol_name: str, freq: str = "yearly", pretty: bool = False) -> dict:
    """Fetch income statement (yearly or quarterly).

    Args:
        symbol_name: Stock ticker symbol
        freq: "yearly" or "quarterly"
        pretty: If True, format column names nicely

    Returns:
        {"symbol": t, "income_statement": {...}}
    """
    try:
        if not symbol_name:
            print(f"ERROR: Symbol {symbol_name} is empty or None")
            raise ValueError("Symbol name is required.")
        normalized_symbol = normalize_symbol(symbol_name.strip().upper())
        data = yf.Ticker(normalized_symbol).get_income_stmt(as_dict=True, pretty=pretty, freq=freq)

        # Convert Timestamp keys to strings if data is a dict
        if isinstance(data, dict):
            income_statement = {str(k): v for k, v in data.items()}
        else:
            income_statement = data

        return {"symbol": symbol_name, "income_statement": income_statement}
    except Exception as e:
        print(f"ERROR: Failed to fetch income statement for symbol: {symbol_name} - {e}")
        return {"symbol": symbol_name, "income_statement": {}, "error": str(e)}


def get_cash_flow(symbol_name: str, freq: str = "yearly", pretty: bool = False) -> dict:
    """Fetch cash flow statement (yearly or quarterly).

    Args:
        symbol_name: Stock ticker symbol
        freq: "yearly" or "quarterly"
        pretty: If True, format column names nicely

    Returns:
        {"symbol": t, "cash_flow": {...}}
    """
    try:
        if not symbol_name:
            print(f"ERROR: Symbol {symbol_name} is empty or None")
            raise ValueError("Symbol name is required.")

        normalized_symbol = normalize_symbol(symbol_name.strip().upper())
        data = yf.Ticker(normalized_symbol).get_cashflow(as_dict=True, pretty=pretty, freq=freq)
        # Convert Timestamp keys to strings if data is a dict
        if isinstance(data, dict):
            cash_flow = {str(k): v for k, v in data.items()}
        else:
            cash_flow = data

        return {"symbol": symbol_name, "cash_flow": cash_flow}

    except Exception as e:
        print(f"ERROR: Failed to fetch cash flow for symbol: {symbol_name} - {e}")
        return {"symbol": symbol_name, "cash_flow": {}, "error": str(e)}


def get_dividends(symbol_name: str, period: str = "max") -> dict:
    """Fetch dividend payment history.

    Args:
        symbol_name: Stock ticker symbol
        period: Period to fetch (e.g., "1y", "5y", "max")

    Returns:
        {"symbol": t, "dividends": {...}}
    """
    try:
        if not symbol_name:
            raise ValueError("Symbol name is required.")
        normalized_symbol = normalize_symbol(symbol_name.strip().upper())
        series = yf.Ticker(normalized_symbol).get_dividends(period=period)
        # Convert Series to dict: {date: value}
        if hasattr(series, "to_dict"):
            div_dict = {str(k): float(v) for k, v in series.to_dict().items()}
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
        {"symbol": t, "capital_gains": {...}}
    """
    try:
        if not symbol_name:
            print(f"ERROR: Symbol {symbol_name} is empty or None")
            raise ValueError("Symbol name is required.")
        normalized_symbol = normalize_symbol(symbol_name.strip().upper())
        series = yf.Ticker(normalized_symbol).get_capital_gains(period=period)
        # Convert Series to dict: {date: value}
        if hasattr(series, "to_dict"):
            cg_dict = {str(k): float(v) for k, v in series.to_dict().items()}
        else:
            cg_dict = {}
        return {"symbol": symbol_name, "capital_gains": cg_dict}
    except Exception as e:
        print(f"ERROR: Failed to fetch capital gains for symbol: {symbol_name} - {e}")
        return {"symbol": symbol_name, "capital_gains": {}, "error": str(e)}


def get_earnings(symbol_name: str, freq: str = "yearly") -> dict:
    """Fetch earnings data.

    Args:
        symbol_name: Stock ticker symbol
        freq: "yearly" or "quarterly"

    Returns:
        {"symbol": t, "earnings": {...}}
    """
    try:
        if not symbol_name:
            print(f"ERROR: Symbol {symbol_name} is empty or None")
            raise ValueError("Symbol name is required.")
        normalized_symbol = normalize_symbol(symbol_name.strip().upper())
        data = yf.Ticker(normalized_symbol).get_earnings(as_dict=True, freq=freq)
        return {"symbol": symbol_name, "earnings": data if data else {}}
    except Exception as e:
        print(f"ERROR: Failed to fetch earnings for symbol: {symbol_name} - {e}")
        return {"symbol": symbol_name, "earnings": {}, "error": str(e)}


def get_earnings_estimate(symbol_name: str) -> dict:
    """Fetch earnings estimates.

    Args:
        symbol_name: Stock ticker symbol

    Returns:
        {"symbol": t, "earnings_estimate": {...}}
    """
    try:
        if not symbol_name:
            print(f"ERROR: Symbol {symbol_name} is empty or None")
            raise ValueError("Symbol name is required.")
        normalized_symbol = normalize_symbol(symbol_name.strip().upper())
        data = yf.Ticker(normalized_symbol).get_earnings_estimate()
        return {"symbol": symbol_name, "earnings_estimate": data if data is not None else {}}
    except Exception as e:
        print(f"ERROR: Failed to fetch earnings estimate for symbol: {symbol_name} - {e}")
        return {"symbol": symbol_name, "earnings_estimate": {}, "error": str(e)}


def get_revenue_estimate(symbol_name: str) -> dict:
    """Fetch revenue estimates.

    Args:
        symbol_name: Stock ticker symbol

    Returns:
        {"symbol": t, "revenue_estimate": {...}}
    """
    try:
        if not symbol_name:
            print(f"ERROR: Symbol {symbol_name} is empty or None")
            raise ValueError("Symbol name is required.")
        normalized_symbol = normalize_symbol(symbol_name.strip().upper())
        data = yf.Ticker(normalized_symbol).get_revenue_estimate()
        return {"symbol": symbol_name, "revenue_estimate": data if data is not None else {}}
    except Exception as e:
        print(f"ERROR: Failed to fetch revenue estimate for symbol: {symbol_name} - {e}")
        return {"symbol": symbol_name, "revenue_estimate": {}, "error": str(e)}


def get_earnings_history(symbol_name: str) -> dict:
    """Fetch earnings history.

    Args:
        symbol_name: Stock ticker symbol

    Returns:
        {"symbol": t, "earnings_history": {...}}
    """
    try:
        if not symbol_name:
            print(f"ERROR: Symbol {symbol_name} is empty or None")
            raise ValueError("Symbol name is required.")

        normalized_symbol = normalize_symbol(symbol_name.strip().upper())
        data = yf.Ticker(normalized_symbol).get_earnings_history()
        return {"symbol": symbol_name, "earnings_history": data if data is not None else {}}
    except Exception as e:
        print(f"ERROR: Failed to fetch earnings history for symbol: {symbol_name} - {e}")
        return {"symbol": symbol_name, "earnings_history": {}, "error": str(e)}


def get_eps_trend(symbol_name: str) -> dict:
    """Fetch EPS trend data.

    Args:
        symbol_name: Stock ticker symbol

    Returns:
        {"symbol": t, "eps_trend": {...}}
    """
    try:
        if not symbol_name:
            print(f"ERROR: Symbol {symbol_name} is empty or None")
            raise ValueError("Symbol name is required.")
        normalized_symbol = normalize_symbol(symbol_name.strip().upper())
        data = yf.Ticker(normalized_symbol).get_eps_trend()
        return {"symbol": symbol_name, "eps_trend": data if data is not None else {}}
    except Exception as e:
        print(f"ERROR: Failed to fetch EPS trend for symbol: {symbol_name} - {e}")
        return {"symbol": symbol_name, "eps_trend": {}, "error": str(e)}


def get_eps_revisions(symbol_name: str) -> dict:
    """Fetch EPS revisions data.

    Args:
        symbol_name: Stock ticker symbol

    Returns:
        {"symbol": t, "eps_revisions": {...}}
    """
    try:
        if not symbol_name:
            print(f"ERROR: Symbol {symbol_name} is empty or None")
            raise ValueError("Symbol name is required.")
        normalized_symbol = normalize_symbol(symbol_name.strip().upper())
        data = yf.Ticker(normalized_symbol).get_eps_revisions()
        return {"symbol": symbol_name, "eps_revisions": data if data is not None else {}}
    except Exception as e:
        print(f"ERROR: Failed to fetch EPS revisions for symbol: {symbol_name} - {e}")
        return {"symbol": symbol_name, "eps_revisions": {}, "error": str(e)}


def get_growth_estimates(symbol_name: str) -> dict:
    """Fetch growth estimates.

    Args:
        symbol_name: Stock ticker symbol

    Returns:
        {"symbol": t, "growth_estimates": {...}}
    """
    try:
        if not symbol_name:
            print(f"ERROR: Symbol {symbol_name} is empty or None")
            raise ValueError("Symbol name is required.")
        normalized_symbol = normalize_symbol(symbol_name.strip().upper())
        data = yf.Ticker(normalized_symbol).get_growth_estimates()
        return {"symbol": symbol_name, "growth_estimates": data if data is not None else {}}
    except Exception as e:
        print(f"ERROR: Failed to fetch growth estimates for symbol: {symbol_name} - {e}")
        return {"symbol": symbol_name, "growth_estimates": {}, "error": str(e)}


def get_major_holders(symbol_name: str) -> dict:
    """Fetch major holders information.

    Args:
        symbol_name: Stock ticker symbol

    Returns:
        {"symbol": t, "major_holders": {...}}
    """
    try:
        if not symbol_name:
            print(f"ERROR: Symbol {symbol_name} is empty or None")
            raise ValueError("Symbol name is required.")
        normalized_symbol = normalize_symbol(symbol_name.strip().upper())
        data = yf.Ticker(normalized_symbol).get_major_holders()
        return {"symbol": symbol_name, "major_holders": data if data is not None else {}}
    except Exception as e:
        print(f"ERROR: Failed to fetch major holders for symbol: {symbol_name} - {e}")
        return {"symbol": symbol_name, "major_holders": {}, "error": str(e)}


def get_institutional_holders(symbol_name: str) -> dict:
    """Fetch institutional holders information.

    Args:
        symbol_name: Stock ticker symbol

    Returns:
        {"symbol": t, "institutional_holders": {...}}
    """
    try:
        if not symbol_name:
            print(f"ERROR: Symbol {symbol_name} is empty or None")
            raise ValueError("Symbol name is required.")
        normalized_symbol = normalize_symbol(symbol_name.strip().upper())
        data = yf.Ticker(normalized_symbol).get_institutional_holders()
        return {"symbol": symbol_name, "institutional_holders": data if data is not None else {}}
    except Exception as e:
        print(f"ERROR: Failed to fetch institutional holders for symbol: {symbol_name} - {e}")
        return {"symbol": symbol_name, "institutional_holders": {}, "error": str(e)}


def get_mutualfund_holders(symbol_name: str) -> dict:
    """Fetch mutual fund holders information.

    Args:
        symbol_name: Stock ticker symbol

    Returns:
        {"symbol": t, "mutualfund_holders": {...}}
    """
    try:
        if not symbol_name:
            print(f"ERROR: Symbol {symbol_name} is empty or None")
            raise ValueError("Symbol name is required.")
        normalized_symbol = normalize_symbol(symbol_name.strip().upper())
        data = yf.Ticker(normalized_symbol).get_mutualfund_holders()
        return {"symbol": symbol_name, "mutualfund_holders": data if data is not None else {}}
    except Exception as e:
        print(f"ERROR: Failed to fetch mutual fund holders for symbol: {symbol_name} - {e}")
        return {"symbol": symbol_name, "mutualfund_holders": {}, "error": str(e)}


def get_insider_purchases(symbol_name: str) -> dict:
    """Fetch insider purchase transactions.

    Args:
        symbol_name: Stock ticker symbol

    Returns:
        {"symbol": t, "insider_purchases": {...}}
    """
    try:
        if not symbol_name:
            print(f"ERROR: Symbol {symbol_name} is empty or None")
            raise ValueError("Symbol name is required.")
        normalized_symbol = normalize_symbol(symbol_name.strip().upper())
        data = yf.Ticker(normalized_symbol).get_insider_purchases()
        return {"symbol": symbol_name, "insider_purchases": data if data is not None else {}}
    except Exception as e:
        print(f"ERROR: Failed to fetch insider purchases for symbol: {symbol_name} - {e}")
        return {"symbol": symbol_name, "insider_purchases": {}, "error": str(e)}


def get_insider_transactions(symbol_name: str) -> dict:
    """Fetch all insider transactions.

    Args:
        symbol_name: Stock ticker symbol

    Returns:
        {"symbol": t, "insider_transactions": {...}}
    """
    try:
        if not symbol_name:
            print(f"ERROR: Symbol {symbol_name} is empty or None")
            raise ValueError("Symbol name is required.")
        normalized_symbol = normalize_symbol(symbol_name.strip().upper())
        data = yf.Ticker(normalized_symbol).get_insider_transactions()
        return {"symbol": symbol_name, "insider_transactions": data if data is not None else {}}
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
        return {"symbol": symbol_name, "last_close_price": None, "date": None, "error": str(e)}
