import yfinance as yf
from langchain.tools import tool

from .utils import _df_to_dict_safe


@tool("get_balance_sheet")
def get_balance_sheet(symbol_name: str, freq: str = "yearly", pretty: bool = False) -> dict:
    """Fetch balance sheet (yearly or quarterly)."""
    if not symbol_name:
        raise ValueError("Symbol name is required.")
    t = symbol_name.strip().upper()
    try:
        df = yf.Ticker(t).get_balance_sheet(as_dict=False, pretty=pretty, freq=freq)
        return {"symbol": t, "balance_sheet": _df_to_dict_safe(df)}
    except Exception as e:
        raise RuntimeError(f"Error fetching balance sheet for {t}: {e}") from e
