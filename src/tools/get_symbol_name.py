from typing import List

from dotenv import load_dotenv

from src.services.vector_embeddings import init_pinecone, query_symbols
from src.tools.common_utils import normalize_symbol

load_dotenv()

# Initialize Pinecone once at module level
index, embeddings = init_pinecone()


def _get_symbol_for_query(query: str) -> str:
    matches = query_symbols(index, embeddings, query, top_k=1)
    if not matches:
        return "Symbol not found"
    return matches[0]["metadata"].get("symbol", "")


def get_equity_id_for_symbol(queries: List[str]) -> List[dict]:
    """Return the best-matching symbol and its equity_id from Pinecone for each query.

    Returns:
        [{"symbol": "RELIANCE", "equity_id": "uuid-string-or-None"}, ...]
    """
    results = []
    for query in queries:
        matches = query_symbols(index, embeddings, query, top_k=1)
        if not matches:
            results.append({"symbol": "", "equity_id": None})
        else:
            meta = matches[0]["metadata"]
            results.append({"symbol": meta.get("symbol", ""), "equity_id": meta.get("equity_id")})
    return results


def get_symbol_names(symbol_list: List[str]) -> List[str]:
    """Extracts the stock symbols from the list of stocks using vector similarity search.

    Input: A list of stock names like ["Adani Green", "Tata Motors"]
    Returns: A list with symbol name strings like "ADANIGREEN", "TATAMOTORS"
    """
    # normalized_query = (user_query or "").strip()
    # if not normalized_query:
    #     return []
    final_list = []
    for symbol in symbol_list:
        return_symbol = _get_symbol_for_query(symbol)
        normalized_symbol = normalize_symbol(return_symbol)
        if normalized_symbol.endswith(".NS") or normalized_symbol.endswith(".BO"):
            unnormalized_symbol = normalized_symbol[:-3]

        final_list.append(unnormalized_symbol)

    return final_list

