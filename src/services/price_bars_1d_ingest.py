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
_YF_BATCH_SIZE = 250


@dataclass(frozen=True)
class EquityRow:
    id: UUID
    symbol: str


@dataclass(frozen=True)
class RefreshRecentDailyResult:
    """Per-run stats for refresh_recent_daily (batched yfinance + DB upsert)."""

    total_equities: int
    successful: int
    failed: int
    failed_symbols: tuple[str, ...]
    rows_upserted: int


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


def _normalize_hist_to_bars(hist: pd.DataFrame) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for ts, row in hist.iterrows():
        td = ts.date() if hasattr(ts, "date") else pd.Timestamp(ts).date()
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


def _fetch_daily_history_batch_sync(
    yahoo_symbols: list[str], period: str
) -> dict[str, list[dict[str, Any]]]:
    if not yahoo_symbols:
        return {}

    hist = yf.download(
        tickers=" ".join(yahoo_symbols),
        period=period,
        interval="1d",
        auto_adjust=True,
        group_by="ticker",
        threads=True,
        progress=False,
    )
    if hist is None or hist.empty:
        return {sym: [] for sym in yahoo_symbols}

    out: dict[str, list[dict[str, Any]]] = {}
    # Multiple tickers -> MultiIndex columns: (ticker, field)
    if isinstance(hist.columns, pd.MultiIndex):
        for sym in yahoo_symbols:
            if sym not in hist.columns.get_level_values(0):
                out[sym] = []
                continue
            one = hist[sym].dropna(how="all")
            out[sym] = [] if one.empty else _normalize_hist_to_bars(one)
        return out

    # Single ticker fallback.
    return {yahoo_symbols[0]: _normalize_hist_to_bars(hist.dropna(how="all"))}


async def fetch_daily_history_batch(
    yahoo_symbols: list[str], period: str
) -> dict[str, list[dict[str, Any]]]:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _fetch_daily_history_batch_sync, yahoo_symbols, period)


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
        period: str = "2d",
        delay_seconds: float = 0.0,
        limit: Optional[int] = None,
    ) -> RefreshRecentDailyResult:
        """
        Idempotent catch-up: re-fetch last N calendar days of daily bars and upsert.
        Covers weekends/holidays and missed scheduler runs.
        """
        equities = await self._load_all_equities()
        if limit is not None:
            equities = equities[:limit]
        if not equities:
            logger.info("No equities found for refresh.")
            return RefreshRecentDailyResult(0, 0, 0, (), 0)

        if delay_seconds > 0:
            logger.warning("delay_seconds is ignored in batched refresh mode.")

        total = len(equities)
        total_upserted = 0
        failed_set: set[str] = set()
        for start in range(0, total, _YF_BATCH_SIZE):
            batch = equities[start : start + _YF_BATCH_SIZE]
            by_yahoo = {to_yahoo_ns(eq.symbol): eq for eq in batch}
            try:
                fetched = await fetch_daily_history_batch(list(by_yahoo.keys()), period)
                db_rows: list[dict[str, Any]] = []
                for ysym, eq in by_yahoo.items():
                    bars = fetched.get(ysym, [])
                    if not bars:
                        failed_set.add(eq.symbol)
                        continue
                    db_rows.extend(
                        {
                            "in_equity_id": eq.id,
                            "trade_date": bar["trade_date"],
                            "open": bar["open"],
                            "high": bar["high"],
                            "low": bar["low"],
                            "close": bar["close"],
                            "volume": bar["volume"],
                        }
                        for bar in bars
                    )
                upserted = await self._repo.upsert_bars_bulk(db_rows)
                await self._repo.commit()
                total_upserted += upserted
                logger.info(
                    "Batch %s-%s/%s: upserted %s rows",
                    start + 1,
                    start + len(batch),
                    total,
                    upserted,
                )
            except Exception:
                await self._repo.rollback()
                logger.exception("Failed refresh batch %s-%s", start + 1, start + len(batch))
                failed_set.update(eq.symbol for eq in batch)

        failed = len(failed_set)
        successful = total - failed
        out = RefreshRecentDailyResult(
            total_equities=total,
            successful=successful,
            failed=failed,
            failed_symbols=tuple(sorted(failed_set)),
            rows_upserted=total_upserted,
        )
        logger.info(
            "Refresh complete: rows=%s symbols_ok=%s symbols_failed=%s",
            out.rows_upserted,
            out.successful,
            out.failed,
        )
        return out


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
    period: str = "2d",
    delay_seconds: float = 0.0,
    limit: Optional[int] = None,
) -> RefreshRecentDailyResult:
    """Backward-compatible function wrapper used by the CLI script."""
    repo = PriceBars1DRepository(session)
    service = PriceBars1DIngestService(repo)
    return await service.refresh_recent_daily(
        period=period, delay_seconds=delay_seconds, limit=limit
    )
