"""Simulated US stock price stream, used when Alpaca credentials are absent.

Emits a mean-reverting random walk per symbol with occasional shocks, tuned so a
2-3% threshold on a 1-5 minute window actually fires during a demo instead of
requiring a lucky market day.
"""

from __future__ import annotations

import asyncio
import random
import uuid
from datetime import datetime, timezone
from typing import Any, AsyncIterator

# Per-tick log-return standard deviation. At one tick per second this gives a
# ~1.2% standard deviation over a 60s window and ~2.6% over 300s.
TICK_VOLATILITY = 0.0015

# Chance per tick of a larger jump, so thresholds are crossed decisively.
SHOCK_PROBABILITY = 0.01
SHOCK_MIN_PCT = 0.01
SHOCK_MAX_PCT = 0.03

# Pull back toward the starting price each tick so a long demo run does not drift.
MEAN_REVERSION = 0.002

# Plausible starting prices; anything not listed starts at DEFAULT_START_PRICE.
START_PRICES: dict[str, float] = {
    "AAPL": 232.0,
    "TSLA": 415.0,
    "NVDA": 178.0,
    "MSFT": 508.0,
    "AMZN": 226.0,
    "GOOGL": 197.0,
    "META": 604.0,
}
DEFAULT_START_PRICE = 100.0


async def stream_simulated_trades(
    symbols: list[str],
    tick_seconds: float,
) -> AsyncIterator[dict[str, Any]]:
    """Yield one normalized trade dict per symbol every ``tick_seconds``."""
    anchors = {s: START_PRICES.get(s, DEFAULT_START_PRICE) for s in symbols}
    prices = dict(anchors)

    while True:
        for symbol in symbols:
            anchor = anchors[symbol]
            price = prices[symbol]

            drift = MEAN_REVERSION * (anchor - price) / anchor
            shock = 0.0
            if random.random() < SHOCK_PROBABILITY:
                shock = random.choice((-1.0, 1.0)) * random.uniform(SHOCK_MIN_PCT, SHOCK_MAX_PCT)

            price *= 1.0 + random.gauss(0.0, TICK_VOLATILITY) + drift + shock
            price = max(round(price, 4), 0.01)
            prices[symbol] = price

            yield {
                "event_id": f"simulated-{uuid.uuid4()}",
                "symbol": symbol,
                "price": price,
                "volume": random.randint(1, 500),
                "event_time": datetime.now(timezone.utc),
                "source": "simulated",
            }

        await asyncio.sleep(tick_seconds)
