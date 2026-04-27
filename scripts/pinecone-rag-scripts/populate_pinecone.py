# scripts/pinecone-rag-scripts/populate_pinecone.py
"""
Populate Pinecone with symbol embeddings sourced from the in_equities DB table.

Each Pinecone document gets:
  - id:         SYMBOL (e.g. "RELIANCE")
  - metadata:   {symbol, company, equity_id}  ← equity_id enables O(1) DB look-ups
  - vector:     OpenAI embedding of "SYMBOL Company Name"

Usage:
    python scripts/pinecone-rag-scripts/populate_pinecone.py
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

import asyncpg
from dotenv import load_dotenv

# Make project root importable
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

load_dotenv()


async def _fetch_equities() -> list[tuple[str, str, str]]:
    """Return [(symbol, company_name, equity_id_str), ...] from in_equities."""
    raw_url = os.environ["DATABASE_URL"]
    url = raw_url.replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(url)
    try:
        rows = await conn.fetch(
            "SELECT id::text, symbol, company_name FROM in_equities ORDER BY symbol"
        )
        return [(r["symbol"], r["company_name"], r["id"]) for r in rows]
    finally:
        await conn.close()


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--wipe",
        action="store_true",
        help="Delete ALL existing Pinecone vectors before upserting (removes stale .NS / .BO entries)",
    )
    args = parser.parse_args()

    from src.services.vector_embeddings import init_pinecone, query_symbols, upsert_from_db

    print("Fetching equities from DB …")
    rows = asyncio.run(_fetch_equities())
    print(f"  {len(rows):,} equities loaded")

    print("Initializing Pinecone …")
    index, embeddings = init_pinecone()

    if args.wipe:
        print("Wiping all existing Pinecone vectors …")
        index.delete(delete_all=True)
        print("  Done.")

    print("Upserting embeddings …")
    upsert_from_db(index, embeddings, rows)
    print("Done — Pinecone index populated with equity_id metadata.")

    print("\nTest query: 'adani green'")
    results = query_symbols(index, embeddings, "adani green", top_k=3)
    for i, r in enumerate(results, 1):
        m = r["metadata"]
        print(f"  {i}. {m.get('symbol')} — {m.get('company')} (equity_id={m.get('equity_id')}) score={r['score']:.4f}")


if __name__ == "__main__":
    main()

