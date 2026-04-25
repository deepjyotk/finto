#!/usr/bin/env python3
"""
Load pnl_statements.csv → f_pnl_statements table (JSONB schema).

The CSV is long/EAV format (one row per metric). This script pivots it
in-memory into JSONB rows: one row per (in_equity_id, statement_type, period)
with all metrics packed into a single dict.

Usage:
    python scripts/db-scripts/load_pnl_statements.py
    python scripts/db-scripts/load_pnl_statements.py --file path/to/other.csv
    python scripts/db-scripts/load_pnl_statements.py --truncate   # wipe first

CSV shape (unchanged from fetch script):
    symbol, symbol_ns, statement_type, metric, period, value

DB shape after pivot:
    in_equity_id=<in_equities.id>, statement_type='annual', period=2024-03-31
    data={"Net Income": 179181000000, "Total Revenue": 899328000000, ...}
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import os
from collections import defaultdict
from datetime import date
from pathlib import Path

import asyncpg
from dotenv import load_dotenv

load_dotenv()

SCRIPT_DIR = Path(__file__).parent
DEFAULT_CSV = SCRIPT_DIR.parent / "artifacts" / "pnl_statements.csv"
CHUNK_SIZE = 5_000  # rows (JSONB rows, each ~1 KB — smaller chunks than EAV)


def parse_date(s: str) -> date | None:
    try:
        return date.fromisoformat(s)
    except (ValueError, TypeError):
        return None


def parse_value(s: str) -> float | None:
    try:
        return float(s)
    except (ValueError, TypeError):
        return None


def pivot_csv(csv_path: Path) -> list[tuple]:
    """
    Read the long-format CSV and pivot into JSONB records.
    Returns a list of tuples: (symbol, symbol_ns, statement_type, period, data_json_str)
    """
    # Group by (symbol, symbol_ns, statement_type, period)
    groups: dict[tuple, dict[str, float]] = defaultdict(dict)
    meta: dict[tuple, str] = {}  # key → symbol (bare, without .NS)

    print(f"Reading {csv_path} …")
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            d = parse_date(row.get("period", ""))
            if d is None:
                continue
            v = parse_value(row.get("value", ""))
            if v is None:
                continue
            metric = row.get("metric", "").strip()
            if not metric:
                continue

            symbol_ns = row["symbol_ns"].strip()
            stmt_type = row["statement_type"].strip()
            key = (symbol_ns, stmt_type, d)

            groups[key][metric] = v
            if key not in meta:
                meta[key] = row["symbol"].strip()

            if (i + 1) % 100_000 == 0:
                print(f"  … read {i+1:,} CSV rows, {len(groups):,} JSONB rows so far")

    records = []
    for (symbol_ns, stmt_type, period), data in groups.items():
        symbol = meta[(symbol_ns, stmt_type, period)]
        records.append((symbol, symbol_ns, stmt_type, period, json.dumps(data)))

    print(f"Pivoted {len(records):,} JSONB rows from {len(groups):,} groups")
    return records


async def _upsert_chunk(conn: asyncpg.Connection, rows: list[tuple]) -> None:
    """
    Upsert a chunk via temp table + INSERT … ON CONFLICT DO UPDATE.
    All three steps run inside one explicit transaction so the COPY and
    INSERT see the same temp-table rows (asyncpg is autocommit by default;
    without a transaction the COPY would commit and clear the stage before
    the INSERT runs).
    """
    async with conn.transaction():
        await conn.execute(
            """
            CREATE TEMP TABLE IF NOT EXISTS _pnl_stage (
                symbol         TEXT,
                symbol_ns      TEXT,
                statement_type TEXT,
                period         DATE,
                data           TEXT
            ) ON COMMIT DELETE ROWS
            """
        )

        await conn.copy_records_to_table(
            "_pnl_stage",
            records=rows,
            columns=["symbol", "symbol_ns", "statement_type", "period", "data"],
        )

        await conn.execute(
            """
            INSERT INTO f_financial_statements
                (in_equity_id, statement_type, period, data)
            SELECT ie.id, s.statement_type, s.period, s.data::jsonb
            FROM   _pnl_stage AS s
            JOIN   in_equities AS ie
              ON   ie.symbol = split_part(
                       upper(COALESCE(NULLIF(s.symbol, ''), s.symbol_ns)),
                       '.',
                       1
                   )
            ON CONFLICT (in_equity_id, statement_type, period)
            DO UPDATE SET
                data       = EXCLUDED.data,
                updated_at = now()
            """
        )


async def load(csv_path: Path, truncate: bool) -> None:
    raw_url = os.environ["DATABASE_URL"]
    url = raw_url.replace("postgresql+asyncpg://", "postgresql://")

    print("Connecting to DB …")
    conn = await asyncpg.connect(url)

    try:
        if truncate:
            print("Truncating f_financial_statements …")
            await conn.execute("TRUNCATE TABLE f_financial_statements RESTART IDENTITY")

        all_records = pivot_csv(csv_path)

        total = len(all_records)
        upserted = 0

        for i in range(0, total, CHUNK_SIZE):
            chunk = all_records[i : i + CHUNK_SIZE]
            await _upsert_chunk(conn, chunk)
            upserted += len(chunk)
            print(f"  … {upserted:,}/{total:,} rows upserted", end="\r")

        print(f"\nDone. {upserted:,} JSONB rows upserted.")

        count = await conn.fetchval("SELECT COUNT(*) FROM f_financial_statements")
        print(f"Total rows in f_financial_statements: {count:,}")

    finally:
        await conn.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--file", type=Path, default=DEFAULT_CSV, help="Path to pnl_statements.csv (long-format)"
    )
    parser.add_argument(
        "--truncate", action="store_true", help="Truncate the table before loading (full reload)"
    )
    args = parser.parse_args()

    if not args.file.exists():
        raise SystemExit(f"CSV not found: {args.file}")

    asyncio.run(load(args.file, args.truncate))


if __name__ == "__main__":
    main()
