#!/usr/bin/env python3
# python scripts/db-scripts/update_old_symbol_name.py

import asyncio
import os

import asyncpg
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

# List of symbol mappings to update
SYMBOL_MAPPINGS = [
    {"old_symbol": "HBLPOWER.NS", "new_symbol": "HBLENGINE.NS"},
    {"old_symbol": "RSIL.NS", "new_symbol": "RSYSTEMS.NS"},
]


async def update_symbols():
    url = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
    url = url.replace("postgresql+asyncpg://", "postgresql://")

    print("🔗 Connecting to database...")
    conn = await asyncpg.connect(url)

    try:
        print(f"📝 Updating {len(SYMBOL_MAPPINGS)} symbol mappings...\n")

        updated_count = 0
        for mapping in SYMBOL_MAPPINGS:
            old_symbol = mapping["old_symbol"]
            new_symbol = mapping["new_symbol"]

            result = await conn.execute(
                """
                UPDATE zerodha_equity_holdings_in
                SET symbol = $1, updated_at = now()
                WHERE symbol = $2
                """,
                new_symbol,
                old_symbol,
            )

            # Extract number of rows affected
            rows_affected = int(result.split()[-1])

            if rows_affected > 0:
                print(f"✅ Updated: {old_symbol} -> {new_symbol} ({rows_affected} rows)")
                updated_count += rows_affected
            else:
                print(f"⏭️  Skipped: {old_symbol} (not found)")

        print(f"\n✨ Total rows updated: {updated_count}")

    finally:
        await conn.close()
        print("\n🔒 Connection closed")


if __name__ == "__main__":
    try:
        asyncio.run(update_symbols())
    except Exception as e:
        print(f"\n💥 Error: {e}")
        raise SystemExit(1)
