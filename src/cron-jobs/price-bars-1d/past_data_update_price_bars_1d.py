"""
Backfill price_bars_1d with ~2 years of daily OHLCV from Yahoo Finance (yfinance).

Run from repo finto/ (so DATABASE_URL loads from .env):

  uv run python src/cron-jobs/price-bars-1d/past_data_update_price_bars_1d.py

Trading days only: Yahoo daily series omits weekends and exchange holidays,
so we only persist rows returned for each session (industry-standard surface).

Options:
  --limit N   process only first N symbols (smoke test)
  --period S  yfinance period string (default: 2y)
"""

from __future__ import annotations

import argparse
import asyncio
import importlib.util
import logging
import sys
from pathlib import Path

# Package root: .../finto (parent of src/)
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
backfill_two_years = _MOD.backfill_two_years

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Backfill price_bars_1d (daily, trading days).")
    p.add_argument("--limit", type=int, default=None, help="Max number of equities to process")
    p.add_argument(
        "--period",
        default="2y",
        help="yfinance period (default 2y)",
    )
    p.add_argument(
        "--delay",
        type=float,
        default=0.15,
        help="Sleep between symbols to reduce rate-limit risk (seconds)",
    )
    return p.parse_args()


async def _run(args: argparse.Namespace) -> None:
    async with SessionLocal() as session:
        await backfill_two_years(
            session,
            period=args.period,
            delay_seconds=args.delay,
            limit=args.limit,
        )


def main() -> None:
    args = parse_args()
    logger.info("Starting backfill period=%s limit=%s", args.period, args.limit)
    asyncio.run(_run(args))
    logger.info("Done.")


if __name__ == "__main__":
    main()
