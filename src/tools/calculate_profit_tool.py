from langchain_core.tools import tool


def calculate_profit(quantity: float, average_price: float, current_price: float) -> dict:
    """Calculate profit or loss using quantity, purchase price, and current price.

    Args:
        quantity: Number of shares/units held
        average_price: Average purchase price per share
        current_price: Current market price per share

    Returns:
        dict: {"profit": float} - Profit or loss amount (negative for loss)
    """
    profit = (current_price - average_price) * quantity
    return {"profit": profit}


@tool
def calculate_profit_tool(quantity: float, average_price: float, current_price: float) -> dict:
    """Calculate profit or loss using quantity, purchase price, and current price.

    Use this tool when you need to calculate the profit/loss for a specific holding.

    Args:
        quantity: Number of shares/units held
        average_price: Average purchase price per share
        current_price: Current market price per share

    Returns:
        dict: {"profit": float} - Profit or loss amount (negative for loss)
    """
    return calculate_profit(quantity, average_price, current_price)
