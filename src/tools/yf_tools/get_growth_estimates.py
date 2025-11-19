import yfinance as yf
from langchain.tools import tool

from .utils import _df_to_dict_safe


@tool("get_growth_estimates")
def get_growth_estimates(symbol_name: str) -> dict:
    """Fetch growth estimates (stock, sector, industry, index comparisons)."""
    if not symbol_name:
        raise ValueError("Symbol name is required.")
    t = symbol_name.strip().upper()
    try:
        data = yf.Ticker(t).get_growth_estimates(as_dict=True)
        return {"symbol": t, "growth_estimates": _df_to_dict_safe(data)}
    except Exception as e:
        raise RuntimeError(f"Error fetching growth estimates for {t}: {e}") from e
