import yfinance as yf
from langchain.tools import tool

from .utils import _df_to_dict_safe


@tool
def get_eps_revisions(symbol_name: str) -> dict:
    """Fetch EPS revisions (up/down changes last 7 & 30 days)."""
    if not symbol_name:
        raise ValueError("Symbol name is required.")
    t = symbol_name.strip().upper()
    try:
        data = yf.Ticker(t).get_eps_revisions(as_dict=True)
        return {"symbol": t, "eps_revisions": _df_to_dict_safe(data)}
    except Exception as e:
        raise RuntimeError(f"Error fetching EPS revisions for {t}: {e}") from e
