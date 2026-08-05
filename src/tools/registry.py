"""
Centralized Tool Registry with category-based routing.

When the function count grows to 80-100+, injecting every docstring into the
code-generation prompt wastes tokens and confuses the LLM.  Instead we:

1. Register every callable with one or more *categories* (tags).
2. At prompt-build time, a lightweight **router** (keyword / embedding match)
   selects only the relevant categories for the user's query.
3. Only those function signatures + docstrings are injected into the prompt.

Categories
----------
  VALUATION        – P/E, P/B, P/S, PEG, EV/EBITDA, …
  PROFITABILITY    – ROE, ROI, profit margin, EBITDA margin, …
  LIQUIDITY        – current ratio, quick ratio, cash ratio, …
  LEVERAGE         – D/E, interest coverage, debt ratio, …
  EFFICIENCY       – asset turnover, inventory turnover, receivable turnover, …
  GROWTH           – CAGR, revenue growth, earnings growth, …
  RISK             – Sharpe, Sortino, beta, alpha, VaR, max drawdown, volatility, …
  DIVIDEND         – dividend yield, payout ratio, dividend growth, …
  TECHNICAL        – RSI, MACD, moving averages, Bollinger bands, …
  TRADING          – win rate, profit factor, expectancy, …
  PRICE_DATA       – current price, historical prices, batch prices, …
  FINANCIAL_STMT   – balance sheet, income statement, cash flow, …
  EARNINGS_EST     – EPS estimates, revenue estimates, growth estimates, …
  OWNERSHIP        – institutional holders, insider transactions, …
  SCREENING        – filters (growth, value, momentum), …
  PORTFOLIO_CALC   – P&L, allocation, portfolio return, …
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import Callable, Dict, FrozenSet, List, Optional, Set, Tuple

# ── Category enum-like constants ────────────────────────────────────────────

VALUATION = "VALUATION"
PROFITABILITY = "PROFITABILITY"
LIQUIDITY = "LIQUIDITY"
LEVERAGE = "LEVERAGE"
EFFICIENCY = "EFFICIENCY"
GROWTH = "GROWTH"
RISK = "RISK"
DIVIDEND = "DIVIDEND"
TECHNICAL = "TECHNICAL"
TRADING = "TRADING"
PRICE_DATA = "PRICE_DATA"
FINANCIAL_STMT = "FINANCIAL_STMT"
EARNINGS_EST = "EARNINGS_EST"
OWNERSHIP = "OWNERSHIP"
SCREENING = "SCREENING"
PORTFOLIO_CALC = "PORTFOLIO_CALC"

ALL_CATEGORIES: FrozenSet[str] = frozenset(
    {
        VALUATION,
        PROFITABILITY,
        LIQUIDITY,
        LEVERAGE,
        EFFICIENCY,
        GROWTH,
        RISK,
        DIVIDEND,
        TECHNICAL,
        TRADING,
        PRICE_DATA,
        FINANCIAL_STMT,
        EARNINGS_EST,
        OWNERSHIP,
        SCREENING,
        PORTFOLIO_CALC,
    }
)


# ── Keyword → category mapping for the lightweight router ──────────────────

_CATEGORY_KEYWORDS: Dict[str, List[str]] = {
    VALUATION: [
        "p/e",
        "pe ratio",
        "price to earnings",
        "p/b",
        "price to book",
        "p/s",
        "price to sales",
        "peg",
        "ev/ebitda",
        "enterprise value",
        "valuation",
        "overvalued",
        "undervalued",
        "fair value",
        "intrinsic",
    ],
    PROFITABILITY: [
        "roe",
        "return on equity",
        "roi",
        "return on investment",
        "roa",
        "return on assets",
        "profit margin",
        "ebitda margin",
        "operating margin",
        "net margin",
        "gross margin",
        "profitability",
        "dupont",
    ],
    LIQUIDITY: [
        "current ratio",
        "quick ratio",
        "cash ratio",
        "liquidity",
        "working capital",
    ],
    LEVERAGE: [
        "debt to equity",
        "d/e",
        "leverage",
        "interest coverage",
        "debt ratio",
        "equity multiplier",
        "financial leverage",
    ],
    EFFICIENCY: [
        "asset turnover",
        "inventory turnover",
        "receivable turnover",
        "payable turnover",
        "efficiency",
        "operating cycle",
        "cash conversion",
    ],
    GROWTH: [
        "cagr",
        "growth rate",
        "revenue growth",
        "earnings growth",
        "compound annual",
        "yoy",
        "year over year",
    ],
    RISK: [
        "sharpe",
        "sortino",
        "beta",
        "alpha",
        "volatility",
        "risk",
        "drawdown",
        "var",
        "value at risk",
        "standard deviation",
        "downside deviation",
        "tracking error",
        "information ratio",
        "treynor",
    ],
    DIVIDEND: [
        "dividend",
        "yield",
        "payout ratio",
        "dividend growth",
        "income",
    ],
    TECHNICAL: [
        "rsi",
        "macd",
        "moving average",
        "sma",
        "ema",
        "bollinger",
        "technical",
        "momentum",
        "stochastic",
        "atr",
        "obv",
    ],
    TRADING: [
        "win rate",
        "profit factor",
        "expectancy",
        "risk reward",
        "trades",
        "trading",
    ],
    PRICE_DATA: [
        "price",
        "close price",
        "current price",
        "historical price",
        "stock price",
        "last price",
    ],
    FINANCIAL_STMT: [
        "balance sheet",
        "income statement",
        "cash flow",
        "financial statement",
        "financials",
        "quarterly results",
    ],
    EARNINGS_EST: [
        "eps",
        "earnings estimate",
        "revenue estimate",
        "earnings history",
        "eps trend",
        "eps revision",
        "growth estimate",
        "analyst",
    ],
    OWNERSHIP: [
        "institutional",
        "insider",
        "mutual fund holder",
        "major holder",
        "ownership",
        "promoter",
    ],
    SCREENING: [
        "screen",
        "filter",
        "find stocks",
        "top stocks",
        "best stocks",
        "growth stocks",
        "value stocks",
    ],
    PORTFOLIO_CALC: [
        "profit",
        "loss",
        "p&l",
        "allocation",
        "portfolio return",
        "holdings",
        "my portfolio",
        "my stocks",
    ],
}


@dataclass
class ToolEntry:
    """A single registered tool/function."""

    name: str
    func: Callable
    categories: FrozenSet[str]
    description: str = ""  # auto-populated from docstring if empty

    def __post_init__(self) -> None:
        if not self.description and self.func.__doc__:
            self.description = self.func.__doc__.strip()


class ToolRegistry:
    """Central registry of all deterministic tool functions."""

    def __init__(self) -> None:
        self._entries: Dict[str, ToolEntry] = {}

    # ── Registration ────────────────────────────────────────────────────

    def register(
        self,
        func: Callable,
        categories: Set[str] | FrozenSet[str] | List[str],
        name: Optional[str] = None,
    ) -> Callable:
        """Register a function under one or more categories. Returns func unchanged."""
        n = name or func.__name__
        cats = frozenset(categories)
        self._entries[n] = ToolEntry(name=n, func=func, categories=cats)
        return func

    def register_many(
        self,
        funcs: List[Callable],
        categories: Set[str] | FrozenSet[str] | List[str],
    ) -> None:
        """Convenience: register a list of functions under the same categories."""
        for f in funcs:
            self.register(f, categories)

    # ── Lookup ──────────────────────────────────────────────────────────

    def get_by_category(self, *categories: str) -> List[ToolEntry]:
        """Return all entries matching ANY of the given categories."""
        cats = set(categories)
        return [e for e in self._entries.values() if e.categories & cats]

    def get_all(self) -> List[ToolEntry]:
        return list(self._entries.values())

    def get_func(self, name: str) -> Callable:
        return self._entries[name].func

    def all_names(self) -> Tuple[str, ...]:
        return tuple(sorted(self._entries.keys()))

    def build_exec_env(self, categories: Optional[Set[str]] = None) -> Dict[str, object]:
        """Build a sandboxed exec() namespace, optionally filtered by categories."""
        env: Dict[str, object] = {"__builtins__": __builtins__}
        entries = self.get_by_category(*categories) if categories else self.get_all()
        for e in entries:
            env[e.name] = e.func
        return env

    # ── Docstring generation for prompt injection ───────────────────────

    def get_signatures(self, categories: Optional[Set[str]] = None) -> str:
        """Generate function signature + docstring stubs for prompt injection."""
        entries = self.get_by_category(*categories) if categories else self.get_all()
        parts = []
        for e in sorted(entries, key=lambda x: x.name):
            sig = inspect.signature(e.func)
            doc = (e.func.__doc__ or "").strip()
            parts.append(f'def {e.name}{sig}:\n    """{doc}"""')
        return "\n\n".join(parts)

    # ── Lightweight keyword router ──────────────────────────────────────

    def route_query(self, query: str, top_k: int = 4) -> List[str]:
        """Given a user query, return the top-k most relevant category names.

        Uses simple keyword matching. For production at scale, swap this with
        an embedding-based classifier (e.g. a small fine-tuned model or
        cosine similarity against category descriptions).
        """
        query_lower = query.lower()
        scores: Dict[str, float] = {cat: 0.0 for cat in ALL_CATEGORIES}

        for cat, keywords in _CATEGORY_KEYWORDS.items():
            for kw in keywords:
                if kw in query_lower:
                    scores[cat] += 1.0

        # Always include PRICE_DATA and PORTFOLIO_CALC as baseline
        scores[PRICE_DATA] += 0.1
        scores[PORTFOLIO_CALC] += 0.1

        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        # Return categories with score > 0, up to top_k
        return [cat for cat, score in ranked[:top_k] if score > 0]


# ── Global singleton ───────────────────────────────────────────────────────

registry = ToolRegistry()
