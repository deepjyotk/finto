#!/usr/bin/env python3
"""
Fetch balance sheet + cash flow statements from yfinance for all NSE stocks.

This complements fetch_pnl_statements.py (which fetches income statements).
Output uses the SAME CSV format so load_pnl_statements.py can load it directly.

Usage:
    python scripts/yf-scripts/fetch_financials.py
    python scripts/yf-scripts/fetch_financials.py --limit 10  # test run

Output:
    scripts/artifacts/financial_statements.csv

Columns (same as pnl_statements.csv):
    symbol, symbol_ns, statement_type, metric, period, value

statement_type values written:
    annual_balance     - annual balance sheet
    quarterly_balance  - quarterly balance sheet
    annual_cashflow    - annual cash flow statement
    quarterly_cashflow - quarterly cash flow statement

Loading into DB (reuse the same load script):
    python scripts/db-scripts/load_pnl_statements.py --file scripts/artifacts/financial_statements.csv

Resume:
    Checkpoint at scripts/artifacts/financials_checkpoint.txt — re-run to resume.
"""

from __future__ import annotations

import csv
import math
import time
from pathlib import Path

import yfinance as yf

# ── Paths ──────────────────────────────────────────────────────────────────

SCRIPT_DIR = Path(__file__).parent
ARTIFACTS_DIR = SCRIPT_DIR.parent / "artifacts"
CSV_INPUT = ARTIFACTS_DIR / "in_equity.csv"
CSV_OUTPUT = ARTIFACTS_DIR / "financial_statements.csv"
CHECKPOINT_FILE = ARTIFACTS_DIR / "financials_checkpoint.txt"

# ── Config ─────────────────────────────────────────────────────────────────

DELAY_BETWEEN_STOCKS = 0.5  # seconds — be polite to yfinance

# Maps statement_type label → yfinance Ticker attribute name
STATEMENT_TYPES: dict[str, str] = {
    "annual_balance": "balance_sheet",
    "quarterly_balance": "quarterly_balance_sheet",
    "annual_cashflow": "cashflow",
    "quarterly_cashflow": "quarterly_cashflow",
}

OUTPUT_COLUMNS = ["symbol", "symbol_ns", "statement_type", "metric", "period", "value"]


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


def _is_nan(v) -> bool:
    try:
        return v is None or (isinstance(v, float) and math.isnan(v))
    except Exception:
        return True


def fetch_statements(symbol_ns: str) -> list[dict]:
    """Fetch balance sheet + cash flow statements for one symbol."""
    rows = []
    ticker = yf.Ticker(symbol_ns)
    bare = symbol_ns.removesuffix(".NS")

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
                if _is_nan(value):
                    continue
                rows.append(
                    {
                        "symbol": bare,
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

    print(f"Total symbols : {len(all_symbols)}")
    print(f"Already done  : {len(done)}")
    print(f"To process    : {len(remaining)}")
    print(f"Output        : {CSV_OUTPUT}")
    print(f"Statement types: {', '.join(STATEMENT_TYPES)}\n")

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
                # Don't mark done — will retry on next run

            time.sleep(DELAY_BETWEEN_STOCKS)

    except KeyboardInterrupt:
        print("\n\nInterrupted. Progress saved — re-run to continue.")
    finally:
        out_file.close()

    done_now = load_checkpoint()
    print(f"\nDone. Processed {len(done_now)}/{len(all_symbols)} symbols.")
    print(f"Output saved to: {CSV_OUTPUT}")
    print(f"\nTo load into DB:")
    print(f"  python scripts/db-scripts/load_pnl_statements.py --file {CSV_OUTPUT}")


if __name__ == "__main__":
    main()
