"""Publish normalized US stock price events to the demo Redpanda topic.

Messages are keyed by symbol so all events for one stock land on the same
partition and keep their relative order, which the windowed Spark aggregation
depends on.
"""

from __future__ import annotations

import asyncio
from typing import Any, AsyncIterator

from aiokafka import AIOKafkaProducer
from pydantic import ValidationError

from src.core.json_logging import logger_for
from src.core.settings import demo_us_stock_settings
from src.demo_us_stocks_data_engineering.alpaca_stream import stream_alpaca_trades
from src.demo_us_stocks_data_engineering.schemas import MarketPriceEvent
from src.demo_us_stocks_data_engineering.simulated_stream import stream_simulated_trades

logger = logger_for(__name__)

# How often to log throughput, in published events.
LOG_EVERY_N_EVENTS = 100


def _build_stream(symbols: list[str]) -> AsyncIterator[dict[str, Any]]:
    """Pick the Alpaca feed when credentials exist, otherwise the simulator."""
    if demo_us_stock_settings.use_alpaca:
        logger.info(
            "demo_us_stock_producer_source",
            extra={"source": "alpaca", "url": demo_us_stock_settings.alpaca_stream_url},
        )
        return stream_alpaca_trades(
            stream_url=demo_us_stock_settings.alpaca_stream_url,
            api_key=str(demo_us_stock_settings.alpaca_api_key),
            api_secret=str(demo_us_stock_settings.alpaca_api_secret),
            symbols=symbols,
        )

    logger.info(
        "demo_us_stock_producer_source",
        extra={
            "source": "simulated",
            "reason": (
                "DEMO_US_STOCK_SIMULATE=true"
                if demo_us_stock_settings.simulate
                else "ALPACA_API_KEY/ALPACA_API_SECRET not configured"
            ),
            "tick_seconds": demo_us_stock_settings.simulate_tick_seconds,
        },
    )
    return stream_simulated_trades(
        symbols=symbols,
        tick_seconds=demo_us_stock_settings.simulate_tick_seconds,
    )


async def run_producer() -> None:
    """Stream prices into ``demo-market-prices`` until interrupted."""
    symbols = demo_us_stock_settings.supported_symbols
    if not symbols:
        raise ValueError("DEMO_US_STOCK_SYMBOLS is empty; nothing to subscribe to")

    topic = demo_us_stock_settings.kafka_topic
    producer = AIOKafkaProducer(
        bootstrap_servers=demo_us_stock_settings.kafka_bootstrap_servers,
        acks="all",
        enable_idempotence=True,
        client_id="demo-us-stock-market-data-producer",
    )

    await producer.start()
    logger.info(
        "demo_us_stock_producer_started",
        extra={
            "topic": topic,
            "bootstrap_servers": demo_us_stock_settings.kafka_bootstrap_servers,
            "symbols": symbols,
        },
    )

    published = 0
    skipped = 0
    try:
        async for raw_event in _build_stream(symbols):
            try:
                event = MarketPriceEvent(**raw_event)
            except ValidationError as exc:
                skipped += 1
                logger.warning(
                    "demo_us_stock_event_skipped",
                    extra={"error": exc.errors(), "raw_symbol": raw_event.get("symbol")},
                )
                continue

            await producer.send_and_wait(
                topic,
                key=event.symbol.encode("utf-8"),
                value=event.to_kafka_value(),
            )
            published += 1
            if published % LOG_EVERY_N_EVENTS == 0:
                logger.info(
                    "demo_us_stock_producer_progress",
                    extra={"published": published, "skipped": skipped, "topic": topic},
                )
    finally:
        await producer.stop()
        logger.info(
            "demo_us_stock_producer_stopped",
            extra={"published": published, "skipped": skipped},
        )


def main() -> None:
    """Entrypoint for ``python -m src.demo_us_stocks_data_engineering``."""
    try:
        asyncio.run(run_producer())
    except KeyboardInterrupt:
        logger.info("demo_us_stock_producer_interrupted")


if __name__ == "__main__":
    main()
