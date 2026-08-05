"""Repository layer for the US stocks data-engineering demo — all DB queries.

Every rule and alert lookup is scoped by ``user_id`` so an id belonging to a
different user is indistinguishable from one that does not exist.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Mapping, Optional
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.demo_us_stock import ChartWindowSpec, DemoUsStockAlert, DemoUsStockAlertRule

# OHLCV over raw ticks, for windows finer than the smallest continuous
# aggregate. first()/last() are TimescaleDB aggregates ordered by event time;
# min()/max() alone could not give open and close.
# The interval parameters are bound as timedelta but still need an explicit
# cast: without one PostgreSQL resolves `now() - $n` through the
# timestamptz - timestamptz overload and the comparison fails to type-check.
_RAW_BARS_SQL = """
SELECT time_bucket(CAST(:bucket_width AS interval), event_time) AS bucket,
       first(price, event_time)  AS open,
       max(price)                AS high,
       min(price)                AS low,
       last(price, event_time)   AS close,
       sum(coalesce(volume, 0))  AS volume
FROM demo_us_stock_prices
WHERE symbol = :symbol
  AND event_time >= now() - CAST(:lookback AS interval)
GROUP BY bucket
ORDER BY bucket
"""

# Continuous aggregates already expose exactly these columns.
_AGGREGATE_BARS_SQL = """
SELECT bucket, open, high, low, close, volume
FROM {relation}
WHERE symbol = :symbol
  AND bucket >= now() - CAST(:lookback AS interval)
ORDER BY bucket
"""


class DemoUsStockRepository:
    """Database operations for demo alert rules, triggered alerts and chart bars."""

    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    # ── Chart bars ──────────────────────────────────────────────────────

    async def fetch_chart_bars(self, symbol: str, spec: ChartWindowSpec) -> list[Mapping[str, Any]]:
        """Return OHLCV bars for one symbol over the window described by ``spec``.

        ``spec`` always comes from ``DEMO_US_STOCK_CHART_WINDOWS``, so the
        relation interpolated into the aggregate query is a server-side
        constant rather than anything the caller supplied. The symbol and the
        durations stay bound parameters.
        """
        if spec.relation is None:
            stmt = text(_RAW_BARS_SQL)
            params = {
                "symbol": symbol,
                "bucket_width": spec.bucket_width,
                "lookback": spec.lookback,
            }
        else:
            stmt = text(_AGGREGATE_BARS_SQL.format(relation=spec.relation))
            params = {"symbol": symbol, "lookback": spec.lookback}

        result = await self._s.execute(stmt, params)
        return list(result.mappings().all())

    # ── Alert rules ─────────────────────────────────────────────────────

    async def create_rule(
        self,
        user_id: UUID,
        symbol: str,
        window_seconds: int,
        percentage_threshold: Decimal,
        direction: str,
    ) -> DemoUsStockAlertRule:
        rule = DemoUsStockAlertRule(
            user_id=user_id,
            symbol=symbol,
            window_seconds=window_seconds,
            percentage_threshold=percentage_threshold,
            direction=direction,
        )
        self._s.add(rule)
        await self._s.flush()
        await self._s.refresh(rule)
        return rule

    async def list_rules(self, user_id: UUID) -> list[DemoUsStockAlertRule]:
        stmt = (
            select(DemoUsStockAlertRule)
            .where(DemoUsStockAlertRule.user_id == user_id)
            .order_by(DemoUsStockAlertRule.created_at.desc())
        )
        result = await self._s.execute(stmt)
        return list(result.scalars().all())

    async def get_rule(self, user_id: UUID, rule_id: UUID) -> Optional[DemoUsStockAlertRule]:
        stmt = select(DemoUsStockAlertRule).where(
            DemoUsStockAlertRule.id == rule_id,
            DemoUsStockAlertRule.user_id == user_id,
        )
        result = await self._s.execute(stmt)
        return result.scalar_one_or_none()

    async def find_duplicate_rule(
        self, user_id: UUID, symbol: str, window_seconds: int, direction: str
    ) -> Optional[DemoUsStockAlertRule]:
        """Return an existing rule for the same symbol, window, and direction, if any."""
        stmt = select(DemoUsStockAlertRule).where(
            DemoUsStockAlertRule.user_id == user_id,
            DemoUsStockAlertRule.symbol == symbol,
            DemoUsStockAlertRule.window_seconds == window_seconds,
            DemoUsStockAlertRule.direction == direction,
        )
        result = await self._s.execute(stmt)
        return result.scalars().first()

    async def delete_rule(self, rule: DemoUsStockAlertRule) -> None:
        await self._s.delete(rule)
        await self._s.flush()

    # ── Triggered alerts ────────────────────────────────────────────────

    async def list_alerts(
        self,
        user_id: UUID,
        limit: int,
        unread_only: bool = False,
    ) -> list[DemoUsStockAlert]:
        stmt = select(DemoUsStockAlert).where(DemoUsStockAlert.user_id == user_id)
        if unread_only:
            stmt = stmt.where(DemoUsStockAlert.is_read.is_(False))
        stmt = stmt.order_by(DemoUsStockAlert.triggered_at.desc()).limit(limit)
        result = await self._s.execute(stmt)
        return list(result.scalars().all())

    async def get_alert(self, user_id: UUID, alert_id: UUID) -> Optional[DemoUsStockAlert]:
        stmt = select(DemoUsStockAlert).where(
            DemoUsStockAlert.id == alert_id,
            DemoUsStockAlert.user_id == user_id,
        )
        result = await self._s.execute(stmt)
        return result.scalar_one_or_none()
