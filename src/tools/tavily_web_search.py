# file: finto/search/tavily_tool.py
from __future__ import annotations

import src.core.json_logging as logging
from typing import Any, Dict, List, Mapping

from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential
from tavily import TavilyClient

from src.core.settings import tavily_settings
from src.schemas.tavily import (
    DEFAULT_ALLOWLIST,
    ResultItem,
    SearchInput,
    SearchOutput,
)

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

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
        }
        return {k: v for k, v in params.items() if v is not None}

    @retry(
        reraise=True,
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=0.4, min=0.4, max=3),
        retry=retry_if_exception_type(Exception),
    )
    def _call(self, params: Mapping[str, Any]) -> Dict[str, Any]:
        logger.debug("tavily.search params=%s", params)
        return self._client.search(**dict(params))

    def search(self, inp: SearchInput) -> SearchOutput:
        raw = self._call(self._build_params(inp))
        items: List[ResultItem] = []
        for r in (raw.get("results", []) or []):
            item: ResultItem = {
                "title": str(r.get("title", "")),
                "url": str(r.get("url", "")),
                "source": str(r.get("source", "")),
            }
            if "published_date" in r:
                item["published_date"] = str(r["published_date"])
            if "content" in r:
                item["snippet"] = str(r["content"])[:280]
            if isinstance(r.get("score"), (int, float)):
                item["score"] = float(r["score"])
            items.append(item)
        return SearchOutput(results=items, answer=raw.get("answer"), usage=raw.get("usage"))

# ---------- Main (smoke test) ----------
if __name__ == "__main__":
    
    # Quick end-to-end sanity checks
    tool = TavilySearchTool(settings=tavily_settings)

    tests: list[SearchInput] = [
        SearchInput(q="Any NSE circulars on NIFTY 50 rebalancing this week", time_range="7d", max_results=5),
        SearchInput(q="RBI policy highlights impact on equities today", time_range="1d"),
        SearchInput(q="Bulk or block deals for RELIANCE today", time_range="1d"),
        SearchInput(q="ASM/GSM surveillance list updates affecting portfolio", time_range="7d"),
    ]

    for i, t in enumerate(tests, 1):
        out = tool.search(t)
        print(f"\n[{i}] Query: {t.q}  | results={len(out.results)}")
        for r in out.results[:3]:
            print(f"- {r.get('title','')} | {r.get('source','')} | {r.get('url','')}")
