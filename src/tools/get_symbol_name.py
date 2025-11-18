# src/tools/get_symbol_name.py
from dotenv import load_dotenv
from langchain_core.tools import tool

from src.utils.vector_embeddings import init_pinecone, query_symbols

load_dotenv()

# Initialize Pinecone once at module level
index, embeddings = init_pinecone()


@tool("get_symbol_name")
def get_symbol_name(user_query: str) -> str:
    """Extracts the stock symbol from the user's query using vector similarity search.

    Input: user's query string like "I want to calculate the total value of my holdings in adani green"
    Returns: symbol name string like "ADANIGREEN"
    """
    # Query Pinecone with the user's natural language query
    matches = query_symbols(index, embeddings, user_query, top_k=1)

    if not matches:
        return "Symbol not found"

    # Return the best matching symbol
    best_match = matches[0]
    symbol_name = best_match["metadata"].get("symbol", "")

    return symbol_name
