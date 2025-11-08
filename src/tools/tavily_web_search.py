# file: finto/search/tavily_tool.py
from __future__ import annotations
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.core.json_logging import logger_for
from typing import Any, Dict, List, Mapping

from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential
from tavily import TavilyClient, TavilyError

from src.core.settings import TavilySettings, tavily_settings
from src.schemas.tavily import (
    DEFAULT_ALLOWLIST,
    ResultItem,
    SearchInput,
    SearchOutput,
)

logger = logger_for(__name__)

# ---------- Tool ----------
class TavilySearchTool:
    """
    Finance-focused Tavily search with India-first defaults.
    Deterministic, compact, and strictly typed.
    """

    __slots__ = ("_client", "_allow", "_settings")

    def __init__(self, settings: TavilySettings) -> None:
        """Initialize TavilySearchTool with injected settings."""
        self._settings = settings
        self._client = TavilyClient(api_key=settings.tavily_api_key)
        self._allow: tuple[str, ...] = DEFAULT_ALLOWLIST

    def _build_params(self, inp: SearchInput) -> Dict[str, Any]:
        params: Dict[str, Any] = {
            "query": inp.q,
            "time_range": inp.time_range,
            "search_depth": inp.depth,
            "max_results": inp.max_results,
            "include_domains": list(self._allow),
            "include_raw_content": inp.include_raw_content,
            "include_answer": True,
        }
        return {k: v for k, v in params.items() if v is not None}

    @retry(
        reraise=True,
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=0.4, min=0.4, max=3),
        retry=retry_if_exception_type(Exception),
    )
    def _call(self, params: Mapping[str, Any]) -> Dict[str, Any]:
        try:
            logger.debug("tavily.search params=%s", params)
            response = self._client.search(**dict(params))
            logger.debug("tavily.search successful, received %d results", len(response.get("results", [])))
            return response
        except TavilyError as e:
            logger.error("Tavily API error: %s", str(e))
            raise
        except Exception as e:
            logger.error("Unexpected error during Tavily search: %s", str(e))
            raise

    def search(self, inp: SearchInput) -> SearchOutput:
        logger.info("Initiating search: query='%s', time_range=%s, max_results=%d", 
                    inp.q, inp.time_range, inp.max_results)
        try:
            raw = self._call(self._build_params(inp))
            items: List[ResultItem] = []
            
            for r in (raw.get("results", []) or []):
                try:
                    item: ResultItem = {
                        "title": str(r.get("title", "")),
                        "url": str(r.get("url", "")),
                        "source": str(r.get("source", "")),
                    }
                    if "published_date" in r:
                        item["published_date"] = str(r["published_date"])
                    if "content" in r:
                        item["snippet"] = str(r["content"])[:280]
                    if "raw_content" in r:
                        item["content"] = str(r["raw_content"])
                    if isinstance(r.get("score"), (int, float)):
                        item["score"] = float(r["score"])
                    items.append(item)
                except Exception as e:
                    logger.warning("Failed to parse result item, skipping: %s", str(e))
                    continue
            
            output = SearchOutput(results=items, answer=raw.get("answer"), usage=raw.get("usage"))
            logger.info("Search completed successfully: retrieved %d results", len(items))
            return output
            
        except (TavilyError, Exception) as e:
            logger.error("Search failed for query='%s': %s", inp.q, str(e))
            raise

# ---------- Main (smoke test) ----------
if __name__ == "__main__":
    
    # Quick end-to-end sanity checks
    
    tool = TavilySearchTool(settings=tavily_settings)

    tests: list[SearchInput] = [
        # SearchInput(q="Any NSE circulars on NIFTY 50 rebalancing this week", time_range="w", max_results=5),
        # SearchInput(q="RBI policy highlights impact on equities today", time_range="d", include_raw_content=True),
        # SearchInput(q="Bulk or block deals for RELIANCE today", time_range="d"),
        SearchInput(q="What's the closing price of RELIANCE today", time_range="d"),
        # SearchInput(q="ASM/GSM surveillance list updates affecting portfolio", time_range="w"),
    ]
    # python -m src.tools.tavily_web_search
    for i, t in enumerate(tests, 1):
        out = tool.search(t)
        print(f"\n[{i}] Query: {t.q}  | results={len(out.results)}")
        
        # Print the top-level answer (if available)
        if out.answer:
            print("*********AI-GENERATED ANSWER*********")
            print(f"{out.answer}")
            print("*********AI-GENERATED ANSWER*********\n")
        
        for r in out.results[:3]:
            print(f"- {r.get('title','')} | {r.get('source','')} | {r.get('url','')}")
            # print("--------------PRINTING SNIPPENT---------------")
            # print(f"- {r.get('snippet','')}")
            # print("--------------PRINTING SNIPPENT---------------") 
            # print("\n")
            # print("*********PRINTING CONTENT*********")
            # print(f"- {r.get('content','')}")
            # print("*********PRINTING CONTENT*********")
            # print("\n\n\n\n\n")
