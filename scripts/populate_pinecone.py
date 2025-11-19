# src/scripts/populate_pinecone.py
"""
Script to populate Pinecone index with company symbols and names from company-symbol-mapping.xlsx
"""
import sys
from pathlib import Path

from dotenv import load_dotenv

from src.services.vector_embeddings import init_pinecone, upsert_from_portfolio_excel

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

load_dotenv()


def main():
    print("Initializing Pinecone...")
    index, embeddings = init_pinecone()

    print("Loading portfolio data and creating embeddings...")
    excel_path = "company-symbol-mapping.xlsx"  # Adjust path if needed
    upsert_from_portfolio_excel(
        index=index,
        embeddings=embeddings,
        excel_path=excel_path,
        symbol_col="Symbol",
        name_col="Company Name",
    )

    print("✓ Successfully populated Pinecone index with symbol embeddings!")

    # Test query
    from src.services.vector_embeddings import query_symbols

    print("\nTesting query: 'adani green'")
    results = query_symbols(index, embeddings, "adani green", top_k=3)
    for i, result in enumerate(results, 1):
        print(
            f"{i}. {result['metadata']['symbol']} - {result['metadata']['company']} (score: {result['score']:.4f})"
        )


if __name__ == "__main__":
    main()

