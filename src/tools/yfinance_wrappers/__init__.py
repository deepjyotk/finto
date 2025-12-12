"""Simple YFinance wrapper functions for use in generated Python code.

These functions mirror the langchain tools but are plain Python functions
that can be called directly in generated code without the langchain tool wrapper.
"""

from typing import Optional

import yfinance as yf


def get_balance_sheet(symbol_name: str, freq: str = "yearly", pretty: bool = False) -> dict:
    """Fetch balance sheet (yearly or quarterly).

    Args:
        symbol_name: Stock ticker symbol (e.g., "AAPL", "RELIANCE.NS")
        freq: "yearly" or "quarterly"
        pretty: If True, format column names nicely

    Returns:
        {"symbol": t, "balance_sheet": {...}}
    """
    if not symbol_name:
        raise ValueError("Symbol name is required.")
    t = symbol_name.strip().upper()
    data = yf.Ticker(t).get_balance_sheet(as_dict=True, pretty=pretty, freq=freq)
    
    # Convert Timestamp keys to strings if data is a dict
    if isinstance(data, dict):
        balance_sheet = {str(k): v for k, v in data.items()}
    else:
        balance_sheet = data
    
    return {"symbol": t, "balance_sheet": balance_sheet}


def get_income_statement(symbol_name: str, freq: str = "yearly", pretty: bool = False) -> dict:
    """Fetch income statement (yearly or quarterly).

    Args:
        symbol_name: Stock ticker symbol
        freq: "yearly" or "quarterly"
        pretty: If True, format column names nicely

    Returns:
        {"symbol": t, "income_statement": {...}}
    """
    if not symbol_name:
        raise ValueError("Symbol name is required.")
    t = symbol_name.strip().upper()
    data = yf.Ticker(t).get_income_stmt(as_dict=True, pretty=pretty, freq=freq)
    
    # Convert Timestamp keys to strings if data is a dict
    if isinstance(data, dict):
        income_statement = {str(k): v for k, v in data.items()}
    else:
        income_statement = data
    
    return {"symbol": t, "income_statement": income_statement}


def get_cash_flow(symbol_name: str, freq: str = "yearly", pretty: bool = False) -> dict:
    """Fetch cash flow statement (yearly or quarterly).

    Args:
        symbol_name: Stock ticker symbol
        freq: "yearly" or "quarterly"
        pretty: If True, format column names nicely

    Returns:
        {"symbol": t, "cash_flow": {...}}
    """
    if not symbol_name:
        raise ValueError("Symbol name is required.")
    t = symbol_name.strip().upper()
    data = yf.Ticker(t).get_cashflow(as_dict=True, pretty=pretty, freq=freq)
    
    # Convert Timestamp keys to strings if data is a dict
    if isinstance(data, dict):
        cash_flow = {str(k): v for k, v in data.items()}
    else:
        cash_flow = data
    
    return {"symbol": t, "cash_flow": cash_flow}


def get_dividends(symbol_name: str, period: str = "max") -> dict:
    """Fetch dividend payment history.

    Args:
        symbol_name: Stock ticker symbol
        period: Period to fetch (e.g., "1y", "5y", "max")

    Returns:
        {"symbol": t, "dividends": {...}}
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
        {"symbol": t, "capital_gains": {...}}
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
        {"symbol": t, "earnings": {...}}
    """
    if not symbol_name:
        raise ValueError("Symbol name is required.")
    t = symbol_name.strip().upper()
    data = yf.Ticker(t).get_earnings(as_dict=True, freq=freq)
    return {"symbol": t, "earnings": data if data else {}}


def get_earnings_estimate(symbol_name: str) -> dict:
    """Fetch earnings estimates.

    Args:
        symbol_name: Stock ticker symbol

    Returns:
        {"symbol": t, "earnings_estimate": {...}}
    """
    if not symbol_name:
        raise ValueError("Symbol name is required.")
    t = symbol_name.strip().upper()
    data = yf.Ticker(t).get_earnings_estimate()
    return {"symbol": t, "earnings_estimate": data if data is not None else {}}


def get_revenue_estimate(symbol_name: str) -> dict:
    """Fetch revenue estimates.

    Args:
        symbol_name: Stock ticker symbol

    Returns:
        {"symbol": t, "revenue_estimate": {...}}
    """
    if not symbol_name:
        raise ValueError("Symbol name is required.")
    t = symbol_name.strip().upper()
    data = yf.Ticker(t).get_revenue_estimate()
    return {"symbol": t, "revenue_estimate": data if data is not None else {}}


def get_earnings_history(symbol_name: str) -> dict:
    """Fetch earnings history.

    Args:
        symbol_name: Stock ticker symbol

    Returns:
        {"symbol": t, "earnings_history": {...}}
    """
    if not symbol_name:
        raise ValueError("Symbol name is required.")
    t = symbol_name.strip().upper()
    data = yf.Ticker(t).get_earnings_history()
    return {"symbol": t, "earnings_history": data if data is not None else {}}


