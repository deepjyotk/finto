"""Alpaca market-data WebSocket client for the US stocks demo.

Speaks the Alpaca v2 stream protocol directly over ``websockets`` rather than
pulling in the full Alpaca SDK: the demo only needs auth, a trades
subscription, and normalization of ``T: "t"`` messages.

Protocol reference::

    <- [{"T":"success","msg":"connected"}]
    -> {"action":"auth","key":"...","secret":"..."}
    <- [{"T":"success","msg":"authenticated"}]
    -> {"action":"subscribe","trades":["AAPL","TSLA"]}
    <- [{"T":"subscription","trades":["AAPL","TSLA"],...}]
    <- [{"T":"t","S":"AAPL","i":123,"p":205.42,"s":100,"t":"2026-08-01T19:30:15.1Z"}]
"""

from __future__ import annotations

import asyncio
import json
import re
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Optional

import websockets

from src.core.json_logging import logger_for

logger = logger_for(__name__)

# Alpaca timestamps carry nanosecond precision; datetime.fromisoformat only
# accepts 3 or 6 fractional digits, so the tail is truncated to microseconds.
_FRACTIONAL_SECONDS = re.compile(r"\.(\d+)")

# Seconds to wait before reconnecting after the stream drops.
RECONNECT_DELAY_SECONDS = 5.0


class AlpacaStreamError(RuntimeError):
    """Raised when Alpaca rejects the connection in a way retrying will not fix."""


def parse_alpaca_timestamp(raw: str) -> datetime:
    """Parse an Alpaca RFC-3339 timestamp into a timezone-aware UTC datetime."""
    normalized = raw.replace("Z", "+00:00")

    def _truncate(match: re.Match[str]) -> str:
        return "." + match.group(1)[:6]

    normalized = _FRACTIONAL_SECONDS.sub(_truncate, normalized)
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def build_event_id(symbol: str, trade_id: Any) -> str:
    """Stable id for a trade so replays deduplicate downstream."""
    return f"alpaca-{symbol}-{trade_id}"


async def _await_message_of_type(
    connection: websockets.ClientConnection, expected: str, context: str
) -> dict[str, Any]:
    """Read frames until one message matches ``T == expected``, raising on errors."""
    while True:
        raw = await connection.recv()
        messages = json.loads(raw)
        if isinstance(messages, dict):
            messages = [messages]
        for message in messages:
            kind = message.get("T")
            if kind == "error":
                raise AlpacaStreamError(
                    f"Alpaca returned an error during {context}: "
                    f"{message.get('msg')} (code {message.get('code')})"
                )
            if kind == expected:
                return message


async def _connect_and_subscribe(
    stream_url: str, api_key: str, api_secret: str, symbols: list[str]
) -> websockets.ClientConnection:
    """Open the stream, authenticate, and subscribe to trades for ``symbols``."""
    connection = await websockets.connect(stream_url, max_queue=1024)
    try:
        await _await_message_of_type(connection, "success", "connect")

        await connection.send(json.dumps({"action": "auth", "key": api_key, "secret": api_secret}))
        await _await_message_of_type(connection, "success", "authentication")

        await connection.send(json.dumps({"action": "subscribe", "trades": symbols}))
        confirmation = await _await_message_of_type(connection, "subscription", "subscription")
        logger.info(
            "demo_us_stock_alpaca_subscribed",
            extra={"symbols": confirmation.get("trades", symbols)},
        )
        return connection
    except Exception:
        await connection.close()
        raise


async def stream_alpaca_trades(
    stream_url: str,
    api_key: str,
    api_secret: str,
    symbols: list[str],
) -> AsyncIterator[dict[str, Any]]:
    """Yield normalized trade dicts from Alpaca, reconnecting on transient drops.

    Yields plain dicts (not ``MarketPriceEvent``) so the producer owns validation
    and can drop a single malformed tick without tearing down the stream.
    """
    while True:
        connection: Optional[websockets.ClientConnection] = None
        try:
            connection = await _connect_and_subscribe(stream_url, api_key, api_secret, symbols)
            async for raw in connection:
                messages = json.loads(raw)
                if isinstance(messages, dict):
                    messages = [messages]
                for message in messages:
                    if message.get("T") == "error":
                        raise AlpacaStreamError(
                            f"Alpaca stream error: {message.get('msg')} "
                            f"(code {message.get('code')})"
                        )
                    if message.get("T") != "t":
                        continue
                    symbol = message.get("S")
                    if not symbol:
                        continue
                    yield {
                        "event_id": build_event_id(symbol, message.get("i")),
                        "symbol": symbol,
                        "price": message.get("p"),
                        "volume": message.get("s"),
                        "event_time": parse_alpaca_timestamp(message["t"]),
                        "source": "alpaca",
                    }
        except AlpacaStreamError:
            raise
        except (websockets.ConnectionClosed, OSError, asyncio.TimeoutError) as exc:
            logger.warning(
                "demo_us_stock_alpaca_reconnecting",
                extra={"error": str(exc), "delay_seconds": RECONNECT_DELAY_SECONDS},
            )
            await asyncio.sleep(RECONNECT_DELAY_SECONDS)
        finally:
            if connection is not None:
                await connection.close()
