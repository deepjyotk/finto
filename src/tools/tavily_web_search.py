# file: finto/search/tavily_tool.py
from __future__ import annotations

import os
import sys
from typing import Any, Dict, Literal, Optional

from langchain_core.tools import tool
from langchain_tavily import TavilySearch
from langgraph.prebuilt import ToolNode

from src.core.json_logging import logger_for
from src.core.settings import tavily_settings

# Add project root to path (go up from tools -> src -> finto)
sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)


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


# Finance-focused defaults — topic and include_domains are always hardcoded.
# We create a new TavilySearch instance per call so that max_results,
# search_depth, and time_range can be varied per-request. Construction is
# cheap (no network calls at init); the API call happens inside .invoke().
def _make_tavily_instance(
    max_results: int,
    search_depth: str,
    time_range: Optional[str],
) -> TavilySearch:
    return TavilySearch(
        max_results=max_results,
        search_depth=search_depth,
        time_range=time_range,
        include_answer=True,
        include_raw_content=False,
        include_domains=list(DEFAULT_ALLOWLIST),
        topic="finance",
    )


@tool("tavily_web_search")
def tavily_web_search(
    query: str,
    time_range: Optional[Literal["day", "week", "month", "year"]] = "day",
    search_depth: Literal["basic", "advanced"] = "basic",
    max_results: int = 3,
) -> Dict[str, Any]:
    """Search the web for finance news, filings, and current events using Tavily.

    Focuses on India-first finance sources (NSE, BSE, SEBI, Reuters, ET, Moneycontrol).
    topic is always "finance" — do not attempt to override it.

    Args:
        query: Search query string.
        time_range: Recency filter — "day" (today), "week" (7 days),
                    "month" (30 days), "year" (12 months). Default: "day".
        search_depth: "basic" for fast headline results (default);
                      "advanced" for deep crawl with more content — use only when
                      a broad/research query needs thorough coverage.
        max_results: Number of source results to return, 1–5. Default: 3.
                     Use 1–2 for targeted lookups; 4–5 for broad market sweeps.

    Returns:
        Dict with keys: query, answer (Tavily AI summary), results
        (list of {title, url, content, score}), response_time.
    """
    instance = _make_tavily_instance(
        max_results=max_results,
        search_depth=search_depth,
        time_range=time_range,
    )
    response = instance.invoke({"query": query})

    if isinstance(response, dict) and "results" in response:
        for result in response["results"]:
            if "content" in result and result["content"]:
                result["content"] = result["content"][:600]

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
            search_depth="basic",
            max_results=3,
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

# News agent tools - focused on web search and basic symbol/price lookup
news_agent_tools = ToolNode([tavily_web_search])
