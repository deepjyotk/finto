from __future__ import annotations

from enum import Enum
from typing import Literal, Optional

import pandas as pd
import yfinance as yf
from langchain_core.tools import tool
from pydantic import BaseModel, Field, field_validator


# ───────────────────────────── Enums ───────────────────────────── #


class AdjustMode(str, Enum):
    """How to adjust prices for corporate actions."""

    AUTO = "auto"   # auto_adjust=True (default)
    BACK = "back"   # back_adjust=True
    NONE = "none"   # no adjustment


# ───────────────────────────── Input model ───────────────────────────── #


class GetTickerPriceInput(BaseModel):
    """
    Input for the get_ticker_price tool.

    This tool is intended **only for Indian equity symbols** on NSE/BSE.
    """

    ticker_symbol: str = Field(
        ...,
        description=(
            "Indian stock ticker symbol on NSE/BSE, e.g. "
            "'RELIANCE.NS', 'TCS.NS', 'HDFCBANK.NS', 'SBIN.NS', 'INFY.NS', "
            "'RELIANCE.BO', etc. Must end with '.NS' (NSE) or '.BO' (BSE)."
        ),
    )

    period: Literal["1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "ytd", "max"] = Field(
        default="1d",
        description=(
            "How far back to look when fetching data. "
            "Valid periods: 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max. "
            "Returns a dict mapping dates (YYYY-MM-DD) to close prices for all periods."
        ),
    )

    interval: Literal["1m", "2m", "5m", "15m", "30m", "60m", "90m", "1h", "1d", "5d", "1wk", "1mo", "3mo"] = Field(
        default="1d",
        description=(
            "Data interval/bar size. Valid intervals: "
            "1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h, 1d, 5d, 1wk, 1mo, 3mo. "
            "Note: Intraday intervals (1m-1h) cannot extend beyond last 60 days."
        ),
    )

    adjust_mode: AdjustMode = Field(
        default=AdjustMode.AUTO,
        description=(
            "Price adjustment mode: "
            "'auto' = auto_adjust=True (default), "
            "'back' = back_adjust=True, "
            "'none' = no adjustment (raw prices)."
        ),
    )

    prepost: bool = Field(
        default=False,
        description=(
            "Include pre-market and post-market data in results. "
            "Default: False (regular trading hours only)."
        ),
    )

    repair: bool = Field(
        default=False,
        description=(
            "Attempt to fix price errors in Yahoo data (100x errors, missing data, "
            "bad dividend adjustments). Default: False."
        ),
    )

    timeout: Optional[float] = Field(
        default=10.0,
        description=(
            "Timeout for the request in seconds. "
            "Default: 10.0 seconds. Set to None for no timeout."
        ),
    )

    @field_validator("ticker_symbol")
    @classmethod
    def normalize_ticker(cls, v: str) -> str:
        v = v.strip().upper()
        if not v:
            raise ValueError("ticker_symbol must be non-empty")
        if not (v.endswith(".NS") or v.endswith(".BO")):
            raise ValueError(
                "Only Indian equities are supported. "
                "ticker_symbol must end with '.NS' (NSE) or '.BO' (BSE), "
                "e.g. 'RELIANCE.NS' or 'TCS.NS'."
            )
        return v


# ───────────────────────────── Tool ───────────────────────────── #


@tool(
    args_schema=GetTickerPriceInput,
)
def get_ticker_price(
    ticker_symbol: str,
    period: Literal["1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "ytd", "max"] = "1d",
    interval: Literal["1m", "2m", "5m", "15m", "30m", "60m", "90m", "1h", "1d", "5d", "1wk", "1mo", "3mo"] = "1d",
    adjust_mode: AdjustMode = AdjustMode.AUTO,
    prepost: bool = False,
    repair: bool = False,
    timeout: Optional[float] = 10.0,
) -> dict[str, float]:
    """
    Return close prices for the given **Indian** ticker symbol.

    - Only Indian equities on NSE/BSE are supported (tickers ending with '.NS' or '.BO').
    - Looks back over `period` (default: "1d") with data interval `interval` (default: "1d").
    - Always returns a dict mapping dates (YYYY-MM-DD) to close prices, regardless of period.
    - Applies price adjustment based on `adjust_mode`.
    - Supports pre/post market data, price repair, and custom timeout.
    
    Raises RuntimeError on failure.
    """
    t = ticker_symbol

    auto_adjust = adjust_mode == AdjustMode.AUTO
    back_adjust = adjust_mode == AdjustMode.BACK

    try:
        hist = yf.Ticker(t).history(
            period=period,
            interval=interval,
            auto_adjust=auto_adjust,
            back_adjust=back_adjust,
            prepost=prepost,
            repair=repair,
            timeout=timeout,
        )

        if hist.empty:
            raise RuntimeError(f"Ticker '{t}' not found on NSE/BSE or no recent data")

        # Always return dict mapping dates to close prices
        prices_dict: dict[str, float] = {}
        for idx, close_price in hist["Close"].items():
            # Convert pandas Timestamp/DatetimeIndex to date string (YYYY-MM-DD)
            # hist.index is a DatetimeIndex, so idx is a Timestamp
            date_str = pd.Timestamp(idx).date().isoformat()
            prices_dict[date_str] = float(close_price)
        
        return prices_dict

    except Exception as e:
        raise RuntimeError(f"Error fetching Indian ticker '{t}': {e}") from e
