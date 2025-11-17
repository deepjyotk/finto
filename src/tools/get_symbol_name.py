# src/tools/get_symbol_name.py
from typing import List 
from concurrent.futures import ThreadPoolExecutor
from langchain_core.tools import tool
from src.utils.vector_embeddings import init_pinecone, query_symbols
from dotenv import load_dotenv

load_dotenv()

# Initialize Pinecone once at module level
index, embeddings = init_pinecone()

def _get_symbol_for_query(query: str) -> str:
    matches = query_symbols(index, embeddings, query, top_k=1)
    if not matches:
        return "Symbol not found"
    return matches[0]["metadata"].get("symbol", "")

@tool("get_symbol_names")
def get_symbol_names(user_queries: List[str]) -> List[str]:
    """Extracts the stock symbols from a list of user's queries using vector similarity search.

    Input: user's query string like "I want to calculate the total value of my holdings in adani green and tata motors"
    Returns: A list with symbol name strings like "ADANIGREEN.NS", "TATAMOTORS.NS"
    """
    # Query Pinecone with the user's natural language query
    with ThreadPoolExecutor() as executor:
        results = list(executor.map(_get_symbol_for_query, user_queries))
    return results
