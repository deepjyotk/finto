#!/usr/bin/env python3
"""Update in_equities symbols from symbolchange.csv mappings.

Reads `scripts/artifacts/symbolchange.csv` and uses:
- Column 2 (index 1): old symbol
- Column 3 (index 2): new symbol

For each mapping, if old symbol exists in `in_equities.symbol`, update it to new symbol.
"""

from __future__ import annotations

import asyncio
import csv
import os
from pathlib import Path

import asyncpg
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

SCRIPT_DIR = Path(__file__).resolve().parent
CSV_PATH = SCRIPT_DIR.parent / "artifacts" / "symbolchange.csv"


def _normalized_symbol(value: str) -> str:
    return value.strip().upper()


def load_symbol_mappings(csv_path: Path) -> list[tuple[str, str]]:
    """Load (old_symbol, new_symbol) mappings from column 2 and 3."""
    mappings: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()

    with csv_path.open(newline="", encoding="utf-8") as file:
        reader = csv.reader(file)
        for row_num, row in enumerate(reader, start=1):
            if len(row) < 3:
                print(f"Skipping row {row_num}: expected at least 3 columns.")
                continue

            old_symbol = _normalized_symbol(row[1])
            new_symbol = _normalized_symbol(row[2])

            if not old_symbol or not new_symbol or old_symbol == new_symbol:
                continue

            pair = (old_symbol, new_symbol)
            if pair not in seen:
                seen.add(pair)
                mappings.append(pair)

    return mappings


async def update_symbols_in_equities() -> None:
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not set.")

    if not CSV_PATH.exists():
        raise FileNotFoundError(f"CSV not found: {CSV_PATH}")

    mappings = load_symbol_mappings(CSV_PATH)
    print(f"Loaded {len(mappings)} unique symbol mappings from {CSV_PATH}")

    db_url = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
    print("Connecting to database...")
    conn = await asyncpg.connect(db_url)

    checked = 0
    updated = 0
    not_found = 0
    conflict_skipped = 0

    try:
        for old_symbol, new_symbol in mappings:
            checked += 1

            old_exists = await conn.fetchval(
                "SELECT 1 FROM in_equities WHERE symbol = $1 LIMIT 1",
                old_symbol,
            )
            if not old_exists:
                not_found += 1
                continue

            new_exists = await conn.fetchval(
                "SELECT 1 FROM in_equities WHERE symbol = $1 LIMIT 1",
                new_symbol,
            )
            if new_exists:
                conflict_skipped += 1
                print(
                    f"Skipped (new symbol already exists): {old_symbol} -> {new_symbol}"
                )
                continue

            result = await conn.execute(
                """
                UPDATE in_equities
                SET symbol = $1, updated_at = now()
                WHERE symbol = $2
                """,
                new_symbol,
                old_symbol,
            )
            rows = int(result.split()[-1])
            if rows > 0:
                updated += rows
                print(f"Updated: {old_symbol} -> {new_symbol} ({rows} row)")

        print("\nDone.")
        print(f"Checked mappings: {checked}")
        print(f"Updated rows: {updated}")
        print(f"Old symbol not found: {not_found}")
        print(f"Skipped due to symbol conflict: {conflict_skipped}")
    finally:
        await conn.close()
        print("Database connection closed.")


if __name__ == "__main__":
    try:
        asyncio.run(update_symbols_in_equities())
    except Exception as exc:  # noqa: BLE001
        print(f"Error: {exc}")
        raise SystemExit(1) from exc
