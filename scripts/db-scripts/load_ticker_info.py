#!/usr/bin/env python3
"""
Load ticker_info.csv into in_equities.company_metadata (yfinance JSON snapshot).

Only updates rows that already exist in in_equities (NSE symbol = CSV "symbol");
CSV rows for unknown symbols are ignored.

Usage:
    python scripts/db-scripts/load_ticker_info.py
    python scripts/db-scripts/load_ticker_info.py --file path/to/other.csv
    python scripts/db-scripts/load_ticker_info.py --truncate   # clear all metadata first

Strategy:
  - Staging table → UPDATE in_equities on matching `symbol` (NSE).
  - Idempotent: re-run overwrites company_metadata and updated_at.
  - `data` is passed as TEXT and cast to jsonb in SQL.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import os
from pathlib import Path

import asyncpg
from dotenv import load_dotenv

load_dotenv()

SCRIPT_DIR = Path(__file__).parent
DEFAULT_CSV = SCRIPT_DIR.parent / "artifacts" / "ticker_info.csv"
CHUNK_SIZE = 2_000


async def _upsert_chunk(conn: asyncpg.Connection, rows: list[tuple]) -> None:
    """rows: [(symbol, symbol_ns, data_json_str), ...]"""
    async with conn.transaction():
        await conn.execute(
            """
            CREATE TEMP TABLE IF NOT EXISTS _ticker_info_stage (
                symbol    TEXT,
                symbol_ns TEXT,
                data      TEXT
            ) ON COMMIT DELETE ROWS
            """
        )

        await conn.copy_records_to_table(
            "_ticker_info_stage",
            records=rows,
            columns=["symbol", "symbol_ns", "data"],
        )

        await conn.execute(
            """
            UPDATE in_equities AS ie
            SET
                company_metadata = s.data::jsonb,
                updated_at = now()
            FROM _ticker_info_stage AS s
            WHERE ie.symbol = s.symbol
            """
        )


async def load(csv_path: Path, truncate: bool) -> None:
    raw_url = os.environ["DATABASE_URL"]
    url = raw_url.replace("postgresql+asyncpg://", "postgresql://")

    print("Connecting to DB …")
    conn = await asyncpg.connect(url)

    try:
        if truncate:
            print("Clearing company_metadata on all in_equities …")
            await conn.execute("UPDATE in_equities SET company_metadata = NULL")

        print(f"Reading {csv_path} …")
        chunk: list[tuple] = []
        total = 0
        upserted = 0

        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                symbol_ns = row.get("symbol_ns", "").strip()
                symbol = row.get("symbol", "").strip()
                data = row.get("data", "").strip()
                if not symbol_ns or not data or data == "{}":
                    continue
                chunk.append((symbol, symbol_ns, data))
                total += 1

                if len(chunk) >= CHUNK_SIZE:
                    await _upsert_chunk(conn, chunk)
                    upserted += len(chunk)
                    print(f"  … {upserted:,} rows upserted", end="\r")
                    chunk = []

        if chunk:
            await _upsert_chunk(conn, chunk)
            upserted += len(chunk)

        print(f"\nDone. {upserted:,} ticker rows upserted from {total:,} CSV rows.")

        count = await conn.fetchval(
            "SELECT COUNT(*) FROM in_equities WHERE company_metadata IS NOT NULL"
        )
        print(f"in_equities rows with company_metadata: {count:,}")

    finally:
        await conn.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", type=Path, default=DEFAULT_CSV, help="Path to ticker_info.csv")
    parser.add_argument(
        "--truncate",
        action="store_true",
        help="Set company_metadata to NULL on all in_equities rows before loading",
    )
    args = parser.parse_args()

    if not args.file.exists():
        raise SystemExit(f"CSV not found: {args.file}")

    asyncio.run(load(args.file, args.truncate))


if __name__ == "__main__":
    main()
