"""Service layer for the US stocks data-engineering demo.

Owns alert-rule CRUD and read access to the alerts written by the Spark
streaming job. Alerts themselves are never created here — Spark is the only
writer, which is what keeps the demo pipeline honest.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Mapping, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.json_logging import logger_for
from src.core.settings import demo_us_stock_settings
from src.models.demo_us_stock import (
    DEMO_US_STOCK_ALERT_DIRECTIONS,
    DEMO_US_STOCK_CHART_WINDOWS,
    DEMO_US_STOCK_WINDOW_SECONDS,
    ChartWindowSpec,
    DemoUsStockAlert,
    DemoUsStockAlertRule,
)
from src.repositories.demo_us_stock_repo import DemoUsStockRepository

logger = logger_for(__name__)


class DemoUsStockService:
    """Orchestrates demo alert rules and alert reads."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = DemoUsStockRepository(session)

    # ── Supported inputs ────────────────────────────────────────────────

    @staticmethod
    def supported_symbols() -> list[str]:
        """Symbols the market-data producer streams, so rules can actually fire."""
        return demo_us_stock_settings.supported_symbols

    @staticmethod
    def window_seconds_options() -> list[int]:
        return list(DEMO_US_STOCK_WINDOW_SECONDS)

    @staticmethod
    def chart_window_options() -> list[str]:
        return list(DEMO_US_STOCK_CHART_WINDOWS)

    # ── Chart bars ──────────────────────────────────────────────────────

    async def chart_bars(
        self, symbol: str, window: str
    ) -> tuple[str, ChartWindowSpec, list[Mapping[str, Any]]]:
        """Return the normalized symbol, the window spec and its OHLCV bars.

        Raises ``ValueError`` for a symbol the producer does not stream or a
        window outside the fixed mapping — neither can produce a chart.
        """
        normalized = symbol.strip().upper()
        supported = self.supported_symbols()
        if normalized not in supported:
            raise ValueError(
                f"'{normalized}' is not part of the demo. "
                f"Supported symbols: {', '.join(supported)}"
            )

        spec = DEMO_US_STOCK_CHART_WINDOWS.get(window)
        if spec is None:
            allowed = ", ".join(DEMO_US_STOCK_CHART_WINDOWS)
            raise ValueError(f"window must be one of {allowed}")

        bars = await self._repo.fetch_chart_bars(normalized, spec)
        return normalized, spec, bars

    # ── Alert rules ─────────────────────────────────────────────────────

    async def create_rule(
        self,
        user_id: UUID,
        symbol: str,
        window_seconds: int,
        percentage_threshold: Decimal,
        direction: str,
    ) -> DemoUsStockAlertRule:
        """Create a rule after validating symbol and window against the demo config."""
        supported = self.supported_symbols()
        if symbol not in supported:
            raise ValueError(
                f"'{symbol}' is not part of the demo. Supported symbols: {', '.join(supported)}"
            )
        if window_seconds not in DEMO_US_STOCK_WINDOW_SECONDS:
            allowed = ", ".join(str(w) for w in DEMO_US_STOCK_WINDOW_SECONDS)
            raise ValueError(f"window_seconds must be one of {allowed}")
        if direction not in DEMO_US_STOCK_ALERT_DIRECTIONS:
            allowed = ", ".join(DEMO_US_STOCK_ALERT_DIRECTIONS)
            raise ValueError(f"direction must be one of {allowed}")
        if percentage_threshold <= 0:
            raise ValueError("percentage_threshold must be greater than 0")

        existing = await self._repo.find_duplicate_rule(
            user_id, symbol, window_seconds, direction
        )
        if existing is not None:
            raise ValueError(
                f"You already have a {direction} rule for {symbol} on a "
                f"{self._window_label(window_seconds)} window. Edit it instead."
            )

        rule = await self._repo.create_rule(
            user_id=user_id,
            symbol=symbol,
            window_seconds=window_seconds,
            percentage_threshold=percentage_threshold,
            direction=direction,
        )
        await self._session.commit()
        logger.info(
            "demo_us_stock_rule_created",
            extra={
                "user_id": str(user_id),
                "rule_id": str(rule.id),
                "symbol": symbol,
                "window_seconds": window_seconds,
                "direction": direction,
            },
        )
        return rule

    async def list_rules(self, user_id: UUID) -> list[DemoUsStockAlertRule]:
        return await self._repo.list_rules(user_id)

    async def update_rule(
        self,
        user_id: UUID,
        rule_id: UUID,
        percentage_threshold: Optional[Decimal] = None,
        direction: Optional[str] = None,
        is_active: Optional[bool] = None,
    ) -> Optional[DemoUsStockAlertRule]:
        """Patch a rule. Returns None when the rule does not belong to the user."""
        rule = await self._repo.get_rule(user_id, rule_id)
        if rule is None:
            return None

        if percentage_threshold is None and direction is None and is_active is None:
            raise ValueError("Provide percentage_threshold, direction, or is_active to update")
        if percentage_threshold is not None:
            if percentage_threshold <= 0:
                raise ValueError("percentage_threshold must be greater than 0")
            rule.percentage_threshold = percentage_threshold
        if direction is not None:
            if direction not in DEMO_US_STOCK_ALERT_DIRECTIONS:
                allowed = ", ".join(DEMO_US_STOCK_ALERT_DIRECTIONS)
                raise ValueError(f"direction must be one of {allowed}")
            if direction != rule.direction:
                existing = await self._repo.find_duplicate_rule(
                    user_id, rule.symbol, rule.window_seconds, direction
                )
                if existing is not None and existing.id != rule.id:
                    raise ValueError(
                        f"You already have a {direction} rule for {rule.symbol} on a "
                        f"{self._window_label(rule.window_seconds)} window."
                    )
            rule.direction = direction
        if is_active is not None:
            rule.is_active = is_active

        rule.updated_at = datetime.now(timezone.utc)
        await self._session.commit()
        await self._session.refresh(rule)
        return rule

    async def delete_rule(self, user_id: UUID, rule_id: UUID) -> bool:
        """Delete a rule and its alerts (FK cascade). False when not found."""
        rule = await self._repo.get_rule(user_id, rule_id)
        if rule is None:
            return False
        await self._repo.delete_rule(rule)
        await self._session.commit()
        logger.info(
            "demo_us_stock_rule_deleted",
            extra={"user_id": str(user_id), "rule_id": str(rule_id)},
        )
        return True

    # ── Triggered alerts ────────────────────────────────────────────────

    async def list_alerts(
        self, user_id: UUID, limit: int = 50, unread_only: bool = False
    ) -> tuple[list[DemoUsStockAlert], int]:
        """Return the user's alerts newest first, plus their total unread count."""
        alerts = await self._repo.list_alerts(user_id, limit=limit, unread_only=unread_only)
        unread = await self._repo.list_alerts(user_id, limit=limit, unread_only=True)
        return alerts, len(unread)

    async def mark_alert_read(self, user_id: UUID, alert_id: UUID) -> Optional[DemoUsStockAlert]:
        """Mark one alert as read. Returns None when it does not belong to the user."""
        alert = await self._repo.get_alert(user_id, alert_id)
        if alert is None:
            return None
        if not alert.is_read:
            alert.is_read = True
            await self._session.commit()
            await self._session.refresh(alert)
        return alert

    # ── Helpers ─────────────────────────────────────────────────────────

    @staticmethod
    def _window_label(window_seconds: int) -> str:
        minutes = window_seconds // 60
        return f"{minutes} minute" if minutes == 1 else f"{minutes} minutes"
