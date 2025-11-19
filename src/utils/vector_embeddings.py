# src/utils/vector_embeddings.py
from typing import Iterable, Tuple

import pandas as pd
from langchain_huggingface import HuggingFaceEmbeddings
from pinecone import Pinecone, ServerlessSpec

from src.core.settings import pinecone_settings


def init_pinecone(
    index_name: str | None = None, dimension: int | None = None
):
    """Initialize Pinecone client and return index and embeddings model."""
    # Use settings defaults if not provided
    index_name = index_name or pinecone_settings.index_name
    dimension = dimension or pinecone_settings.dimension
    api_key = pinecone_settings.api_key

    # Initialize Pinecone client (new API)
    pc = Pinecone(api_key=api_key)

    # Create index if it doesn't exist
    existing_indexes = [index.name for index in pc.list_indexes()]
    if index_name not in existing_indexes:
        pc.create_index(
            name=index_name,
            dimension=dimension,
            metric="cosine",
            spec=ServerlessSpec(cloud="aws", region="us-east-1"),  # Change based on your preference
        )

    index = pc.Index(index_name)
    # Use embedding model from settings (runs locally, no API key needed)
    embeddings = HuggingFaceEmbeddings(
        model_name=pinecone_settings.embedding_model,
        model_kwargs={"device": "cpu"},  # Change to 'cuda' if you have GPU
        encode_kwargs={"normalize_embeddings": True},  # Normalize for better cosine similarity
    )
    return index, embeddings


def upsert_symbols_from_iterable(
    index, embeddings: HuggingFaceEmbeddings, items: Iterable[Tuple[str, str]], batch_size: int = 64
):
    """
    Upsert symbol/company pairs.
    items: iterable of tuples (symbol, company_name)
    Uses id = symbol (safe unique id). Metadata includes company_name.
    """
    ids = []
    texts = []
    metas = []
    for symbol, company in items:
        text = f"{symbol} {company}"
        ids.append(symbol)
        texts.append(text)
        metas.append({"symbol": symbol, "company": company})
        if len(ids) >= batch_size:
            vectors = embeddings.embed_documents(texts)
            to_upsert = [
                {"id": ids[i], "values": vectors[i], "metadata": metas[i]} for i in range(len(ids))
            ]
            index.upsert(vectors=to_upsert)
            ids = []
            texts = []
            metas = []
    # leftover
    if ids:
        vectors = embeddings.embed_documents(texts)
        to_upsert = [
            {"id": ids[i], "values": vectors[i], "metadata": metas[i]} for i in range(len(ids))
        ]
        index.upsert(vectors=to_upsert)


def upsert_from_portfolio_excel(
    index,
    embeddings: HuggingFaceEmbeddings,
    excel_path: str = "portfolio.xlsx",
    symbol_col: str = "Symbol",
    name_col: str = "Name",
):
    """Load symbols from Excel and upsert to Pinecone."""
    df = pd.read_excel(excel_path)
    if symbol_col not in df.columns or name_col not in df.columns:
        raise ValueError(f"Expected columns {symbol_col} and {name_col} in {excel_path}")
    items = ((str(row[symbol_col]).strip(), str(row[name_col]).strip()) for _, row in df.iterrows())
    upsert_symbols_from_iterable(index, embeddings, items)


def query_symbols(index, embeddings: HuggingFaceEmbeddings, query_text: str, top_k: int = 5):
    """
    Query Pinecone with an embedding for the natural language query.
    Returns list of dicts: {id, score, metadata}
    """
    qvec = embeddings.embed_query(query_text)
    response = index.query(vector=qvec, top_k=top_k, include_metadata=True)
    matches = []
    for match in response["matches"]:
        matches.append(
            {
                "id": match["id"],
                "score": match.get("score", 0),
                "metadata": match.get("metadata", {}),
            }
        )
    return matches
