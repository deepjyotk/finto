from typing import List

from dotenv import load_dotenv

from src.services.vector_embeddings import init_pinecone, query_symbols

load_dotenv()

# Initialize Pinecone once at module level
index, embeddings = init_pinecone()


def _get_symbol_for_query(query: str) -> str:
    matches = query_symbols(index, embeddings, query, top_k=1)
    if not matches:
        return "Symbol not found"
    return matches[0]["metadata"].get("symbol", "")


def get_symbol_names(user_query: str) -> List[str]:
    """Extracts the stock symbols from a user's query using vector similarity search.

    Input: user's query string like "I want to calculate the total value of my holdings in adani green and tata motors"
    Returns: A list with symbol name strings like "ADANIGREEN.NS", "TATAMOTORS.NS"
    """
    normalized_query = (user_query or "").strip()
    if not normalized_query:
        return []

    return [_get_symbol_for_query(normalized_query)]
