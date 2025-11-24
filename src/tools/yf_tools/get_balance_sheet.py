import yfinance as yf
from langchain.tools import tool

from src.utils.data_frame import _df_to_dict_safe
from src.core.json_logging import logger_for

logger = logger_for(__name__)


@tool("get_balance_sheet")
def get_balance_sheet(symbol_name: str, freq: str = "yearly", pretty: bool = False) -> dict:
    """Fetch balance sheet (yearly or quarterly)."""
    if not symbol_name:
        raise ValueError("Symbol name is required.")
    t = symbol_name.strip().upper()
    try:
        df = yf.Ticker(t).get_balance_sheet(as_dict=False, pretty=pretty, freq=freq)

        dict_result = _df_to_dict_safe(df)
        logger.info(f"Tool: get_balance_sheet, Symbol: {t}, Balance sheet: {dict_result}")
        return {"symbol": t, "balance_sheet": dict_result}
    except Exception as e:
        raise RuntimeError(f"Error fetching balance sheet for {t}: {e}") from e
