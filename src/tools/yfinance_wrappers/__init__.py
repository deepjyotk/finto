"""Simple YFinance wrapper functions for use in generated Python code.

These functions mirror the langchain tools but are plain Python functions
that can be called directly in generated code without the langchain tool wrapper.
"""

from typing import Optional

import yfinance as yf

from src.utils.data_frame import _df_to_dict_safe


def get_balance_sheet(symbol_name: str, freq: str = "yearly", pretty: bool = False) -> dict:
    """Fetch balance sheet (yearly or quarterly).

    Args:
        symbol_name: Stock ticker symbol (e.g., "AAPL", "RELIANCE.NS")
        freq: "yearly" or "quarterly"
        pretty: If True, format column names nicely

    Returns:
        Dict with symbol and balance_sheet data
    """
    if not symbol_name:
        raise ValueError("Symbol name is required.")
    t = symbol_name.strip().upper()
    df = yf.Ticker(t).get_balance_sheet(as_dict=False, pretty=pretty, freq=freq)
    return {"symbol": t, "balance_sheet": _df_to_dict_safe(df)}


def get_income_statement(symbol_name: str, freq: str = "yearly", pretty: bool = False) -> dict:
    """Fetch income statement (yearly or quarterly).

    Args:
        symbol_name: Stock ticker symbol
        freq: "yearly" or "quarterly"
        pretty: If True, format column names nicely

    Returns:
        Dict with symbol and income_statement data
    """
    if not symbol_name:
        raise ValueError("Symbol name is required.")
    t = symbol_name.strip().upper()
    df = yf.Ticker(t).get_income_stmt(as_dict=False, pretty=pretty, freq=freq)
    return {"symbol": t, "income_statement": _df_to_dict_safe(df)}


def get_cash_flow(symbol_name: str, freq: str = "yearly", pretty: bool = False) -> dict:
    """Fetch cash flow statement (yearly or quarterly).

    Args:
        symbol_name: Stock ticker symbol
        freq: "yearly" or "quarterly"
        pretty: If True, format column names nicely

    Returns:
        Dict with symbol and cash_flow data
    """
    if not symbol_name:
        raise ValueError("Symbol name is required.")
    t = symbol_name.strip().upper()
    df = yf.Ticker(t).get_cashflow(as_dict=False, pretty=pretty, freq=freq)
    return {"symbol": t, "cash_flow": _df_to_dict_safe(df)}


def get_dividends(symbol_name: str, period: str = "max") -> dict:
    """Fetch dividend payment history.

    Args:
        symbol_name: Stock ticker symbol
        period: Period to fetch (e.g., "1y", "5y", "max")

    Returns:
        Dict with symbol and dividends data
    """
    if not symbol_name:
        raise ValueError("Symbol name is required.")
    t = symbol_name.strip().upper()
    series = yf.Ticker(t).get_dividends(period=period)
    # Convert Series to dict: {date: value}
    if hasattr(series, "to_dict"):
        div_dict = {str(k): float(v) for k, v in series.to_dict().items()}
    else:
        div_dict = {}
    return {"symbol": t, "dividends": div_dict}


def get_capital_gains(symbol_name: str, period: str = "max") -> dict:
    """Fetch capital gains history.

    Args:
        symbol_name: Stock ticker symbol
        period: Period to fetch (e.g., "1y", "5y", "max")

    Returns:
        Dict with symbol and capital_gains data
    """
    if not symbol_name:
        raise ValueError("Symbol name is required.")
    t = symbol_name.strip().upper()
    series = yf.Ticker(t).get_capital_gains(period=period)
    # Convert Series to dict: {date: value}
    if hasattr(series, "to_dict"):
        cg_dict = {str(k): float(v) for k, v in series.to_dict().items()}
    else:
        cg_dict = {}
    return {"symbol": t, "capital_gains": cg_dict}


