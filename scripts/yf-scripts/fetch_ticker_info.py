#!/usr/bin/env python3
"""
Fetch yfinance ticker info (market cap, P/E, ratios, sector, etc.) for all NSE stocks.

This writes one JSON row per stock to ticker_info.csv, which is then loaded into
f_ticker_info table via load_ticker_info.py.

Usage:
    python scripts/yf-scripts/fetch_ticker_info.py
    python scripts/yf-scripts/fetch_ticker_info.py --limit 10  # test run

Output:
    scripts/artifacts/ticker_info.csv

Columns:
    symbol      - NSE symbol (e.g. RELIANCE)
    symbol_ns   - yfinance symbol (e.g. RELIANCE.NS)
    data        - JSON string with all yfinance info fields

Key fields captured in data:
    Valuation   : marketCap, trailingPE, forwardPE, priceToBook, enterpriseValue,
                  enterpriseToRevenue, enterpriseToEbitda
    Price       : currentPrice, regularMarketPrice, fiftyTwoWeekHigh,
                  fiftyTwoWeekLow, fiftyDayAverage, twoHundredDayAverage
    Profitability: grossMargins, operatingMargins, profitMargins,
                   returnOnEquity, returnOnAssets, returnOnCapital
    Growth      : earningsGrowth, revenueGrowth, earningsQuarterlyGrowth
    Dividends   : dividendYield, dividendRate, payoutRatio
    Balance     : debtToEquity, currentRatio, quickRatio, totalCash,
                  totalDebt, totalRevenue, freeCashflow
    Risk        : beta, shortRatio
    Metadata    : sector, industry, fullTimeEmployees, country, website,
                  longBusinessSummary

Resume:
    Checkpoint at scripts/artifacts/ticker_info_checkpoint.txt
"""

from __future__ import annotations

import csv
import json
import math
import time
from pathlib import Path
from typing import Any

import yfinance as yf

# ── Paths ──────────────────────────────────────────────────────────────────

SCRIPT_DIR = Path(__file__).parent
ARTIFACTS_DIR = SCRIPT_DIR.parent / "artifacts"
CSV_INPUT = ARTIFACTS_DIR / "in_equity.csv"
CSV_OUTPUT = ARTIFACTS_DIR / "ticker_info.csv"
CHECKPOINT_FILE = ARTIFACTS_DIR / "ticker_info_checkpoint.txt"

# ── Config ─────────────────────────────────────────────────────────────────

DELAY_BETWEEN_STOCKS = 0.5

# Fields to extract from yfinance info dict (keep None if missing).
# Storing a curated subset keeps rows small and avoids internal yfinance keys.
FIELDS_TO_KEEP = [
    # Valuation
    "marketCap", "trailingPE", "forwardPE", "priceToBook",
    "enterpriseValue", "enterpriseToRevenue", "enterpriseToEbitda",
    "trailingEps", "forwardEps",
    # Price
    "currentPrice", "regularMarketPrice",
    "fiftyTwoWeekHigh", "fiftyTwoWeekLow",
    "fiftyDayAverage", "twoHundredDayAverage",
    # Profitability
    "grossMargins", "operatingMargins", "profitMargins",
    "returnOnEquity", "returnOnAssets",
    # Growth
    "earningsGrowth", "revenueGrowth", "earningsQuarterlyGrowth",
    # Dividends
    "dividendYield", "dividendRate", "payoutRatio",
    "exDividendDate", "lastDividendDate",
    # Balance sheet derived
    "debtToEquity", "currentRatio", "quickRatio",
    "totalCash", "totalCashPerShare", "totalDebt",
    "totalRevenue", "revenuePerShare",
    "freeCashflow", "operatingCashflow",
    # Shares
    "sharesOutstanding", "floatShares", "sharesShort",
    "shortRatio", "shortPercentOfFloat",
    # Risk
    "beta", "auditRisk", "boardRisk", "compensationRisk", "overallRisk",
    # Metadata
    "sector", "industry", "fullTimeEmployees",
    "country", "city", "website",
    "longName", "shortName",
    "longBusinessSummary",
    # Exchange / price info
    "currency", "exchange", "quoteType",
    "previousClose", "open", "volume", "averageVolume",
    "bookValue", "faceValue",
]

OUTPUT_COLUMNS = ["symbol", "symbol_ns", "data"]


# ── Helpers ────────────────────────────────────────────────────────────────

def load_symbols() -> list[str]:
    with open(CSV_INPUT, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return [row["symbol"].strip() for row in reader if row["symbol"].strip()]


def load_checkpoint() -> set[str]:
    if not CHECKPOINT_FILE.exists():
        return set()
    return set(CHECKPOINT_FILE.read_text(encoding="utf-8").splitlines())


def mark_done(symbol: str) -> None:
    with open(CHECKPOINT_FILE, "a", encoding="utf-8") as f:
        f.write(symbol + "\n")


def _clean(v: Any) -> Any:
    """Convert non-serialisable types; drop NaN/inf."""
    if v is None:
        return None
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        return None
    # yfinance sometimes returns Timestamp objects
    try:
        import pandas as pd
        if isinstance(v, pd.Timestamp):
            return v.isoformat()
    except ImportError:
        pass
    return v


def fetch_info(symbol_ns: str) -> dict | None:
    ticker = yf.Ticker(symbol_ns)
    raw: dict = ticker.info or {}
    if not raw or raw.get("quoteType") == "NONE":
        return None

    data: dict[str, Any] = {}
    for field in FIELDS_TO_KEEP:
        v = _clean(raw.get(field))
        if v is not None:
            data[field] = v

    return data if data else None


# ── Main ───────────────────────────────────────────────────────────────────

def main() -> None:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None,
                        help="Process only N symbols (for testing)")
    args = parser.parse_args()

    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

    all_symbols = load_symbols()
    if args.limit:
        all_symbols = all_symbols[: args.limit]

    done = load_checkpoint()
    remaining = [s for s in all_symbols if s not in done]

    print(f"Total symbols : {len(all_symbols)}")
    print(f"Already done  : {len(done)}")
    print(f"To process    : {len(remaining)}")
    print(f"Output        : {CSV_OUTPUT}\n")

    write_header = not CSV_OUTPUT.exists() or CSV_OUTPUT.stat().st_size == 0
    out_file = open(CSV_OUTPUT, "a", newline="", encoding="utf-8")
    writer = csv.DictWriter(out_file, fieldnames=OUTPUT_COLUMNS)
    if write_header:
        writer.writeheader()

    try:
        for i, symbol in enumerate(remaining, start=1):
            symbol_ns = f"{symbol}.NS"
            print(f"[{i}/{len(remaining)}] {symbol_ns} ...", end=" ", flush=True)

            try:
                data = fetch_info(symbol_ns)
                if data:
                    writer.writerow({
                        "symbol": symbol,
                        "symbol_ns": symbol_ns,
                        "data": json.dumps(data),
                    })
                    out_file.flush()
                    print(f"{len(data)} fields")
                else:
                    print("no data")
                mark_done(symbol)
            except Exception as exc:
                print(f"ERROR: {exc}")

            time.sleep(DELAY_BETWEEN_STOCKS)

    except KeyboardInterrupt:
        print("\n\nInterrupted. Progress saved — re-run to continue.")
    finally:
        out_file.close()

    done_now = load_checkpoint()
    print(f"\nDone. Processed {len(done_now)}/{len(all_symbols)} symbols.")
    print(f"Output saved to: {CSV_OUTPUT}")
    print(f"\nTo load into DB:")
    print(f"  python scripts/db-scripts/load_ticker_info.py")


if __name__ == "__main__":
    main()
