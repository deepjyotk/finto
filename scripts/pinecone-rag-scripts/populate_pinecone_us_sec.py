# scripts/pinecone-rag-scripts/populate_pinecone_us_sec.py
"""
Populate Pinecone with US company tickers from SEC company_tickers.json.

Each Pinecone document gets:
  - id:         US:{SYMBOL}  (avoids overwriting NSE bare-symbol ids like INFY)
  - metadata:   {symbol, company, company_registered_in: "US"}
  - vector:     OpenAI embedding of "SYMBOL Company Name US"

Also writes src/data/us_sec_tickers.json for runtime normalize_symbol (.NS skip).

Usage:
    python scripts/pinecone-rag-scripts/populate_pinecone_us_sec.py
"""
from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

from dotenv import load_dotenv

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

load_dotenv()

SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SEC_USER_AGENT = "FintoFinanceBot admin@finto.app"
US_REGISTRY_PATH = project_root / "src" / "data" / "us_sec_tickers.json"


def fetch_sec_tickers() -> list[dict[str, str]]:
    """Download SEC company_tickers.json and return [{symbol, company}, ...]."""
    req = urllib.request.Request(
        SEC_TICKERS_URL,
        headers={"User-Agent": SEC_USER_AGENT, "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        payload = json.loads(resp.read().decode("utf-8"))

    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    # SEC payload is {"0": {"cik_str": ..., "ticker": "AAPL", "title": "..."}, ...}
    for entry in payload.values():
        ticker = str(entry.get("ticker") or "").strip().upper()
        title = str(entry.get("title") or "").strip()
        if not ticker or not title:
            continue
        # Yahoo-style class shares already use '-' in SEC (e.g. BRK-B)
        if ticker in seen:
            continue
        seen.add(ticker)
        rows.append({"symbol": ticker, "company": title})
    return rows


def write_us_registry(symbols: list[str]) -> None:
    US_REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    US_REGISTRY_PATH.write_text(
        json.dumps(sorted(symbols), indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    from src.services.vector_embeddings import init_pinecone, query_symbols, upsert_symbols_from_iterable

    print(f"Fetching SEC tickers from {SEC_TICKERS_URL} …")
    companies = fetch_sec_tickers()
    print(f"  {len(companies):,} US tickers loaded")

    symbols = [c["symbol"] for c in companies]
    write_us_registry(symbols)
    print(f"  Wrote registry → {US_REGISTRY_PATH}")

    print("Initializing Pinecone …")
    index, embeddings = init_pinecone()

    items = [
        {
            "id": f"US:{c['symbol']}",
            "symbol": c["symbol"],
            "company": c["company"],
            "company_registered_in": "US",
        }
        for c in companies
    ]

    print("Upserting US embeddings …")
    upsert_symbols_from_iterable(index, embeddings, items)
    print("Done — Pinecone index populated with US SEC tickers.")

    for q in ("tesla", "TSLA"):
        print(f"\nTest query: {q!r}")
        results = query_symbols(index, embeddings, q, top_k=3)
        for i, r in enumerate(results, 1):
            m = r["metadata"]
            print(
                f"  {i}. id={r['id']} {m.get('symbol')} — {m.get('company')} "
                f"(company_registered_in={m.get('company_registered_in')}) score={r['score']:.4f}"
            )


if __name__ == "__main__":
    main()
