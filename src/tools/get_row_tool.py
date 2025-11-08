import pandas as pd
from langchain_core.tools import tool

# 1️⃣ Load your Excel file
df = pd.read_excel("portfolio.xlsx")


@tool
def get_entire_row(symbol_name: str) -> dict:
    """Extracts the entire row from the portfolio containing details regarding the stock symbol"""
    return df[df["Symbol"] == symbol_name].iloc[0].to_dict()