def get_earnings(symbol_name: str, freq: str = "yearly") -> dict:
    """Fetch earnings data.

    Args:
        symbol_name: Stock ticker symbol
        freq: "yearly" or "quarterly"

    Returns:
        Dict with symbol and earnings data
    """
    if not symbol_name:
        raise ValueError("Symbol name is required.")
    t = symbol_name.strip().upper()
    data = yf.Ticker(t).get_earnings(as_dict=True, freq=freq)
    return {"symbol": t, "earnings": _df_to_dict_safe(data)}


def get_earnings_estimate(symbol_name: str) -> dict:
    """Fetch earnings estimates.

    Args:
        symbol_name: Stock ticker symbol

    Returns:
        Dict with symbol and earnings_estimate data
    """
    if not symbol_name:
        raise ValueError("Symbol name is required.")
    t = symbol_name.strip().upper()
    data = yf.Ticker(t).get_earnings_estimate()
    return {"symbol": t, "earnings_estimate": _df_to_dict_safe(data)}


def get_revenue_estimate(symbol_name: str) -> dict:
    """Fetch revenue estimates.

    Args:
        symbol_name: Stock ticker symbol

    Returns:
        Dict with symbol and revenue_estimate data
    """
    if not symbol_name:
        raise ValueError("Symbol name is required.")
    t = symbol_name.strip().upper()
    data = yf.Ticker(t).get_revenue_estimate()
    return {"symbol": t, "revenue_estimate": _df_to_dict_safe(data)}


def get_earnings_history(symbol_name: str) -> dict:
    """Fetch earnings history.

    Args:
        symbol_name: Stock ticker symbol

    Returns:
        Dict with symbol and earnings_history data
    """
    if not symbol_name:
        raise ValueError("Symbol name is required.")
    t = symbol_name.strip().upper()
    data = yf.Ticker(t).get_earnings_history()
    return {"symbol": t, "earnings_history": _df_to_dict_safe(data)}


def get_eps_trend(symbol_name: str) -> dict:
    """Fetch EPS trend data.

    Args:
        symbol_name: Stock ticker symbol

    Returns:
        Dict with symbol and eps_trend data
    """
    if not symbol_name:
        raise ValueError("Symbol name is required.")
    t = symbol_name.strip().upper()
    data = yf.Ticker(t).get_eps_trend()
    return {"symbol": t, "eps_trend": _df_to_dict_safe(data)}


def get_eps_revisions(symbol_name: str) -> dict:
    """Fetch EPS revisions data.

    Args:
        symbol_name: Stock ticker symbol

    Returns:
        Dict with symbol and eps_revisions data
    """
    if not symbol_name:
        raise ValueError("Symbol name is required.")
    t = symbol_name.strip().upper()
    data = yf.Ticker(t).get_eps_revisions()
    return {"symbol": t, "eps_revisions": _df_to_dict_safe(data)}


def get_growth_estimates(symbol_name: str) -> dict:
    """Fetch growth estimates.

    Args:
        symbol_name: Stock ticker symbol

    Returns:
        Dict with symbol and growth_estimates data
    """
    if not symbol_name:
        raise ValueError("Symbol name is required.")
    t = symbol_name.strip().upper()
    data = yf.Ticker(t).get_growth_estimates()
    return {"symbol": t, "growth_estimates": _df_to_dict_safe(data)}


def get_major_holders(symbol_name: str) -> dict:
    """Fetch major holders information.

    Args:
        symbol_name: Stock ticker symbol

    Returns:
        Dict with symbol and major_holders data
    """
    if not symbol_name:
        raise ValueError("Symbol name is required.")
    t = symbol_name.strip().upper()
    data = yf.Ticker(t).get_major_holders()
    return {"symbol": t, "major_holders": _df_to_dict_safe(data)}


def get_institutional_holders(symbol_name: str) -> dict:
    """Fetch institutional holders information.

    Args:
        symbol_name: Stock ticker symbol

    Returns:
        Dict with symbol and institutional_holders data
    """
    if not symbol_name:
        raise ValueError("Symbol name is required.")
    t = symbol_name.strip().upper()
    data = yf.Ticker(t).get_institutional_holders()
    return {"symbol": t, "institutional_holders": _df_to_dict_safe(data)}


