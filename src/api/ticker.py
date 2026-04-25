"""Public ticker / stock profile endpoint."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.schemas.ticker import StockSearchResult, TickerResponse
from src.core.db import get_session
from src.services.stock_search import search_stocks
from src.services.ticker_service import TickerService

router = APIRouter(prefix="/ticker", tags=["ticker"])


def _get_ticker_service(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> TickerService:
    return TickerService(session)


@router.get("/search", response_model=list[StockSearchResult])
async def search_tickers(
    q: str = Query(
        ..., min_length=1, max_length=100, description="Search query: symbol or company name"
    ),
    limit: int = Query(10, ge=1, le=30, description="Max results"),
):
    """
    Fast autocomplete search over all NSE stocks.

    Matches symbol prefix first, then symbol substring, then company name substring.
    Results come from an in-memory cache populated at startup — no DB call per request.

    Example: GET /api/v1/ticker/search?q=reli&limit=10
    """
    matches = search_stocks(q, limit=limit)
    return [StockSearchResult(**m) for m in matches]


@router.get("/{symbol}", response_model=TickerResponse)
async def get_ticker(
    symbol: str,
    svc: Annotated[TickerService, Depends(_get_ticker_service)],
    price_period: str = Query(
        "1y",
        description=(
            "Chart lookback. Default: DB-backed daily bars from price_bars_1d: "
            "1mo, 6mo, 1y, max (max = ~2y of table data). "
            "Legacy 3y/5y/… map to max. "
            "Set TICKER_USE_YFINANCE_FOR_PRICES=1 to use yfinance for price_history: "
            "1d 5d 1mo 3mo 6mo 1y 2y 5y 10y ytd max"
        ),
    ),
    price_interval: str = Query(
        "1d",
        description=(
            "Candle interval for price chart. With DB (default) only 1d data exists; "
            "other values are ignored. With yfinance flag: 1m 2m 5m 15m 30m 60m 90m 1h 1d 5d 1wk 1mo 3mo"
        ),
    ),
    annual_periods: int = Query(10, ge=1, le=20, description="Number of annual periods"),
    quarterly_periods: int = Query(12, ge=1, le=20, description="Number of quarterly periods"),
):
    """
    Public stock ticker page data — no auth required.

    Returns company info, key ratios, OHLCV price history (for chart),
    annual P&L table, and quarterly P&L table.

    Example: GET /api/v1/ticker/RELIANCE
    """
    data = await svc.get_ticker(
        symbol,
        price_period=price_period,
        price_interval=price_interval,
        annual_periods=annual_periods,
        quarterly_periods=quarterly_periods,
    )
    if data is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No data found for symbol '{symbol.upper()}'.",
        )
    return TickerResponse(**data)
