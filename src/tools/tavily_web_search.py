#! TODO: the current implementation is WIP, dont use it yet

# file: finto/search/tavily_tool.py
from __future__ import annotations

import logging
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings
from tavily import TavilyClient
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

try:
    from langchain.tools import StructuredTool
    from langgraph.prebuilt import ToolNode
except Exception:
    StructuredTool = None
    ToolNode = None

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


# -----------------------------
# Settings & Constants
# -----------------------------
class TavilySettings(BaseSettings):
    TAVILY_API_KEY: str = Field(..., description="Tavily API key")
    TAVILY_DEFAULT_MAX_RESULTS: int = 5
    TAVILY_DEFAULT_SEARCH_DEPTH: Literal["basic", "advanced"] = "basic"
    TAVILY_DEFAULT_TIME_RANGE: str = "w"
    TAVILY_DEFAULT_INCLUDE_ANSWER: bool = True
    TAVILY_DEFAULT_INCLUDE_RAW: bool = True
    TAVILY_DEFAULT_AUTO_PARAMETERS: bool = False

    # India finance authoritative domains (adjust as needed)
    TAVILY_FINANCE_WHITELIST: List[str] = [
        "nseindia.com",
        "bseindia.com",
        "sebi.gov.in",
        "rbi.org.in",
        "mca.gov.in",
    ]

    model_config = {
        "env_file": ".env",
        "case_sensitive": True,
        "extra": "ignore",  # Ignore extra fields from .env
    }


# -----------------------------
# Models
# -----------------------------
Topic = Literal["finance", "general", "news", "technology", "science"]


class TavilySearchParams(BaseModel):
    query: str = Field(..., description="Natural language search query.")
    topic: Topic = Field("finance", description="Topical bias for the search.")
    max_results: int = Field(5, ge=1, le=20)
    include_answer: bool = True
    include_raw_content: bool = True
    search_depth: Literal["basic", "advanced"] = "basic"
    time_range: Optional[str] = Field("w", description="d/w/m/y or day/week/month/year")
    include_domains: Optional[List[str]] = None
    exclude_domains: Optional[List[str]] = None
    country: Optional[str] = None
    language: Optional[str] = None
    auto_parameters: bool = False

    @field_validator("include_domains", "exclude_domains", mode="before")
    @classmethod
    def empty_to_none(cls, v):
        return v or None


class TavilySearchResult(BaseModel):
    answer: Optional[str]
    results: List[Dict[str, Any]] = Field(default_factory=list)
    usage: Optional[Dict[str, Any]] = None


# -----------------------------
# Tool Implementation
# -----------------------------
class TavilySearchTool:
    """
    Thin, typed wrapper over TavilyClient with sensible defaults for finance use cases.
    """

    def __init__(self, settings: Optional[TavilySettings] = None):
        self.settings = settings or TavilySettings()
        self._client = TavilyClient(api_key=self.settings.TAVILY_API_KEY)

    def _defaulted_params(self, p: TavilySearchParams) -> Dict[str, Any]:
        # Apply opinionated defaults if caller omitted fields
        include_domains = (
            p.include_domains or self.settings.TAVILY_FINANCE_WHITELIST
            if p.topic == "finance"
            else None
        )
        return {
            "query": p.query,
            "topic": p.topic,
            "max_results": p.max_results or self.settings.TAVILY_DEFAULT_MAX_RESULTS,
            "include_answer": (
                p.include_answer
                if p.include_answer is not None
                else self.settings.TAVILY_DEFAULT_INCLUDE_ANSWER
            ),
            "include_raw_content": (
                p.include_raw_content
                if p.include_raw_content is not None
                else self.settings.TAVILY_DEFAULT_INCLUDE_RAW
            ),
            "search_depth": p.search_depth or self.settings.TAVILY_DEFAULT_SEARCH_DEPTH,
            "time_range": p.time_range or self.settings.TAVILY_DEFAULT_TIME_RANGE,
            "include_domains": include_domains,
            "exclude_domains": p.exclude_domains,
            "country": p.country,
            "language": p.language,
            "auto_parameters": (
                p.auto_parameters
                if p.auto_parameters is not None
                else self.settings.TAVILY_DEFAULT_AUTO_PARAMETERS
            ),
        }

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=8),
        retry=retry_if_exception_type(Exception),
    )
    def _call_api(self, params: Dict[str, Any]) -> Dict[str, Any]:
        # Strip Nones (Tavily client prefers omission)
        clean = {k: v for k, v in params.items() if v is not None}
        logger.debug("Tavily request params=%s", clean)
        return self._client.search(**clean)

    def search(self, params: TavilySearchParams) -> TavilySearchResult:
        """
        Perform a Tavily search with robust defaults & retries.
        """
        payload = self._defaulted_params(params)
        raw = self._call_api(payload)

        # Normalize to our result schema
        return TavilySearchResult(
            answer=raw.get("answer"),
            results=raw.get("results", []),
            usage=raw.get("usage"),
        )

    # ---------- LangChain tool factory ----------
    def as_langchain_tool(self) -> "StructuredTool":
        if StructuredTool is None:
            raise RuntimeError("langchain not installed; cannot create StructuredTool")

        def _fn(**kwargs) -> Dict[str, Any]:
            # Accept dict payload; validate to our schema
            model = TavilySearchParams(**kwargs)
            res = self.search(model)
            return res.model_dump()

        return StructuredTool.from_function(
            name="web_search_tavily",
            description=(
                "Finance-focused web search via Tavily. "
                "Use for latest notices/news/corporate actions affecting holdings. "
                "Returns structured results with optional answer."
            ),
            func=_fn,
            args_schema=TavilySearchParams,  # typed inputs for tool calling / function-calling LLMs
            return_direct=False,
        )

    # ---------- LangGraph node ----------
    def as_langgraph_node(self) -> "ToolNode":
        if ToolNode is None:
            raise RuntimeError("langgraph not installed; cannot create ToolNode")
        tool = self.as_langchain_tool()
        return ToolNode(tools=[tool])


# -----------------------------
# Example wiring (optional)
# -----------------------------
if __name__ == "__main__":
    settings = TavilySettings()
    tool = TavilySearchTool(settings=settings)
    params = TavilySearchParams(
        query="Latest NSE circulars impacting index rebalancing this week",
        topic="finance",
        time_range="w",
        search_depth="basic",
        max_results=5,
        include_domains=["nseindia.com", "bseindia.com", "sebi.gov.in"],
        country="India",
        language="en",
    )
    result = tool.search(params)
    print(f"Answer: {result.answer}")
    for r in result.results[:3]:
        print("-", r.get("title"), "|", r.get("url"))
