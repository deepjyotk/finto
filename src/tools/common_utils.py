import json
from functools import lru_cache
from pathlib import Path

INDIAN_EXCHANGE_SUFFIXES = {"NS", "BO"}

_US_REGISTRY_PATH = Path(__file__).resolve().parent.parent / "data" / "us_sec_tickers.json"


@lru_cache(maxsize=1)
def _load_us_sec_tickers() -> frozenset[str]:
    """Bare US tickers from SEC populate script; empty if registry missing."""
    try:
        data = json.loads(_US_REGISTRY_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return frozenset()
    if not isinstance(data, list):
        return frozenset()
    return frozenset(str(s).strip().upper() for s in data if s)


def is_us_sec_symbol(symbol: str) -> bool:
    """True when *symbol* (bare or with Indian suffix stripped) is in the US SEC registry."""
    s = symbol.strip().upper()
    if "." in s:
        base, suffix = s.rsplit(".", 1)
        if suffix in INDIAN_EXCHANGE_SUFFIXES:
            s = base
    return s in _load_us_sec_tickers()


def normalize_symbol(symbol: str, default_exchange: str = "NS") -> str:
    """
    Normalize a stock symbol to a Yahoo-ready format.

    Indian bare tickers get ``.{default_exchange}`` (default ``.NS``).
    US SEC registry tickers stay bare (no ``.NS``).
    Existing ``.NS`` / ``.BO`` suffixes are preserved.
    """
    if not symbol:
        raise ValueError("Symbol is required")

    s = symbol.strip().upper()

    # If exchange suffix already exists, keep it
    if "." in s and s.split(".")[1] in INDIAN_EXCHANGE_SUFFIXES:
        return s

    # US tickers must not get an Indian exchange suffix
    if is_us_sec_symbol(s):
        return s

    # Default to adding the exchange suffix (India / NSE)
    return f"{s}.{default_exchange}"
