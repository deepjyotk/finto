# file: finto/schemas/tavily.py
from __future__ import annotations

from typing import Any, Dict, Final, List, Literal, TypedDict

from pydantic import BaseModel, ConfigDict, Field

# ---------- Types ----------
TimeRange = Literal["d", "w", "m", "y", "day", "week", "month", "year"]
Depth = Literal["basic", "advanced"]

class ResultItem(TypedDict, total=False):
    title: str
    url: str
    source: str
    published_date: str
    snippet: str
    content: str
    score: float

class SearchInput(BaseModel):
    """Minimal, finance-first search inputs."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    q: str = Field(..., description="Natural language query (tickers/sectors/macro).")
    time_range: TimeRange = "d"
    max_results: int = Field(6, ge=1, le=20)
    depth: Depth = "basic"
    include_raw_content: bool = Field(default=True, description="Whether to include raw content in the search results")


class SearchOutput(BaseModel):
    """Normalized search output (stable surface for the rest of the graph)."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    results: List[ResultItem] = Field(default_factory=list)
    answer: str | None = None
    usage: Dict[str, Any] | None = None

# ---------- Defaults ----------
DEFAULT_ALLOWLIST: Final[tuple[str, ...]] = (
    "nseindia.com",
    "bseindia.com",
    "sebi.gov.in",
    "reuters.com",
    "economictimes.indiatimes.com",
    "moneycontrol.com",
    "livemint.com",
    "business-standard.com",
)