def get_eps_trend(symbol_name: str) -> dict:
    """Fetch EPS trend data.

    Args:
        symbol_name: Stock ticker symbol

    Returns:
        {"symbol": t, "eps_trend": {...}}
    """
    if not symbol_name:
        raise ValueError("Symbol name is required.")
    t = symbol_name.strip().upper()
    data = yf.Ticker(t).get_eps_trend()
    return {"symbol": t, "eps_trend": data if data is not None else {}}


def get_eps_revisions(symbol_name: str) -> dict:
    """Fetch EPS revisions data.

    Args:
        symbol_name: Stock ticker symbol

    Returns:
        {"symbol": t, "eps_revisions": {...}}
    """
    if not symbol_name:
        raise ValueError("Symbol name is required.")
    t = symbol_name.strip().upper()
    data = yf.Ticker(t).get_eps_revisions()
    return {"symbol": t, "eps_revisions": data if data is not None else {}}


def get_growth_estimates(symbol_name: str) -> dict:
    """Fetch growth estimates.

    Args:
        symbol_name: Stock ticker symbol

    Returns:
        {"symbol": t, "growth_estimates": {...}}
    """
    if not symbol_name:
        raise ValueError("Symbol name is required.")
    t = symbol_name.strip().upper()
    data = yf.Ticker(t).get_growth_estimates()
    return {"symbol": t, "growth_estimates": data if data is not None else {}}


def get_major_holders(symbol_name: str) -> dict:
    """Fetch major holders information.

    Args:
        symbol_name: Stock ticker symbol

    Returns:
        {"symbol": t, "major_holders": {...}}
    """
    if not symbol_name:
        raise ValueError("Symbol name is required.")
    t = symbol_name.strip().upper()
    data = yf.Ticker(t).get_major_holders()
    return {"symbol": t, "major_holders": data if data is not None else {}}


def get_institutional_holders(symbol_name: str) -> dict:
    """Fetch institutional holders information.

    Args:
        symbol_name: Stock ticker symbol

    Returns:
        {"symbol": t, "institutional_holders": {...}}
    """
    if not symbol_name:
        raise ValueError("Symbol name is required.")
    t = symbol_name.strip().upper()
    data = yf.Ticker(t).get_institutional_holders()
    return {"symbol": t, "institutional_holders": data if data is not None else {}}


def get_mutualfund_holders(symbol_name: str) -> dict:
    """Fetch mutual fund holders information.

    Args:
        symbol_name: Stock ticker symbol

    Returns:
        {"symbol": t, "mutualfund_holders": {...}}
    """
    if not symbol_name:
        raise ValueError("Symbol name is required.")
    t = symbol_name.strip().upper()
    data = yf.Ticker(t).get_mutualfund_holders()
    return {"symbol": t, "mutualfund_holders": data if data is not None else {}}


def get_insider_purchases(symbol_name: str) -> dict:
    """Fetch insider purchase transactions.

    Args:
        symbol_name: Stock ticker symbol

    Returns:
        {"symbol": t, "insider_purchases": {...}}
    """
    if not symbol_name:
        raise ValueError("Symbol name is required.")
    t = symbol_name.strip().upper()
    data = yf.Ticker(t).get_insider_purchases()
    return {"symbol": t, "insider_purchases": data if data is not None else {}}


def get_insider_transactions(symbol_name: str) -> dict:
    """Fetch all insider transactions.

    Args:
        symbol_name: Stock ticker symbol

    Returns:
        {"symbol": t, "insider_transactions": {...}}
    """
    if not symbol_name:
        raise ValueError("Symbol name is required.")
    t = symbol_name.strip().upper()
    data = yf.Ticker(t).get_insider_transactions()
    return {"symbol": t, "insider_transactions": data if data is not None else {}}


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
        period: Period to fetch (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max) (default: 1d)
        interval: Data interval (1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h, 1d, 5d, 1wk, 1mo, 3mo) (default: 1d)
        adjust_mode: "auto", "back", or "none" for price adjustment (default: auto)
        prepost: Include pre/post market data (default: False)
        repair: Attempt to fix data errors (default: False)
        timeout: Request timeout in seconds (default: 10.0)

    Returns:
        On Success:
        {"symbol": ticker_symbol, "prices": {...}, "period": period, "interval": interval}
        On Failure:
        {"symbol": ticker_symbol, "prices": {}, "message": str(e)}
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
        return {"symbol": ticker_symbol, "prices": {}, "message": str(e)}


def get_last_close_price(symbol_name: str) -> dict:
    """Fetch the most recent close price for a ticker.

    Args:
        symbol_name: Stock ticker symbol (e.g., "AAPL", "RELIANCE.NS")

    Returns:
        On Success:
        {"symbol": ticker_symbol, "last_close_price": last_close_price, "date": date}
        On Failure:
        {"symbol": ticker_symbol, "last_close_price": None, "date": None, "error": error}
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
