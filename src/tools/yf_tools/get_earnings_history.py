import yfinance as yf
from langchain.tools import tool

from src.utils.data_frame import _df_to_dict_safe


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
