import yfinance as yf
from langchain_core.tools import tool

@tool
def get_ticker_price(ticker: str) -> str:
    """Return the latest close price for the given ticker symbol.

    Input: ticker symbol string like 'AAPL' or 'BTC-USD'.
    Output: short string with the latest close price or an error message.
    """
    if not ticker:
        return "Error: no ticker provided"
    t = ticker.strip().upper()
    try:
        hist = yf.Ticker(t).history(period="1d")
        if hist.empty:
            return f"Ticker '{t}' not found or no recent data"
        price = float(hist["Close"].iloc[-1])
        return f"{t} price: {price:.2f} USD"
    except Exception as e:
        return f"Error fetching ticker '{t}': {e}"