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
        # if .NS is present, can you remove it and return the symbol without .NS
        final_list.append(normalized_symbol)
    return final_list

