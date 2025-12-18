#!/usr/bin/env python3
# python scripts/db-scripts/populate_in_equities.py
import asyncio
import csv
import os
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import asyncpg
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

SCRIPT_DIR = Path(__file__).parent
CSV_PATH = SCRIPT_DIR.parent / "artifacts" / "in_equity.csv"


def parse_date(date_str: str) -> date | None:
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, "%d-%b-%Y").date()
    except ValueError:
        return None


def parse_decimal(value: str) -> Decimal | None:
    if not value:
        return None
    try:
        return Decimal(value)
    except Exception:
        return None


def parse_int(value: str) -> int | None:
    if not value:
        return None
    try:
        return int(value)
    except Exception:
        return None


async def populate_in_equities():
    url = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
    url = url.replace("postgresql+asyncpg://", "postgresql://")

    print("🔗 Connecting to database...")
    conn = await asyncpg.connect(url)

    try:
        print(f"📂 Reading CSV from {CSV_PATH}...")
        with open(CSV_PATH, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        print(f"📝 Found {len(rows)} equities to insert...\n")

        inserted_count = 0
        skipped_count = 0

        for row in rows:
            try:
                await conn.execute(
                    """
                    INSERT INTO in_equities (
                        symbol, company_name, series, date_of_listing,
                        paid_up_value, market_lot, isin_number, face_value
                    )
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    ON CONFLICT (symbol) DO NOTHING
                    """,
                    row["symbol"],
                    row["company_name"],
                    row["series"] or None,
                    parse_date(row["date_of_listing"]),
                    parse_decimal(row["paid_up_value"]),
                    parse_int(row["market_lot"]),
                    row["isin_number"],
                    parse_decimal(row["face_value"]),
                )
                inserted_count += 1

            except asyncpg.UniqueViolationError:
                skipped_count += 1
            except Exception as e:
                print(f"❌ Failed to insert {row['symbol']}: {e}")

        print(f"✨ Successfully inserted {inserted_count} equities")
        if skipped_count:
            print(f"⏭️  Skipped {skipped_count} duplicates")

        count = await conn.fetchval("SELECT COUNT(*) FROM in_equities")
        print(f"\n📈 Total equities in database: {count}")

    finally:
        await conn.close()
        print("\n🔒 Connection closed")


if __name__ == "__main__":
    try:
        asyncio.run(populate_in_equities())
    except Exception as e:
        print(f"\n💥 Error: {e}")
        raise SystemExit(1)
