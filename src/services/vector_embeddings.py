# src/services/vector_embeddings.py
from typing import Iterable, Tuple

import pandas as pd
from langchain_openai import OpenAIEmbeddings
from pinecone import Pinecone, ServerlessSpec

from src.core.settings import llm_settings, pinecone_settings


def init_pinecone(index_name: str | None = None, dimension: int | None = None):
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
            spec=ServerlessSpec(cloud="aws", region="us-east-1"),
        )

    index = pc.Index(index_name)
    # Use OpenAI embeddings (API-based, no local model needed)
    embeddings = OpenAIEmbeddings(
        model=pinecone_settings.embedding_model,
        openai_api_key=llm_settings.openai_api_key,
    )
    return index, embeddings


def upsert_symbols_from_iterable(
    index,
    embeddings: OpenAIEmbeddings,
    items: Iterable[Tuple],
    batch_size: int = 64,
):
    """
    Upsert symbol/company pairs (optionally with equity_id).

    items: iterable of 2-tuples (symbol, company_name)
           OR 3-tuples (symbol, company_name, equity_id)

    Pinecone metadata stored: {symbol, company, equity_id (if provided)}
    The vector id is the NSE symbol (e.g. "RELIANCE").
    """
    ids = []
    texts = []
    metas = []
    for item in items:
        symbol, company = item[0], item[1]
        equity_id = item[2] if len(item) > 2 else None
        embed_text = f"{symbol} {company}"
        ids.append(symbol)
        texts.append(embed_text)
        meta: dict = {"symbol": symbol, "company": company}
        if equity_id:
            meta["equity_id"] = str(equity_id)
        metas.append(meta)
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
    embeddings: OpenAIEmbeddings,
    excel_path: str = "portfolio.xlsx",
    symbol_col: str = "Symbol",
    name_col: str = "Name",
):
    """Load symbols from Excel and upsert to Pinecone (no equity_id)."""
    df = pd.read_excel(excel_path)
    if symbol_col not in df.columns or name_col not in df.columns:
        raise ValueError(f"Expected columns {symbol_col} and {name_col} in {excel_path}")
    items = ((str(row[symbol_col]).strip(), str(row[name_col]).strip()) for _, row in df.iterrows())
    upsert_symbols_from_iterable(index, embeddings, items)


def upsert_from_db(
    index,
    embeddings: OpenAIEmbeddings,
    rows: list[Tuple[str, str, str]],
    batch_size: int = 64,
) -> None:
    """Upsert (symbol, company_name, equity_id) triples sourced from in_equities DB table."""
    upsert_symbols_from_iterable(index, embeddings, rows, batch_size=batch_size)


def query_symbols(index, embeddings: OpenAIEmbeddings, query_text: str, top_k: int = 5):
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
