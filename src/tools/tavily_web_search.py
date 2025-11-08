# file: finto/search/tavily_tool.py
from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Literal, Optional

from langchain.tools import StructuredTool
from langgraph.prebuilt import ToolNode
from pydantic import BaseModel, Field
from tavily import TavilyClient
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

# --------- Opinionated finance/India allow-list ----------
DEFAULT_ALLOWLIST: List[str] = [
    "nseindia.com",
    "bseindia.com",
    "sebi.gov.in",
    "reuters.com",
    "economictimes.indiatimes.com",
    "moneycontrol.com",
    "livemint.com",
    "business-standard.com",
]

# --------- Minimal, typed input/output ----------
TimeRange = Literal["1d", "3d", "7d", "30d"]
Depth = Literal["basic", "advanced"]


class SearchInput(BaseModel):
    q: str = Field(..., description="Natural language query (tickers/sectors/macro).")
    time_range: TimeRange = "1d"
    max_results: int = Field(6, ge=1, le=20)
    depth: Depth = "basic"
    sites_allow: Optional[List[str]] = None
    sites_block: Optional[List[str]] = None


class SearchOutput(BaseModel):
    results: List[Dict[str, Any]] = Field(default_factory=list)
    answer: Optional[str] = None
    usage: Optional[Dict[str, Any]] = None


# --------- Tool (thin, deterministic wrapper) ----------
class TavilySearchTool:
    """
    Finance-focused Tavily search with India-first defaults.
    Keep it simple: choose a horizon, depth, and (optionally) tweak domain lists.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        default_allowlist: Optional[List[str]] = None,
    ):
        api_key = api_key or os.getenv("TAVILY_API_KEY")
        if not api_key:
            raise RuntimeError("Missing TAVILY_API_KEY")
        self.client = TavilyClient(api_key=api_key)
        self.default_allowlist = default_allowlist or DEFAULT_ALLOWLIST

    def _params(self, inp: SearchInput) -> Dict[str, Any]:
        # Favor official/regulatory + reputable finance sources by default
        include_domains = inp.sites_allow or self.default_allowlist
        params: Dict[str, Any] = {
            "query": inp.q,
            "time_range": inp.time_range,
            "search_depth": inp.depth,
            "max_results": inp.max_results,
            "include_domains": include_domains,
            "exclude_domains": inp.sites_block,
            # Keep the API surface tiny; Tavily tolerates omitted extras.
        }
        # Drop Nones
        return {k: v for k, v in params.items() if v is not None}

    @retry(
        reraise=True,
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=0.4, min=0.4, max=3),
        retry=retry_if_exception_type(Exception),
    )
    def _call(self, params: Dict[str, Any]) -> Dict[str, Any]:
        logger.debug("tavily.search params=%s", params)
        return self.client.search(**params)

    def search(self, inp: SearchInput) -> SearchOutput:
        raw = self._call(self._params(inp))
        return SearchOutput(
            results=raw.get("results", []),
            answer=raw.get("answer"),
            usage=raw.get("usage"),
        )

    # --------- LangChain adapter (optional) ----------
    def as_langchain_tool(self) -> "StructuredTool":
        if StructuredTool is None:
            raise RuntimeError("langchain not installed")

        def _fn(**kwargs) -> Dict[str, Any]:
            out = self.search(SearchInput(**kwargs))
            return out.model_dump()

        return StructuredTool.from_function(
            name="web_search",
            description=(
                "Finance-focused web search (India-first). "
                "Use for timely news/circulars/events affecting NSE/BSE tickers or sectors."
            ),
            func=_fn,
            args_schema=SearchInput,
            return_direct=False,
        )

    # --------- LangGraph adapter (optional) ----------
    def as_langgraph_node(self) -> "ToolNode":
        if ToolNode is None:
            raise RuntimeError("langgraph not installed")
        return ToolNode(tools=[self.as_langchain_tool()])


# --------- Example (manual run) ----------
if __name__ == "__main__":
    tool = TavilySearchTool()
    out = tool.search(
        SearchInput(
            q="NSE circular index rebalancing this week site:nseindia.com",
            time_range="7d",
            depth="basic",
            max_results=5,
        )
    )
    for r in out.results[:3]:
        print("-", r.get("title"), "|", r.get("url"))
