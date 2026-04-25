"""Repository for reading equities and upserting daily price bars."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from typing import Any
from uuid import UUID

from sqlalchemy import func, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.price_bar_1d import PriceBar1d


class PriceBars1DRepository:
    """DB operations for `price_bars_1d` ingestion flows."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def load_all_equities(self) -> list[tuple[UUID, str]]:
        result = await self._session.execute(
            text("SELECT id, symbol FROM in_equities ORDER BY symbol")
        )
        return [(row[0], row[1]) for row in result.fetchall()]

    async def list_bars_for_equity_since(
        self, in_equity_id: UUID, start_date: date
    ) -> list[dict[str, Any]]:
        """Return daily rows for one equity on or after start_date, ordered by session date."""
        result = await self._session.execute(
            text(
                """
                SELECT trade_date, open, high, low, close, volume
                FROM   price_bars_1d
                WHERE  in_equity_id = :in_equity_id
                  AND  trade_date >= :start_date
                ORDER  BY trade_date ASC
                """
            ),
            {"in_equity_id": in_equity_id, "start_date": start_date},
        )
        return [
            {
                "trade_date": row[0],
                "open": row[1],
                "high": row[2],
                "low": row[3],
                "close": row[4],
                "volume": row[5],
            }
            for row in result.fetchall()
        ]

    async def upsert_bars(self, in_equity_id: UUID, bars: Sequence[dict]) -> int:
        if not bars:
            return 0

        table = PriceBar1d.__table__
        rows = [
            {
                "in_equity_id": in_equity_id,
                "trade_date": bar["trade_date"],
                "open": bar["open"],
                "high": bar["high"],
                "low": bar["low"],
                "close": bar["close"],
                "volume": bar["volume"],
            }
            for bar in bars
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
        await self._session.execute(upsert)
        return len(rows)

    async def commit(self) -> None:
        await self._session.commit()

    async def rollback(self) -> None:
        await self._session.rollback()
