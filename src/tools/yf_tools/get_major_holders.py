import yfinance as yf
from langchain.tools import tool


@tool("get_major_holders")
def get_major_holders(symbol_name: str) -> dict:
    """Return major shareholders for the given symbol name."""
    if not symbol_name:
        raise ValueError("Symbol name is required.")
    t = symbol_name.strip().upper()
    try:
        data = yf.Ticker(t).get_major_holders(as_dict=True)
        return {"symbol": t, "major_holders": data}
    except Exception as e:
        raise RuntimeError(f"Error fetching major holders for '{t}': {e}") from e
