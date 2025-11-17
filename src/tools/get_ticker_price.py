import yfinance as yf
from langchain_core.tools import tool
from typing import List, Union
from concurrent.futures import ThreadPoolExecutor

def _get_single_ticker_price(ticker_symbol: str) -> Union[float, str]:
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
        return f"Data not available for {t}"

@tool("get_ticker_prices")
def get_ticker_prices(ticker_symbols: List[str]) -> List[Union[float, str]]:
    """Return the latest close prices for a list of ticker symbols."""
    with ThreadPoolExecutor() as executor:
        prices = list(executor.map(_get_single_ticker_price, ticker_symbols))
    return prices
