#!/usr/bin/env python3
"""
Fetch annual & quarterly income statements (P&L) from yfinance for all NSE stocks
listed in in_equity.csv and write them to a single long-format CSV.

Usage:
    python scripts/yf-scripts/fetch_pnl_statements.py

Output:
    scripts/artifacts/pnl_statements.csv

Columns:
    symbol          - NSE symbol (e.g. RELIANCE)
    symbol_ns       - yfinance symbol (e.g. RELIANCE.NS)
    statement_type  - 'annual' | 'quarterly'
    metric          - row label from yfinance (e.g. 'Total Revenue', 'Net Income')
    period          - ISO date string of the statement period end
    value           - numeric value (INR)

Resume:
    Already-processed symbols are skipped on re-run (checkpoint file tracked).
"""

from __future__ import annotations

import csv
import os
import sys
import time
from pathlib import Path

import yfinance as yf

# ── Paths ──────────────────────────────────────────────────────────────────

SCRIPT_DIR = Path(__file__).parent
ARTIFACTS_DIR = SCRIPT_DIR.parent / "artifacts"
CSV_INPUT = ARTIFACTS_DIR / "in_equity.csv"
CSV_OUTPUT = ARTIFACTS_DIR / "pnl_statements.csv"
CHECKPOINT_FILE = ARTIFACTS_DIR / "pnl_checkpoint.txt"

# ── Config ─────────────────────────────────────────────────────────────────

DELAY_BETWEEN_STOCKS = 0.5  # seconds between requests (be polite to yfinance)
STATEMENT_TYPES = {
    "annual": "income_stmt",
    "quarterly": "quarterly_income_stmt",
}

OUTPUT_COLUMNS = ["symbol", "symbol_ns", "statement_type", "metric", "period", "value"]


# ── Helpers ────────────────────────────────────────────────────────────────


def load_symbols() -> list[str]:
    """Read all symbols from the NSE equity CSV."""
    symbols = []
    with open(CSV_INPUT, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            sym = row["symbol"].strip()
            if sym:
                symbols.append(sym)
    return symbols


def load_checkpoint() -> set[str]:
    """Return the set of symbols already processed."""
    if not CHECKPOINT_FILE.exists():
        return set()
    return set(CHECKPOINT_FILE.read_text(encoding="utf-8").splitlines())


def mark_done(symbol: str) -> None:
    with open(CHECKPOINT_FILE, "a", encoding="utf-8") as f:
        f.write(symbol + "\n")


def fetch_statements(symbol_ns: str) -> list[dict]:
    """Fetch annual + quarterly income statements and return as list of row dicts."""
    rows = []
    ticker = yf.Ticker(symbol_ns)

    for stmt_type, attr in STATEMENT_TYPES.items():
        try:
            df = getattr(ticker, attr)
        except Exception as exc:
            print(f"    [WARN] {symbol_ns} {stmt_type}: {exc}")
            continue

        if df is None or df.empty:
            continue

        for metric in df.index:
            for period_col in df.columns:
                value = df.at[metric, period_col]
                # Skip NaN
                try:
                    import math

                    if value is None or (isinstance(value, float) and math.isnan(value)):
                        continue
                except Exception:
                    continue

                rows.append(
                    {
                        "symbol": symbol_ns.removesuffix(".NS"),
                        "symbol_ns": symbol_ns,
                        "statement_type": stmt_type,
                        "metric": str(metric),
                        "period": (
                            str(period_col.date())
                            if hasattr(period_col, "date")
                            else str(period_col)
                        ),
                        "value": value,
                    }
                )

    return rows


# ── Main ───────────────────────────────────────────────────────────────────


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--limit", type=int, default=None, help="Process only N symbols (for testing)"
    )
    args = parser.parse_args()

    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

    all_symbols = load_symbols()
    if args.limit:
        all_symbols = all_symbols[: args.limit]

    done = load_checkpoint()
    remaining = [s for s in all_symbols if s not in done]

    print(f"Total symbols: {len(all_symbols)}")
    print(f"Already done:  {len(done)}")
    print(f"To process:    {len(remaining)}")
    print(f"Output:        {CSV_OUTPUT}\n")

    # Open CSV (append if resuming, create with header if new)
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
                rows = fetch_statements(symbol_ns)
                if rows:
                    writer.writerows(rows)
                    out_file.flush()
                    print(f"{len(rows)} rows")
                else:
                    print("no data")

                mark_done(symbol)

            except Exception as exc:
                print(f"ERROR: {exc}")
                # Don't mark as done — will retry on next run

            time.sleep(DELAY_BETWEEN_STOCKS)

    except KeyboardInterrupt:
        print("\n\nInterrupted. Progress saved — re-run to continue.")
    finally:
        out_file.close()

    done_now = load_checkpoint()
    print(f"\nDone. Processed {len(done_now)}/{len(all_symbols)} symbols.")
    print(f"Output saved to: {CSV_OUTPUT}")


if __name__ == "__main__":
    main()
