import yfinance as yf
from langchain.tools import tool

from src.utils.data_frame import _df_to_dict_safe


@tool("get_earnings_estimate")
def get_earnings_estimate(symbol_name: str) -> dict:
    """Fetch earnings estimates for upcoming quarters and years."""
    if not symbol_name:
        raise ValueError("Symbol name is required.")
    t = symbol_name.strip().upper()
    try:
        data = yf.Ticker(t).get_earnings_estimate(as_dict=True)
        return {"symbol": t, "earnings_estimate": _df_to_dict_safe(data)}
    except Exception as e:
        raise RuntimeError(f"Error fetching earnings estimate for {t}: {e}") from e
