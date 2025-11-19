import yfinance as yf
from langchain.tools import tool

from src.utils.data_frame import _df_to_dict_safe


@tool
def get_capital_gains(symbol_name: str, period: str = "max") -> dict:
    """Fetch capital gain distribution history (for funds/ETFs)."""
    if not symbol_name:
        raise ValueError("Symbol name is required.")
    t = symbol_name.strip().upper()
    try:
        series = yf.Ticker(t).get_capital_gains(period=period)
        return {"symbol": t, "capital_gains": _df_to_dict_safe(series)}
    except Exception as e:
        raise RuntimeError(f"Error fetching capital gains for {t}: {e}") from e
