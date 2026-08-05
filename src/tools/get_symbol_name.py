from typing import List

from dotenv import load_dotenv

from src.services.vector_embeddings import init_pinecone, query_symbols
from src.tools.common_utils import normalize_symbol

load_dotenv()

# Initialize Pinecone once at module level
index, embeddings = init_pinecone()


def _meta_result(meta: dict) -> dict:
    return {
        "symbol": meta.get("symbol", "") or "",
        "equity_id": meta.get("equity_id"),
        "company": meta.get("company") or "",
        # Missing field (legacy NSE vectors) treated as India
        "company_registered_in": meta.get("company_registered_in") or "IN",
    }


def _fetch_exact_ticker(query: str) -> dict | None:
    """Resolve an exact ticker via Pinecone fetch (NSE bare id or US:{TICKER})."""
    q = (query or "").strip().upper()
    if not q or " " in q:
        return None
    # Reject obvious natural-language / multi-token; allow Yahoo class shares (BRK-B)
    try:
        fetched = index.fetch(ids=[q, f"US:{q}"])
    except Exception:
        return None

    vectors = getattr(fetched, "vectors", None)
    if vectors is None and isinstance(fetched, dict):
        vectors = fetched.get("vectors") or {}
    if not vectors:
        return None

    # Prefer bare NSE id when both exist (e.g. INFY); US-only tickers use US:{TICKER}.
    for vid in (q, f"US:{q}"):
        if vid not in vectors:
            continue
        rec = vectors[vid]
        meta = getattr(rec, "metadata", None) or (rec.get("metadata") if isinstance(rec, dict) else {}) or {}
        if meta.get("symbol"):
            return _meta_result(meta)
    return None


def _get_symbol_for_query(query: str) -> str:
    exact = _fetch_exact_ticker(query)
    if exact and exact["symbol"]:
        return exact["symbol"]
    matches = query_symbols(index, embeddings, query, top_k=1)
    if not matches:
        return "Symbol not found"
    return matches[0]["metadata"].get("symbol", "")


def get_equity_id_for_symbol(queries: List[str]) -> List[dict]:
    """Return the best-matching symbol and metadata from Pinecone for each query.

    Returns:
        [{
            "symbol": "RELIANCE"|"TSLA",
            "equity_id": "uuid-string-or-None",
            "company": "Reliance Industries Limited"|"Tesla, Inc.",
            "company_registered_in": "IN"|"US",
        }, ...]
    """
    results = []
    for query in queries:
        exact = _fetch_exact_ticker(query)
        if exact and exact["symbol"]:
            results.append(exact)
            continue
        matches = query_symbols(index, embeddings, query, top_k=1)
        if not matches:
            results.append(
                {
                    "symbol": "",
                    "equity_id": None,
                    "company": "",
                    "company_registered_in": "IN",
                }
            )
        else:
            results.append(_meta_result(matches[0]["metadata"]))
    return results


def get_symbol_names(symbol_list: List[str]) -> List[str]:
    """Extracts the stock symbols from the list of stocks using vector similarity search.

    Input: A list of stock names like ["Adani Green", "Tata Motors"]
    Returns: A list with symbol name strings like "ADANIGREEN", "TATAMOTORS"
    """
    final_list = []
    for symbol in symbol_list:
        return_symbol = _get_symbol_for_query(symbol)
        normalized_symbol = normalize_symbol(return_symbol)
        if normalized_symbol.endswith(".NS") or normalized_symbol.endswith(".BO"):
            unnormalized_symbol = normalized_symbol[:-3]
        else:
            unnormalized_symbol = normalized_symbol

        final_list.append(unnormalized_symbol)

    return final_list
