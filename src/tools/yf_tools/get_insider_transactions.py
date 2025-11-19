import yfinance as yf
from langchain.tools import tool

from .utils import _df_to_dict_safe


@tool("get_insider_transactions")
def get_insider_transactions(symbol_name: str) -> dict:
    """Return insider transactions (sales, purchases, option exercises, etc.) for the given ticker."""
    if not symbol_name:
        raise ValueError("Symbol name is required.")
    t = symbol_name.strip().upper()
    try:
        df = yf.Ticker(t).get_insider_transactions(as_dict=False)
        return {"symbol": t, "insider_transactions": _df_to_dict_safe(df)}
    except Exception as e:
        raise RuntimeError(f"Error fetching insider transactions for '{t}': {e}") from e
