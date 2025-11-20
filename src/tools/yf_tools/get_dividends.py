import yfinance as yf
from langchain.tools import tool

from src.utils.data_frame import _df_to_dict_safe


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
