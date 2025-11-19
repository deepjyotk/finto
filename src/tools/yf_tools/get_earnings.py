import yfinance as yf
from langchain.tools import tool

from src.utils.data_frame import _df_to_dict_safe


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
