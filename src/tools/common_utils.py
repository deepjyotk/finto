INDIAN_EXCHANGE_SUFFIXES = {"NS", "BO"}


def normalize_symbol(symbol: str, default_exchange: str = "NS") -> str:
    """
    Normalize a stock symbol to a standard format.

    Args:
        symbol: Stock symbol to normalize
        default_exchange: Default exchange to use if not specified

    Returns:
        Normalized stock symbol
    """
    if not symbol:
        raise ValueError("Symbol is required")

    s = symbol.strip().upper()

    # If exchange suffix already exists, keep it
    if "." in s and s.split(".")[1] in INDIAN_EXCHANGE_SUFFIXES:
        return s

    # Default to adding the exchange suffix
    return f"{s}.{default_exchange}"
