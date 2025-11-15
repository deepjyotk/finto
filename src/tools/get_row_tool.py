# import pandas as pd
# from langchain_core.tools import tool

# # 1️⃣ Load your Excel file
# df = pd.read_excel("portfolio.xlsx")


# @tool("get_holding_by_symbol")
# def get_holding_by_symbol(symbol_name: str) -> dict:
#     """Return the portfolio holding snapshot for the given symbol name (case-insensitive).
#     Fields: TickerName, ISIN, Sector, Quantity Available, Quantity Discrepant,
#     Quantity Long Term, Quantity Pledged (Margin), Quantity Pledged (Loan),
#     Average Price, Previous Closing Price, Unrealized P&L, Unrealized P&L Pct."""
#     row = df[df["Symbol"].str.casefold() == symbol_name.casefold()].iloc[0].to_dict()
#     return row
