"""API endpoints for the US stocks data-engineering demo.

Isolated from the rest of Arthik: its own TimescaleDB database, a separate
router prefix, and no interaction with portfolio, AI, notification or the
Indian-equity ticker workflows.

Every endpoint derives ``user_id`` from the authenticated session. The client
can never submit another user's id, and rules/alerts belonging to someone else
return 404 rather than leaking their existence.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated, Literal, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.api.schemas.demo_us_stocks import (
    AlertListResponse,
    AlertResponse,
    AlertRuleListResponse,
    AlertRuleResponse,
    ChartBar,
    ChartResponse,
    CreateAlertRuleRequest,
    SupportedSymbolsResponse,
    UpdateAlertRuleRequest,
)
from src.core.json_logging import logger_for
from src.core.middleware import require_auth
from src.dependencies import get_demo_us_stock_service
from src.models.demo_us_stock import (
    DEMO_US_STOCK_DEFAULT_CHART_WINDOW,
    DEMO_US_STOCK_DEFAULT_SYMBOL,
)
from src.services.demo_us_stock import DemoUsStockService

logger = logger_for(__name__)

router = APIRouter(prefix="/demo/us-stocks", tags=["demo-us-stocks"])


def _to_threshold(value: Optional[float]) -> Optional[Decimal]:
    """Convert a request float to the Decimal the NUMERIC(8,4) column expects.

    Going via ``str`` keeps the shortest exact representation, so 0.2 stays
    0.2 rather than becoming 0.2000000000000000111.
    """
    return None if value is None else Decimal(str(value))


@router.get("/symbols", response_model=SupportedSymbolsResponse)
async def supported_symbols(
    svc: Annotated[DemoUsStockService, Depends(get_demo_us_stock_service)],
    user: dict = Depends(require_auth),
):
    """Symbols the market-data producer streams, plus the allowed window sizes.

    A rule can only be created for one of these symbols, otherwise it would
    never fire because nothing publishes prices for it.
    """
    return SupportedSymbolsResponse(
        symbols=svc.supported_symbols(),
        window_seconds_options=svc.window_seconds_options(),
        chart_window_options=svc.chart_window_options(),
        default_symbol=DEMO_US_STOCK_DEFAULT_SYMBOL,
        default_chart_window=DEMO_US_STOCK_DEFAULT_CHART_WINDOW,
    )


@router.get("/chart", response_model=ChartResponse)
async def stock_chart(
    svc: Annotated[DemoUsStockService, Depends(get_demo_us_stock_service)],
    user: dict = Depends(require_auth),
    symbol: str = Query(DEMO_US_STOCK_DEFAULT_SYMBOL, description="US stock symbol, e.g. TSLA"),
    window: Literal["1min", "1h", "1d", "1mo"] = Query(
        DEMO_US_STOCK_DEFAULT_CHART_WINDOW,
        description="Chart window; the server picks the matching granularity",
    ),
):
    """OHLCV bars for one symbol, read from TimescaleDB.

    The window determines the source relation through a fixed server-side
    mapping — a raw-tick rollup for ``1min`` and a continuous aggregate for the
    rest. Relation names are never accepted from the client.
    """
    try:
        resolved_symbol, spec, bars = await svc.chart_bars(symbol=symbol, window=window)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    return ChartResponse(
        symbol=resolved_symbol,
        window=window,
        granularity=spec.granularity,
        data=[
            ChartBar(
                timestamp=bar["bucket"],
                open=bar["open"],
                high=bar["high"],
                low=bar["low"],
                close=bar["close"],
                volume=bar["volume"],
            )
            for bar in bars
        ],
    )


@router.post(
    "/alert-rules",
    response_model=AlertRuleResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_alert_rule(
    body: CreateAlertRuleRequest,
    svc: Annotated[DemoUsStockService, Depends(get_demo_us_stock_service)],
    user: dict = Depends(require_auth),
):
    """Create a price-movement alert rule for the authenticated user."""
    user_id = UUID(user["user_id"])
    try:
        rule = await svc.create_rule(
            user_id=user_id,
            symbol=body.symbol,
            window_seconds=body.window_seconds,
            percentage_threshold=Decimal(str(body.percentage_threshold)),
            direction=body.direction,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    return AlertRuleResponse.model_validate(rule)


@router.get("/alert-rules", response_model=AlertRuleListResponse)
async def list_alert_rules(
    svc: Annotated[DemoUsStockService, Depends(get_demo_us_stock_service)],
    user: dict = Depends(require_auth),
):
    """List the authenticated user's alert rules, newest first."""
    user_id = UUID(user["user_id"])
    rules = await svc.list_rules(user_id)
    return AlertRuleListResponse(rules=[AlertRuleResponse.model_validate(rule) for rule in rules])


@router.patch("/alert-rules/{rule_id}", response_model=AlertRuleResponse)
async def update_alert_rule(
    rule_id: UUID,
    body: UpdateAlertRuleRequest,
    svc: Annotated[DemoUsStockService, Depends(get_demo_us_stock_service)],
    user: dict = Depends(require_auth),
):
    """Update a rule's threshold and/or pause it."""
    user_id = UUID(user["user_id"])
    try:
        rule = await svc.update_rule(
            user_id=user_id,
            rule_id=rule_id,
            percentage_threshold=_to_threshold(body.percentage_threshold),
            direction=body.direction,
            is_active=body.is_active,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    if rule is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert rule not found.")
    return AlertRuleResponse.model_validate(rule)


@router.delete("/alert-rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_alert_rule(
    rule_id: UUID,
    svc: Annotated[DemoUsStockService, Depends(get_demo_us_stock_service)],
    user: dict = Depends(require_auth),
):
    """Delete a rule along with the alerts it produced."""
    user_id = UUID(user["user_id"])
    deleted = await svc.delete_rule(user_id, rule_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert rule not found.")


@router.get("/alerts", response_model=AlertListResponse)
async def list_alerts(
    svc: Annotated[DemoUsStockService, Depends(get_demo_us_stock_service)],
    user: dict = Depends(require_auth),
    limit: int = Query(50, ge=1, le=200, description="Max alerts to return"),
    unread_only: bool = Query(False, description="Return only unread alerts"),
):
    """List alerts triggered for the authenticated user, newest first."""
    user_id = UUID(user["user_id"])
    alerts, unread_count = await svc.list_alerts(user_id, limit=limit, unread_only=unread_only)
    return AlertListResponse(
        alerts=[AlertResponse.model_validate(alert) for alert in alerts],
        unread_count=unread_count,
    )


@router.patch("/alerts/{alert_id}/read", response_model=AlertResponse)
async def mark_alert_read(
    alert_id: UUID,
    svc: Annotated[DemoUsStockService, Depends(get_demo_us_stock_service)],
    user: dict = Depends(require_auth),
):
    """Mark a triggered alert as read."""
    user_id = UUID(user["user_id"])
    alert = await svc.mark_alert_read(user_id, alert_id)
    if alert is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found.")
    return AlertResponse.model_validate(alert)
