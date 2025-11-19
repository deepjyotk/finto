import yfinance as yf
from langchain.tools import tool

from .utils import _df_to_dict_safe


@tool("get_mutualfund_holders")
def get_mutualfund_holders(symbol_name: str) -> dict:
    """Return mutual fund holders for the given symbol name."""
    if not symbol_name:
        raise ValueError("Symbol name is required.")
    t = symbol_name.strip().upper()
    try:
        df = yf.Ticker(t).get_mutualfund_holders(as_dict=False)
        return {"symbol": t, "mutualfund_holders": _df_to_dict_safe(df)}
    except Exception as e:
        raise RuntimeError(f"Error fetching mutual fund holders for '{t}': {e}") from e
