"""Screener node metadata (deterministic screening + HITL; no CodeAct sandbox)."""

from __future__ import annotations

# yfinance wrappers used by :func:`src.tools.screener_tool.run_get_screened_stocks_sync`
# (subset of BOTH_FUNCTIONS ∪ SCREENER_FUNCTIONS).
_SCREENER_TOOL_YF_NAMES: tuple[str, ...] = (
    "get_balance_sheet",
    "get_earnings_estimate",
    "get_income_statement",
    "get_revenue_estimate",
    "get_ticker_info",
)


def screener_analysis_tool_sandbox_function_names() -> tuple[str, ...]:
    """Names exposed to the orchestrator prompt as internal screener capabilities."""
    return _SCREENER_TOOL_YF_NAMES
