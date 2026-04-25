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
from sqlalchemy import func, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.price_bar_1d import PriceBar1d

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


async def upsert_bars(session: AsyncSession, in_equity_id: UUID, bars: list[dict[str, Any]]) -> int:
    if not bars:
        return 0
    table = PriceBar1d.__table__
    rows = [
        {
            "in_equity_id": in_equity_id,
            "trade_date": b["trade_date"],
            "open": b["open"],
            "high": b["high"],
            "low": b["low"],
            "close": b["close"],
            "volume": b["volume"],
        }
        for b in bars
    ]
    ins = pg_insert(table).values(rows)
    upsert = ins.on_conflict_do_update(
        index_elements=[table.c.in_equity_id, table.c.trade_date],
        set_={
            "open": ins.excluded.open,
            "high": ins.excluded.high,
            "low": ins.excluded.low,
            "close": ins.excluded.close,
            "volume": ins.excluded.volume,
            "updated_at": func.now(),
        },
    )
    await session.execute(upsert)
    return len(rows)


async def load_all_equities(session: AsyncSession) -> list[EquityRow]:
    result = await session.execute(text("SELECT id, symbol FROM in_equities ORDER BY symbol"))
    return [EquityRow(id=r[0], symbol=r[1]) for r in result.fetchall()]


async def backfill_two_years(
    session: AsyncSession,
    *,
    period: str = "2y",
    delay_seconds: float = 0.15,
    limit: Optional[int] = None,
) -> None:
    equities = await load_all_equities(session)
    if limit is not None:
        equities = equities[:limit]
    total = len(equities)
    for i, eq in enumerate(equities, start=1):
        ysym = to_yahoo_ns(eq.symbol)
        try:
            bars = await fetch_daily_history(ysym, period)
            n = await upsert_bars(session, eq.id, bars)
            await session.commit()
            logger.info("[%s/%s] %s (%s): upserted %s bars", i, total, eq.symbol, ysym, n)
        except Exception:
            await session.rollback()
            logger.exception("Failed equity %s (%s)", eq.symbol, ysym)
        if delay_seconds > 0 and i < total:
            await asyncio.sleep(delay_seconds)


async def refresh_recent_daily(
    session: AsyncSession,
    *,
    period: str = "14d",
    delay_seconds: float = 0.1,
    limit: Optional[int] = None,
) -> None:
    """
    Idempotent catch-up: re-fetch last N calendar days of daily bars and upsert.
    Covers weekends/holidays and missed scheduler runs.
    """
    equities = await load_all_equities(session)
    if limit is not None:
        equities = equities[:limit]
    total = len(equities)
    for i, eq in enumerate(equities, start=1):
        ysym = to_yahoo_ns(eq.symbol)
        try:
            bars = await fetch_daily_history(ysym, period)
            n = await upsert_bars(session, eq.id, bars)
            await session.commit()
            logger.info("[%s/%s] %s: upserted %s recent bars", i, total, eq.symbol, n)
        except Exception:
            await session.rollback()
            logger.exception("Failed equity %s", eq.symbol)
        if delay_seconds > 0 and i < total:
            await asyncio.sleep(delay_seconds)
