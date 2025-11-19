import yfinance as yf
from langchain.tools import tool

from src.utils.data_frame import _df_to_dict_safe


@tool("get_institutional_holders")
def get_institutional_holders(symbol_name: str) -> dict:
    """Return institutional holders for the given symbol name."""
    if not symbol_name:
        raise ValueError("Symbol name is required.")
    t = symbol_name.strip().upper()
    try:
        df = yf.Ticker(t).get_institutional_holders(as_dict=False)
        return {"symbol": t, "institutional_holders": _df_to_dict_safe(df)}
    except Exception as e:
        raise RuntimeError(f"Error fetching institutional holders for '{t}': {e}") from e
