from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.db import get_session

router = APIRouter(prefix="/dev", tags=["dev"])


class DevPriceBarQueryResponse(BaseModel):
    symbol: str
    company_name: str
    open: Decimal | None
    high: Decimal | None
    low: Decimal | None
    close: Decimal | None
    volume: int | None


@router.get("/query/price-bar", response_model=DevPriceBarQueryResponse | None)
async def query_price_bar_by_symbol_and_trade_date(
    symbol: Annotated[str, Query(min_length=1, description="NSE symbol, e.g. RELIANCE")],
    trade_date: Annotated[date, Query(description="Trade date in YYYY-MM-DD format")],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    result = await session.execute(
        text(
            """
            SELECT
                ie.symbol,
                ie.company_name,
                pb.open,
                pb.high,
                pb.low,
                pb.close,
                pb.volume
            FROM in_equities AS ie
            JOIN price_bars_1d AS pb
              ON pb.in_equity_id = ie.id
            WHERE ie.symbol = split_part(upper(:symbol), '.', 1)
              AND pb.trade_date = :trade_date
            LIMIT 1
            """
        ),
        {"symbol": symbol.strip(), "trade_date": trade_date},
    )
    row = result.fetchone()
    if row is None:
        return None

    return DevPriceBarQueryResponse(
        symbol=row.symbol,
        company_name=row.company_name,
        open=row.open,
        high=row.high,
        low=row.low,
        close=row.close,
        volume=row.volume,
    )
