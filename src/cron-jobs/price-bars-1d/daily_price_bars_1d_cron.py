"""
Incremental daily update for price_bars_1d (intended for GCP Cloud Scheduler).

Re-fetches a short rolling window of daily bars per symbol and upserts, so missed
runs or holidays do not leave gaps.

Run from repo finto/:

  uv run python src/cron-jobs/price-bars-1d/daily_price_bars_1d_cron.py

Cloud Scheduler: HTTP target to a secured Cloud Run route that invokes this logic,
or a Cloud Run Job / VM cron that runs the same command with service credentials.
"""

from __future__ import annotations

import argparse
import asyncio
import importlib.util
import logging
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(_ROOT / ".env")

from src.core.db import SessionLocal  # noqa: E402

_INGEST_PATH = Path(__file__).resolve().parent / "services" / "price_bars_1d_ingest.py"
_SPEC = importlib.util.spec_from_file_location("price_bars_1d_ingest", _INGEST_PATH)
if _SPEC is None or _SPEC.loader is None:
    raise ImportError(f"Unable to load ingest module from {_INGEST_PATH}")
_MOD = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = _MOD
_SPEC.loader.exec_module(_MOD)
refresh_recent_daily = _MOD.refresh_recent_daily

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Upsert recent daily bars into price_bars_1d.")
    p.add_argument("--limit", type=int, default=None, help="Max number of equities to process")
    p.add_argument(
        "--period",
        default="14d",
        help="yfinance lookback window (default 14d)",
    )
    p.add_argument(
        "--delay",
        type=float,
        default=0.1,
        help="Sleep between symbols (seconds)",
    )
    return p.parse_args()


async def _run(args: argparse.Namespace) -> None:
    async with SessionLocal() as session:
        await refresh_recent_daily(
            session,
            period=args.period,
            delay_seconds=args.delay,
            limit=args.limit,
        )


def main() -> None:
    args = parse_args()
    logger.info("Starting daily refresh period=%s limit=%s", args.period, args.limit)
    asyncio.run(_run(args))
    logger.info("Done.")


if __name__ == "__main__":
    main()
