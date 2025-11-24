import pandas as pd
from langchain_core.tools import tool


@tool
def calculate_profit(quantity: float, average_price: float, current_price: float) -> dict:
    """Calculate profit or loss using quantity, purchase price, and current price."""
    profit = (current_price - average_price) * quantity
    return {"profit": profit}
