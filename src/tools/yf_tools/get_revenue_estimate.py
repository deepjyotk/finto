import yfinance as yf
from langchain.tools import tool

from .utils import _df_to_dict_safe


@tool("get_revenue_estimate")
def get_revenue_estimate(symbol_name: str) -> dict:
    """Fetch revenue estimates for upcoming quarters and years."""
    if not symbol_name:
        raise ValueError("Symbol name is required.")
    t = symbol_name.strip().upper()
    try:
        data = yf.Ticker(t).get_revenue_estimate(as_dict=True)
        return {"symbol": t, "revenue_estimate": _df_to_dict_safe(data)}
    except Exception as e:
        raise RuntimeError(f"Error fetching revenue estimate for {t}: {e}") from e
