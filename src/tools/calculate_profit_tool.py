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
