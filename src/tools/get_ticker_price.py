import yfinance as yf
from langchain_core.tools import tool


@tool("get_ticker_price")
def get_ticker_price(ticker_symbol: str) -> float:
    """Return the latest close price (float) for the given ticker symbol.

    Input: ticker symbol string like 'AAPL' or 'BTC-USD'.
    Returns a float price on success or raises on error.
    """
    if not ticker_symbol:
        raise ValueError("no ticker provided")
    t = ticker_symbol.strip().upper()
    try:
        hist = yf.Ticker(t).history(period="1d")
        if hist.empty:
            raise RuntimeError(f"Ticker '{t}' not found or no recent data")
        price = float(hist["Close"].iloc[-1])
        return price
    except Exception as e:
        raise RuntimeError(f"Error fetching ticker '{t}': {e}") from e
