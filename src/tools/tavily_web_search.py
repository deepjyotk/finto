# file: finto/search/tavily_tool.py
from __future__ import annotations
import sys
import os

# Add project root to path (go up from tools -> src -> finto)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from src.core.json_logging import logger_for
from typing import Any, Dict, List, Optional, Literal

from langchain_tavily import TavilySearch
from langchain_core.tools import tool
from src.core.settings import tavily_settings

# Set API key in environment for LangChain to pick up
os.environ["TAVILY_API_KEY"] = tavily_settings.tavily_api_key

logger = logger_for(__name__)

# ---------- Constants ----------
DEFAULT_ALLOWLIST: tuple[str, ...] = (
    "nseindia.com",
    "bseindia.com",
    "sebi.gov.in",
    "reuters.com",
    "economictimes.indiatimes.com",
    "moneycontrol.com",
    "livemint.com",
    "business-standard.com",
)


# ---------- Tool Function for LangChain Agent ----------
# Initialize TavilySearch with proper parameters
_tool_instance = TavilySearch(
    max_results=2,
    search_depth="basic",
    include_answer=True,
    include_raw_content=True,
    include_domains=list(DEFAULT_ALLOWLIST),
    topic="finance",
)


@tool("tavily_web_search")
def tavily_web_search(
    query: str,
    time_range: Optional[Literal["day", "week", "month", "year"]] = "day",
    max_results: int = 2,
) -> Dict[str, Any]:
    """Search the web for finance news, filings, and current events using Tavily.

    Focuses on India-first finance sources (NSE, BSE, SEBI, Reuters, ET, Moneycontrol).
    Returns recent, source-backed context with AI-generated summaries.

    Args:
        query: Search query string
        time_range: Filter by time - "day", "week", "month", or "year" (default: "day")
        max_results: Maximum results to return, 1-3 (default: 2)

    Returns:
        Dict with keys: query, answer, results (list of {title, url, content, score}),
        images, response_time. Content is truncated to prevent context overflow.
    """
    # TavilySearch.invoke() accepts query and can override instance parameters
    # through its _run() method via invoke()
    response = _tool_instance.invoke(
        {
            "query": query,
            "time_range": time_range,
            "max_results": max_results,
        }
    )

    if isinstance(response, dict) and "results" in response:
        for result in response["results"]:
            if "content" in result and result["content"]:
                result["content"] = result["content"][:600]
            if "raw_content" in result:
                del result["raw_content"]

    return response


# ---------- Main (smoke test) ----------
if __name__ == "__main__":
    # Quick end-to-end sanity checks using native LangChain I/O

    # Test queries
    test_queries = [
        "What's the closing price of RELIANCE today",
        # "Any NSE circulars on NIFTY 50 rebalancing this week",
        # "RBI policy highlights impact on equities today",
        # "Bulk or block deals for RELIANCE today",
        # "ASM/GSM surveillance list updates affecting portfolio",
    ]

    # python -m src.tools.tavily_web_search
    for i, query in enumerate(test_queries, 1):
        result = tavily_web_search(
            query=query,
            time_range="day",
            max_results=6,
        )

        print(f"\n[{i}] Query: {query}")
        print(f"Results: {len(result.get('results', []))}")
        print(f"Response time: {result.get('response_time', 'N/A')}")

        # Print the AI-generated answer (if available)
        if result.get("answer"):
            print("\n*********AI-GENERATED ANSWER*********")
            print(result["answer"])
            print("*********AI-GENERATED ANSWER*********")

        # Print top results
        print("\nTop Results:")
        for idx, r in enumerate(result.get("results", [])[:3], 1):
            print(f"\n{idx}. {r.get('title', 'No title')}")
            print(f"   URL: {r.get('url', '')}")
            print(f"   Score: {r.get('score', 'N/A')}")
            if r.get("content"):
                print(f"   Content preview: {r['content'][:150]}...")
            # Uncomment to see raw content
            # if r.get("raw_content"):
            #     print(f"   Raw content: {r['raw_content'][:200]}...")
