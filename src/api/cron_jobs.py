"""API endpoints used by infrastructure cron jobs."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel

from src.dependencies import get_price_bars_1d_ingest_service
from src.services.price_bars_1d_ingest import PriceBars1DIngestService

router = APIRouter(prefix="/cron-jobs", tags=["cron-jobs"])


class DailyBarsCronResponse(BaseModel):
    ok: bool
    message: str
    period: str
    delay_seconds: float
    limit: int | None
    total_equities: int
    successful: int
    failed: int
    failed_symbols: list[str]
    rows_upserted: int


@router.post("/daily/", response_model=DailyBarsCronResponse, status_code=status.HTTP_200_OK)
async def trigger_daily_price_bars_refresh(
    service: Annotated[PriceBars1DIngestService, Depends(get_price_bars_1d_ingest_service)],
    period: str = Query("2d", description="yfinance lookback period"),
    delay: float = Query(0.0, ge=0.0, le=5.0, description="Ignored in batched mode; keep as 0"),
    limit: int | None = Query(None, ge=1, description="Optional symbol limit for partial runs"),
):
    result = await service.refresh_recent_daily(period=period, delay_seconds=delay, limit=limit)
    return DailyBarsCronResponse(
        ok=True,
        message="Daily price bars refresh completed.",
        period=period,
        delay_seconds=delay,
        limit=limit,
        total_equities=result.total_equities,
        successful=result.successful,
        failed=result.failed,
        failed_symbols=list(result.failed_symbols),
        rows_upserted=result.rows_upserted,
    )
