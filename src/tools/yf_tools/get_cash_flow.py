import yfinance as yf
from langchain.tools import tool

from src.utils.data_frame import _df_to_dict_safe


@tool("get_cash_flow")
def get_cash_flow(symbol_name: str, freq: str = "yearly", pretty: bool = False) -> dict:
    """Fetch cash flow statement (yearly or quarterly)."""
    if not symbol_name:
        raise ValueError("Symbol name is required.")
    t = symbol_name.strip().upper()
    try:
        df = yf.Ticker(t).get_cash_flow(as_dict=False, pretty=pretty, freq=freq)
        return {"symbol": t, "cash_flow": _df_to_dict_safe(df)}
    except Exception as e:
        raise RuntimeError(f"Error fetching cash flow for {t}: {e}") from e
