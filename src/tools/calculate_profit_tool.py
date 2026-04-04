def calculate_profit_or_loss(
    quantity: float, average_price: float, current_price: float
) -> dict:
    """Calculate profit or loss using quantity, purchase price, and current price.

    Args:
        quantity: Number of shares/units held
        average_price: Average purchase price per share
        current_price: Current market price per share

    Returns:
        dict: {"profit_or_loss": float} - Profit or loss amount (negative for loss)
    """
    quantity = float(quantity)
    average_price = float(average_price)
    current_price = float(current_price)
    profit_or_loss = (current_price - average_price) * quantity
    return {"profit_or_loss": profit_or_loss}
