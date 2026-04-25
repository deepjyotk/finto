"""In-memory stock search service for the Daily Stock Game autocomplete.

Loads NSE equity list from the `in_equities` DB table once at startup.
Fast prefix + substring matching — no DB calls per keystroke.
Falls back to Pinecone for semantic "company description" queries.
"""

from __future__ import annotations

import asyncio
from typing import TypedDict

from sqlalchemy import text

from src.core.json_logging import logger_for

logger = logger_for(__name__)

# Module-level in-memory cache populated at app startup via load_equity_cache()
_equity_cache: list["StockMatch"] = []
_valid_symbols: set[str] = set()


class StockMatch(TypedDict):
    symbol: str  # e.g. "RELIANCE"
    symbol_ns: str  # e.g. "RELIANCE.NS"
    company_name: str  # e.g. "Reliance Industries Limited"


async def load_equity_cache() -> None:
    """Populate the in-memory cache from the `in_equities` table. Call once at startup."""
    global _equity_cache, _valid_symbols
    from src.core.db import SessionLocal

    try:
        async with SessionLocal() as session:
            result = await session.execute(
                text("SELECT symbol, company_name FROM in_equities ORDER BY symbol")
            )
            rows = result.fetchall()
        records: list[StockMatch] = []
        for row in rows:
            sym = (row[0] or "").strip().upper()
            name = (row[1] or "").strip()
            if sym:
                records.append(StockMatch(symbol=sym, symbol_ns=f"{sym}.NS", company_name=name))
        _equity_cache = records
        _valid_symbols = {s["symbol"] for s in records}
        logger.info("stock_search_loaded", extra={"count": len(records)})
    except Exception as exc:
        logger.error("stock_search_load_failed", extra={"error": str(exc)})


def _get_equity_list() -> list[StockMatch]:
    return _equity_cache


def get_valid_symbols() -> set[str]:
    """Return a set of all valid NSE symbols (without .NS suffix)."""
    return _valid_symbols


def search_stocks(query: str, limit: int = 10) -> list[StockMatch]:
    """Fast in-memory search: matches symbol prefix first, then company name substring.

    Args:
        query: User typed text (case-insensitive).
        limit: Max results to return.

    Returns:
        List of matching stocks, symbol-prefix matches ranked first.
    """
    q = query.strip().upper()
    if not q or len(q) < 1:
        return []

    all_stocks = _get_equity_list()
    q_lower = q.lower()

    symbol_prefix: list[StockMatch] = []
    symbol_contains: list[StockMatch] = []
    name_contains: list[StockMatch] = []

    for stock in all_stocks:
        sym = stock["symbol"]
        name_lower = stock["company_name"].lower()

        if sym.startswith(q):
            symbol_prefix.append(stock)
        elif q in sym:
            symbol_contains.append(stock)
        elif q_lower in name_lower:
            name_contains.append(stock)

    # Merge: prefix matches first, then symbol contains, then name contains
    results = symbol_prefix + symbol_contains + name_contains
    return results[:limit]


async def search_stocks_semantic(query: str, limit: int = 10) -> list[StockMatch]:
    """Semantic search via Pinecone for natural language queries like 'solar energy company'.

    Only called when the fast search returns few results and query looks like a description.
    Runs sync Pinecone/OpenAI call in a thread pool.
    """

    def _sync_search() -> list[StockMatch]:
        try:
            from src.services.vector_embeddings import init_pinecone, query_symbols

            index, embeddings = init_pinecone()
            matches = query_symbols(index, embeddings, query, top_k=limit)
            return [
                StockMatch(
                    symbol=m["metadata"]["symbol"],
                    symbol_ns=f"{m['metadata']['symbol']}.NS",
                    company_name=m["metadata"].get("company", ""),
                )
                for m in matches
            ]
        except Exception as exc:
            logger.warning("semantic_stock_search_failed", extra={"error": str(exc)})
            return []

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _sync_search)


def validate_symbol(symbol: str) -> bool:
    """Return True if symbol (with or without .NS) is a known NSE equity."""
    sym = symbol.upper().removesuffix(".NS")
    return sym in get_valid_symbols()
