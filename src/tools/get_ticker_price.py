import yfinance as yf
from langchain_core.tools import tool
import json


@tool("get_ticker_price")
def get_ticker_price(ticker_symbol: str) -> str:
    """Return latest close price for a ticker symbol.

    Input: ticker symbol like 'AAPL' or 'BTC-USD'.
    Robust behavior: NEVER raises for missing/invalid tickers; instead returns a JSON string:
      {"symbol": <str>, "price": <float|null>, "status": "ok|not_found|error", "reason": <str|optional>}.
    """
    if not ticker_symbol:
        return json.dumps({"symbol": None, "price": None, "status": "error", "reason": "no ticker provided"})
    t = ticker_symbol.strip().upper()
    if t.startswith("$"):
        t = t[1:]
    try:
        hist = yf.Ticker(t).history(period="1d")
        if hist.empty or "Close" not in hist.columns:
            return json.dumps({"symbol": t, "price": None, "status": "not_found", "reason": "no recent data or delisted"})
        price = float(hist["Close"].iloc[-1])
        return json.dumps({"symbol": t, "price": price, "status": "ok"})
    except Exception as e:
        return json.dumps({"symbol": t, "price": None, "status": "error", "reason": str(e)})
