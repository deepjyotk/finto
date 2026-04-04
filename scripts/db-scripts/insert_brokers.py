#!/usr/bin/env python3
"""Insert sample brokers into the brokers table"""

import asyncio
import os

import asyncpg
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")


async def insert_brokers():
    """Insert sample broker data"""

    # Convert URL for asyncpg
    url = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
    url = url.replace("postgresql+asyncpg://", "postgresql://")

    print("🔗 Connecting to database...")
    conn = await asyncpg.connect(url)

    try:
        # Sample brokers to insert
        brokers = [
            {"name": "Zerodha", "type": "Equity", "country": "India"},
            {"name": "Grow", "type": "Equity", "country": "India"},
            {"name": "AngelOne", "type": "Equity", "country": "India"},
        ]

        print(f"\n📝 Inserting {len(brokers)} brokers...\n")

        inserted_count = 0
        for broker in brokers:
            try:
                # Insert broker
                broker_id = await conn.fetchval(
                    """
                    INSERT INTO brokers (broker_name, broker_type, country)
                    VALUES ($1::broker_name_enum, $2::broker_type_enum, $3::country_enum)
                    RETURNING broker_id
                    """,
                    broker["name"],
                    broker["type"],
                    broker["country"],
                )

                print(
                    f"✅ Inserted: {broker['name']:<10} | {broker['type']:<8} | {broker['country']:<6} | ID: {broker_id}"
                )
                inserted_count += 1

            except Exception as e:
                print(
                    f"❌ Failed to insert {broker['name']} ({broker['type']}, {broker['country']}): {e}"
                )

        print(f"\n✨ Successfully inserted {inserted_count}/{len(brokers)} brokers")

        # Display all brokers in the table
        print("\n📊 Current brokers in database:\n")
        all_brokers = await conn.fetch("SELECT * FROM brokers ORDER BY broker_name, broker_type")

        if all_brokers:
            print(f"{'Broker Name':<12} {'Type':<8} {'Country':<8} {'ID'}")
            print("-" * 60)
            for b in all_brokers:
                print(
                    f"{b['broker_name']:<12} {b['broker_type']:<8} {b['country']:<8} {b['broker_id']}"
                )

            print(f"\n📈 Total brokers in database: {len(all_brokers)}")
        else:
            print("No brokers found in database")

    finally:
        await conn.close()
        print("\n🔒 Connection closed")


if __name__ == "__main__":
    try:
        asyncio.run(insert_brokers())
    except Exception as e:
        print(f"\n💥 Error: {e}")
        raise SystemExit(1)
