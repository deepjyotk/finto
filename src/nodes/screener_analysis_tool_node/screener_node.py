"""Screener node: deterministic screening with HITL parameter form (LangGraph interrupt)."""

from __future__ import annotations

import asyncio
from functools import partial
from typing import Any

from langchain_core.runnables import RunnableLambda
from langchain_core.tools import BaseTool, tool
from langgraph.types import interrupt
from sqlalchemy import text

from src.core.db import SessionLocal
from src.core.json_logging import logger_for
from src.core.llm import LLMFactory
from src.nodes.screener_analysis_tool_node.screener_hitl_form_builder import (
    build_screener_hitl_a2ui_messages,
)
from src.schemas.agent_state import AgentState
from src.tools.screener_tool import (
    _MEDIUM_DEFAULTS,
    ScreenerRunRequest,
    enabled_medium_hitl_param_names,
    run_get_screened_stocks_sync,
)

logger = logger_for(__name__)


async def _load_all_equity_symbols() -> list[str]:
    """Load full NSE universe from `in_equities` and map to Yahoo `.NS` format."""
    async with SessionLocal() as session:
        result = await session.execute(text("SELECT symbol FROM in_equities ORDER BY symbol"))
        symbols: list[str] = []
        for row in result:
            raw = row[0]
            if not raw or not isinstance(raw, str):
                continue
            sym = raw.strip().upper()
            if not sym:
                continue
            symbols.append(sym if sym.endswith(".NS") else f"{sym}.NS")
    return list(dict.fromkeys(symbols))


def _parse_form_values_to_request(values: dict[str, Any]) -> ScreenerRunRequest:
    """Map form payload to a typed screener run request."""
    out: dict[str, Any] = dict(_MEDIUM_DEFAULTS)
    for k in enabled_medium_hitl_param_names():
        if k not in values:
            continue
        raw = values[k]
        if raw is None or (isinstance(raw, str) and raw.strip() == ""):
            out[k] = None
            continue
        try:
            out[k] = float(raw)
        except (TypeError, ValueError):
            pass

    return ScreenerRunRequest.from_values(out)


class ScreenerNode:
    """Screener: load all equities, collect HITL params, run deterministic screen."""

    def __init__(self, llm_factory: LLMFactory) -> None:
        self._llm_factory = llm_factory

    def create_worker_tool(self) -> BaseTool:
        """Build screener_analysis_tool for the orchestrator (HITL + deterministic screen)."""

        node = self

        @tool
        async def screener_analysis_tool(task: str) -> str:
            """Screen the broader market for stocks matching specific criteria.

            Use for finding, filtering, and ranking stocks by fundamentals, valuation,
            growth trends, or any quantitative strategy. Does NOT access the user's
            portfolio — call financial_analysis_tool for portfolio-related questions.

            Args:
                task: Screening strategy and criteria with universe hints (sector, region, count).
            """
            all_equities = await _load_all_equity_symbols()
            if not all_equities:
                return "ERROR: No equities found in in_equities table."

            enabled_fields = enabled_medium_hitl_param_names()
            form_messages = build_screener_hitl_a2ui_messages(
                defaults=dict(_MEDIUM_DEFAULTS), enabled_fields=enabled_fields
            )
            payload = {
                "kind": "hitl_screener",
                "a2ui_messages": form_messages,
                "all_equities_count": len(all_equities),
                "task": task,
                "defaults": dict(_MEDIUM_DEFAULTS),
            }

            resume_values = interrupt(payload)
            if not isinstance(resume_values, dict):
                return "ERROR: HITL resume payload must be a dict of form field values."

            merged = {**resume_values}
            request = _parse_form_values_to_request(merged)

            return await asyncio.to_thread(
                partial(run_get_screened_stocks_sync, all_equities, request)
            )

        return screener_analysis_tool

    def get_runnable_sequence(self) -> RunnableLambda[AgentState, AgentState]:
        """Return a runnable for direct graph wiring (unused in current hub-spoke design)."""

        async def screener_node_fn(state: AgentState) -> AgentState:
            return state

        return RunnableLambda(screener_node_fn)
