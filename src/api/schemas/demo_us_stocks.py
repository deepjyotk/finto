"""Pydantic schemas for the US stocks data-engineering demo API."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

# Request fields deliberately avoid Decimal bounds and ValueError-raising
# validators. The app's RequestValidationError handler only sanitizes bytes, so a
# non-JSON-serializable value inside a Pydantic error `ctx` (a Decimal bound, or a
# ValueError instance) turns what should be a 422 into a 500. `Literal` and float
# bounds keep every `ctx` value JSON-serializable.

# ── Requests ────────────────────────────────────────────────────────────────


class CreateAlertRuleRequest(BaseModel):
    """User creates a directional price-movement rule, e.g. "TSLA moves down 3% within 5 minutes"."""

    symbol: str = Field(..., min_length=1, max_length=10, description="US stock symbol, e.g. AAPL")
    window_seconds: Literal[60, 300, 900] = Field(
        ...,
        description="Aggregation window: 60 (1 min), 300 (5 min) or 900 (15 min)",
    )
    percentage_threshold: float = Field(
        ...,
        gt=0,
        le=100,
        description="Percentage move in the chosen direction that triggers the alert, e.g. 2 for 2%",
    )
    direction: Literal["up", "down"] = Field(
        ...,
        description="Trigger on upward (up) or downward (down) window open-to-close moves",
    )

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, v: str) -> str:
        """Uppercase and trim; the service rejects unsupported symbols with a 400."""
        return v.strip().upper()


class UpdateAlertRuleRequest(BaseModel):
    """Partial update of an existing rule. Omitted fields are left untouched."""

    percentage_threshold: Optional[float] = Field(
        default=None,
        gt=0,
        le=100,
        description="New percentage threshold for the rule's direction",
    )
    direction: Optional[Literal["up", "down"]] = Field(
        default=None,
        description="New direction: up or down",
    )
    is_active: Optional[bool] = Field(
        default=None, description="Pause or resume evaluation of this rule"
    )


# ── Responses ───────────────────────────────────────────────────────────────


class SupportedSymbolsResponse(BaseModel):
    """Response for GET /demo/us-stocks/symbols."""

    symbols: list[str]
    window_seconds_options: list[int]
    chart_window_options: list[str]
    default_symbol: str
    default_chart_window: str


class ChartBar(BaseModel):
    """One OHLCV bucket from TimescaleDB."""

    timestamp: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int


class ChartResponse(BaseModel):
    """Response for GET /demo/us-stocks/chart.

    ``granularity`` reports the bucket size the server chose for the requested
    window, so the client never has to know which relation was queried.
    """

    symbol: str
    window: str
    granularity: str
    data: list[ChartBar]


class AlertRuleResponse(BaseModel):
    """A single user-created alert rule."""

    id: UUID
    symbol: str
    window_seconds: int
    percentage_threshold: Decimal
    direction: Literal["up", "down"]
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AlertRuleListResponse(BaseModel):
    """Response for GET /demo/us-stocks/alert-rules."""

    rules: list[AlertRuleResponse]


class AlertResponse(BaseModel):
    """A single triggered alert produced by the Spark streaming job."""

    id: UUID
    rule_id: UUID
    symbol: str
    window_start: datetime
    window_end: datetime
    opening_price: Decimal
    closing_price: Decimal
    percentage_change: Decimal
    threshold_percentage: Decimal
    message: str
    is_read: bool
    triggered_at: datetime

    model_config = {"from_attributes": True}


class AlertListResponse(BaseModel):
    """Response for GET /demo/us-stocks/alerts."""

    alerts: list[AlertResponse]
    unread_count: int
