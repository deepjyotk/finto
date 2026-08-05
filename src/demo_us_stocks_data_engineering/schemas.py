"""Normalized market-price event published to the demo Redpanda topic."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class MarketPriceEvent(BaseModel):
    """One trade tick, normalized to a source-independent shape.

    ``event_id`` must be stable for a given upstream trade so that Spark and the
    ``demo_us_stock_prices`` primary key can both deduplicate replays.
    """

    event_id: str = Field(..., description="Stable id for this upstream trade event")
    symbol: str = Field(..., description="US stock symbol, e.g. AAPL")
    price: float = Field(..., gt=0, description="Trade price")
    volume: Optional[int] = Field(default=None, description="Trade size, when reported")
    event_time: datetime = Field(..., description="Exchange timestamp, timezone-aware UTC")
    source: str = Field(default="alpaca", description="Upstream feed: 'alpaca' or 'simulated'")

    def to_kafka_value(self) -> bytes:
        """Serialize to the JSON wire format the Spark job parses."""
        return self.model_dump_json().encode("utf-8")
