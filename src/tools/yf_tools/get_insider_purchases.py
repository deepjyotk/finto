import yfinance as yf
from langchain.tools import tool

from src.utils.data_frame import _df_to_dict_safe


@tool("get_insider_purchases")
def get_insider_purchases(symbol_name: str) -> dict:
    """Return insider purchase transactions for the given ticker."""
    if not symbol_name:
        raise ValueError("Symbol name is required.")
    t = symbol_name.strip().upper()
    try:
        df = yf.Ticker(t).get_insider_purchases(as_dict=False)
        return {"symbol": t, "insider_purchases": _df_to_dict_safe(df)}
    except Exception as e:
        raise RuntimeError(f"Error fetching insider purchases for '{t}': {e}") from e
