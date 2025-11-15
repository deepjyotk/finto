import pandas as pd
from langchain_core.tools import tool
import yfinance as yf

df = pd.read_excel("portfolio.xlsx")

# 1️⃣ Calculate total investment per stock
@tool
def calculate_total_investment_in_specific_stock(symbol_name: str) -> dict:
    """Calculates the total invested amount in a specific stock using the symbol name"""
    row = df[df["Symbol"] == symbol_name].iloc[0]
    total_investment = row["Quantity Available"] * row["Average Price"]
    return {"symbol": symbol_name, "total_investment": total_investment}


# 2️⃣ Calculate portfolio’s total current value
# @tool
# def calculate_total_portfolio_value() -> dict:
#     """Calculates current total market value of the portfolio using live prices."""
#     symbols = df["Symbol"].tolist()
#     prices = yf.download(symbols, period="1d")["Close"].iloc[-1].to_dict()
#     df["Current Price"] = df["Symbol"].map(prices)
#     df["Current Value"] = df["Quantity"] * df["Current Price"]
#     total_value = df["Current Value"].sum()
#     return {"total_portfolio_value": total_value}


# # 3️⃣ Calculate portfolio’s unrealized profit or loss
# @tool
# def calculate_unrealized_pnl() -> dict:
#     """Calculates total unrealized profit or loss for the portfolio."""
#     df["PnL"] = (df["Current Price"] - df["Average Price"]) * df["Quantity"]
#     total_pnl = df["PnL"].sum()
#     return {"unrealized_pnl": total_pnl}


# 4️⃣ Calculate portfolio weight for each stock
@tool
def get_portfolio_weights() -> dict:
    """Returns the portfolio weight (%) of each stock based on its current value."""
    df["Current Value"] = df["Quantity"] * df["Current Price"]
    total_value = df["Current Value"].sum()
    df["Weight (%)"] = (df["Current Value"] / total_value) * 100
    weights = df[["Symbol", "Weight (%)"]].set_index("Symbol")["Weight (%)"].to_dict()
    return {"portfolio_weights": weights}


# 5️⃣ Calculate ROI (Return on Investment) for each stock
@tool
def calculate_roi(symbol_name: str) -> dict:
    """Computes ROI (%) for a given stock."""
    row = df[df["Symbol"] == symbol_name].iloc[0]
    roi = ((row["Current Price"] - row["Average Price"]) / row["Average Price"]) * 100
    return {"symbol": symbol_name, "ROI (%)": roi}