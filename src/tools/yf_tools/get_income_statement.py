from pathlib import Path

import pandas as pd
import yfinance as yf
from langchain.tools import tool

from src.utils.data_frame import _df_to_dict_safe


@tool("get_income_statement")
def get_income_statement(symbol_name: str, freq: str = "yearly", pretty: bool = False) -> dict:
    """Fetch income statement (yearly, quarterly, or trailing)."""
    if not symbol_name:
        raise ValueError("Symbol name is required.")
    t = symbol_name.strip().upper()
    try:
        df = yf.Ticker(t).get_income_stmt(as_dict=False, pretty=pretty, freq=freq)
        cols_2022 = [c for c in df.columns if pd.to_datetime(str(c)).year == 2022]
        pd.set_option("display.float_format", "{:,.0f}".format)
        df_2022 = df[cols_2022]
        if df is not None and not df.empty:
            filepath = (
                Path(__file__).parent.parent.parent.parent
                / f"income_statement_{t}_{freq}_2022.xlsx"
            )
            df_2022.to_excel(filepath)
        return {"symbol": t, "income_statement": _df_to_dict_safe(df)}
    except Exception as e:
        raise RuntimeError(f"Error fetching income statement for {t}: {e}") from e
