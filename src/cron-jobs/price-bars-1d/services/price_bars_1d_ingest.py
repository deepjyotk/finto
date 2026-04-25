"""Fetch daily bars from Yahoo via yfinance and upsert into price_bars_1d."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID

import pandas as pd
import yfinance as yf
from sqlalchemy.ext.asyncio import AsyncSession

from src.repositories.price_bars_1d_repo import PriceBars1DRepository

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EquityRow:
    id: UUID
    symbol: str


def to_yahoo_ns(symbol: str) -> str:
    s = symbol.upper().strip()
    return s if s.endswith(".NS") else f"{s}.NS"


def _fetch_daily_history_sync(yahoo_symbol: str, period: str) -> list[dict[str, Any]]:
    """
    Return one dict per trading day in Yahoo's daily series (weekends/holidays omitted).
    """
    ticker = yf.Ticker(yahoo_symbol)
    hist = ticker.history(period=period, interval="1d", auto_adjust=True)
    if hist is None or hist.empty:
        return []
    out: list[dict[str, Any]] = []
    for ts, row in hist.iterrows():
        if hasattr(ts, "date"):
            td: date = ts.date()  # type: ignore[union-attr]
        else:
            td = pd.Timestamp(ts).date()
        o, h, l_, c, v = (
            row.get("Open"),
            row.get("High"),
            row.get("Low"),
            row.get("Close"),
            row.get("Volume"),
        )
        out.append(
            {
                "trade_date": td,
                "open": None if pd.isna(o) else Decimal(str(round(float(o), 6))),
                "high": None if pd.isna(h) else Decimal(str(round(float(h), 6))),
                "low": None if pd.isna(l_) else Decimal(str(round(float(l_), 6))),
                "close": None if pd.isna(c) else Decimal(str(round(float(c), 6))),
                "volume": None if pd.isna(v) else int(v),
            }
        )
    return out


async def fetch_daily_history(yahoo_symbol: str, period: str) -> list[dict[str, Any]]:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _fetch_daily_history_sync, yahoo_symbol, period)


class PriceBars1DIngestService:
    """Orchestrates daily bar fetching and DB upserts."""

    def __init__(self, repo: PriceBars1DRepository) -> None:
        self._repo = repo

    async def _load_all_equities(self) -> list[EquityRow]:
        rows = await self._repo.load_all_equities()
        return [EquityRow(id=row[0], symbol=row[1]) for row in rows]

    async def backfill_two_years(
        self,
        *,
        period: str = "2y",
        delay_seconds: float = 0.15,
        limit: Optional[int] = None,
    ) -> None:
        equities = await self._load_all_equities()
        if limit is not None:
            equities = equities[:limit]
        total = len(equities)
        for i, eq in enumerate(equities, start=1):
            ysym = to_yahoo_ns(eq.symbol)
            try:
                bars = await fetch_daily_history(ysym, period)
                count = await self._repo.upsert_bars(eq.id, bars)
                await self._repo.commit()
                logger.info("[%s/%s] %s (%s): upserted %s bars", i, total, eq.symbol, ysym, count)
            except Exception:
                await self._repo.rollback()
                logger.exception("Failed equity %s (%s)", eq.symbol, ysym)
            if delay_seconds > 0 and i < total:
                await asyncio.sleep(delay_seconds)

    async def refresh_recent_daily(
        self,
        *,
        period: str = "14d",
        delay_seconds: float = 0.1,
        limit: Optional[int] = None,
    ) -> None:
        """
        Idempotent catch-up: re-fetch last N calendar days of daily bars and upsert.
        Covers weekends/holidays and missed scheduler runs.
        """
        equities = await self._load_all_equities()
        if limit is not None:
            equities = equities[:limit]
        total = len(equities)
        for i, eq in enumerate(equities, start=1):
            ysym = to_yahoo_ns(eq.symbol)
            try:
                bars = await fetch_daily_history(ysym, period)
                count = await self._repo.upsert_bars(eq.id, bars)
                await self._repo.commit()
                logger.info("[%s/%s] %s: upserted %s recent bars", i, total, eq.symbol, count)
            except Exception:
                await self._repo.rollback()
                logger.exception("Failed equity %s", eq.symbol)
            if delay_seconds > 0 and i < total:
                await asyncio.sleep(delay_seconds)


async def backfill_two_years(
    session: AsyncSession,
    *,
    period: str = "2y",
    delay_seconds: float = 0.15,
    limit: Optional[int] = None,
) -> None:
    """Backward-compatible function wrapper used by the CLI script."""
    repo = PriceBars1DRepository(session)
    service = PriceBars1DIngestService(repo)
    await service.backfill_two_years(period=period, delay_seconds=delay_seconds, limit=limit)


async def refresh_recent_daily(
    session: AsyncSession,
    *,
    period: str = "14d",
    delay_seconds: float = 0.1,
    limit: Optional[int] = None,
) -> None:
    """Backward-compatible function wrapper used by the CLI script."""
    repo = PriceBars1DRepository(session)
    service = PriceBars1DIngestService(repo)
    await service.refresh_recent_daily(period=period, delay_seconds=delay_seconds, limit=limit)
