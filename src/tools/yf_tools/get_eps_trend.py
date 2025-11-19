import yfinance as yf
from langchain.tools import tool

from .utils import _df_to_dict_safe


@tool("get_eps_trend")
def get_eps_trend(symbol_name: str) -> dict:
    """Fetch historical EPS trend data (current vs 7, 30, 60, 90 days ago)."""
    if not symbol_name:
        raise ValueError("Symbol name is required.")
    t = symbol_name.strip().upper()
    try:
        data = yf.Ticker(t).get_eps_trend(as_dict=True)
        return {"symbol": t, "eps_trend": _df_to_dict_safe(data)}
    except Exception as e:
        raise RuntimeError(f"Error fetching EPS trend for {t}: {e}") from e