def get_mutualfund_holders(symbol_name: str) -> dict:
    """Fetch mutual fund holders information.

    Args:
        symbol_name: Stock ticker symbol

    Returns:
        Dict with symbol and mutualfund_holders data
    """
    if not symbol_name:
        raise ValueError("Symbol name is required.")
    t = symbol_name.strip().upper()
    data = yf.Ticker(t).get_mutualfund_holders()
    return {"symbol": t, "mutualfund_holders": _df_to_dict_safe(data)}


def get_insider_purchases(symbol_name: str) -> dict:
    """Fetch insider purchase transactions.

    Args:
        symbol_name: Stock ticker symbol

    Returns:
        Dict with symbol and insider_purchases data
    """
    if not symbol_name:
        raise ValueError("Symbol name is required.")
    t = symbol_name.strip().upper()
    data = yf.Ticker(t).get_insider_purchases()
    return {"symbol": t, "insider_purchases": _df_to_dict_safe(data)}


def get_insider_transactions(symbol_name: str) -> dict:
    """Fetch all insider transactions.

    Args:
        symbol_name: Stock ticker symbol

    Returns:
        Dict with symbol and insider_transactions data
    """
    if not symbol_name:
        raise ValueError("Symbol name is required.")
    t = symbol_name.strip().upper()
    data = yf.Ticker(t).get_insider_transactions()
    return {"symbol": t, "insider_transactions": _df_to_dict_safe(data)}


def get_ticker_price(
    ticker_symbol: str,
    period: str = "1d",
    interval: str = "1d",
    adjust_mode: str = "auto",
    prepost: bool = False,
    repair: bool = False,
    timeout: Optional[float] = 10.0,
) -> dict:
    """Fetch historical price data for a ticker.

    Args:
        ticker_symbol: Stock ticker symbol (e.g., "RELIANCE.NS", "AAPL")
        period: Period to fetch (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max)
        interval: Data interval (1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h, 1d, 5d, 1wk, 1mo, 3mo)
        adjust_mode: "auto", "back", or "none" for price adjustment
        prepost: Include pre/post market data
        repair: Attempt to fix data errors
        timeout: Request timeout in seconds

    Returns:
        Dict with symbol and price history as {date: price} mapping
    """
    ticker_symbol = ticker_symbol.strip().upper()
    if not ticker_symbol:
        raise ValueError("ticker_symbol must be non-empty")

    # Map adjust_mode to yfinance parameters
    auto_adjust = adjust_mode == "auto"
    back_adjust = adjust_mode == "back"

    try:
        hist = yf.Ticker(ticker_symbol).history(
            period=period,
            interval=interval,
            auto_adjust=auto_adjust,
            back_adjust=back_adjust,
            prepost=prepost,
            repair=repair,
            timeout=timeout,
        )

        if hist.empty:
            return {"symbol": ticker_symbol, "prices": {}, "message": "No data available"}

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
            "symbol": ticker_symbol,
            "prices": price_dict,
            "period": period,
            "interval": interval,
        }
    except Exception as e:
        raise RuntimeError(f"Error fetching price for {ticker_symbol}: {e}") from e


def get_last_close_price(symbol_name: str) -> dict:
    """Fetch the most recent close price for a ticker.

    Args:
        symbol_name: Stock ticker symbol (e.g., "AAPL", "RELIANCE.NS")

    Returns:
        Dict with symbol, last_close_price, and date
        Example: {"symbol": "AAPL", "last_close_price": 150.25, "date": "2024-01-15"}
    """
    if not symbol_name:
        raise ValueError("Symbol name is required.")

    ticker_symbol = symbol_name.strip().upper()
    try:
        ticker = yf.Ticker(ticker_symbol)
        # Get last 5 days to ensure we have data
        hist = ticker.history(period="5d")

        if hist.empty:
            return {
                "symbol": ticker_symbol,
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

        return {"symbol": ticker_symbol, "last_close_price": last_close, "date": date_str}
    except Exception as e:
        return {"symbol": ticker_symbol, "last_close_price": None, "date": None, "error": str(e)}
