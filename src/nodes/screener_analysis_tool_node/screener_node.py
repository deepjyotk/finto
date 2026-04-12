"""Screener node: deterministic screening with HITL parameter form (LangGraph interrupt)."""

from __future__ import annotations

import asyncio
import json
from functools import partial
from pathlib import Path
from typing import Any, cast

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableLambda
from langchain_core.tools import BaseTool, tool
from langgraph.runtime import get_runtime
from langgraph.types import interrupt
from pydantic import BaseModel, Field

from src.core.enums import LLMModel
from src.core.json_logging import logger_for
from src.core.llm import LLMFactory
from src.schemas.agent_state import AgentContext, AgentState
from src.tools.screener_tool import _MEDIUM_DEFAULTS, run_get_screened_stocks_sync

logger = logger_for(__name__)

_HITL_FORM_PATH = Path(__file__).resolve().parent / "screener_hitl_a2ui_form.json"


def _load_hitl_a2ui_form() -> dict[str, Any]:
    try:
        raw = _HITL_FORM_PATH.read_text(encoding="utf-8")
        return cast(dict[str, Any], json.loads(raw))
    except (OSError, json.JSONDecodeError) as e:
        logger.error("Failed to load HITL A2UI form from %s: %s", _HITL_FORM_PATH, e)
        return {
            "type": "a2ui_response",
            "root": ["note"],
            "components": {
                "note": {
                    "type": "info-box",
                    "props": {"text": "Screener form asset missing on server.", "variant": "error"},
                }
            },
        }


class _UniverseSymbols(BaseModel):
    """LLM output: NSE tickers to pass through deterministic filters."""

    symbols: list[str] = Field(
        ...,
        min_length=1,
        max_length=120,
        description=(
            "NSE (India) tickers as Yahoo Finance symbols with .NS suffix only "
            "(e.g. RELIANCE.NS, TCS.NS, HDFCBANK.NS). No US or other exchanges."
        ),
    )


def _normalize_to_nse_symbols(symbols: list[str]) -> list[str]:
    """Map labels to Yahoo NSE symbols (.NS). Drops non-Indian / ambiguous tickers."""
    out: list[str] = []
    for raw in symbols:
        if not isinstance(raw, str):
            continue
        t = raw.strip().upper()
        if not t:
            continue
        if t.endswith(".NS"):
            out.append(t)
        elif t.endswith(".BO"):
            out.append(t[: -len(".BO")] + ".NS")
        elif "." in t:
            # e.g. US tickers — skip
            continue
        else:
            out.append(f"{t}.NS")
    return list(dict.fromkeys(out))


def _extract_candidate_symbols(llm: BaseChatModel, task: str) -> list[str]:
    """Use a small structured LLM call to propose an NSE-only stock universe from the task text."""
    structured = llm.with_structured_output(_UniverseSymbols)
    messages = [
        SystemMessage(
            content=(
                "You propose stock ticker symbols for the National Stock Exchange of India (NSE) only. "
                "Every symbol MUST be a valid Yahoo Finance NSE ticker ending with .NS "
                "(e.g. RELIANCE.NS, TCS.NS, INFY.NS, HDFCBANK.NS). "
                "Do not use US symbols (e.g. AAPL), .BO (BSE), or other exchanges. "
                "Include 25–60 liquid NSE names relevant to the user's sector/theme when the task is broad; "
                "if the user names specific Indian stocks, output those as .NS. Do not include duplicates."
            )
        ),
        HumanMessage(content=task),
    ]
    try:
        raw = structured.invoke(messages)
        if not isinstance(raw, _UniverseSymbols):
            return []
        out = raw
        cleaned = [s.strip().upper() for s in out.symbols if isinstance(s, str) and s.strip()]
        deduped = list(dict.fromkeys(cleaned))
        return _normalize_to_nse_symbols(deduped)
    except Exception as e:
        logger.warning("Structured universe extraction failed, falling back to []: %s", e)
        return []


def _parse_form_values_to_kwargs(values: dict[str, Any]) -> dict[str, Any]:
    """Map client form payload (from a2ui-form-submit) to run_get_screened_stocks_sync kwargs."""
    out: dict[str, Any] = dict(_MEDIUM_DEFAULTS)
    float_keys = (
        "pe_min",
        "pe_max",
        "peg_min",
        "peg_max",
        "pb_max",
        "ps_max",
        "ev_ebitda_max",
        "roe_min_pct",
        "roic_min_pct",
        "operating_margin_min_pct",
        "revenue_growth_yoy_min_pct",
        "eps_growth_yoy_min_pct",
        "debt_to_equity_max",
        "interest_coverage_min",
        "current_ratio_min",
        "market_cap_min_usd",
        "beta_min",
        "beta_max",
        "dividend_yield_min_pct",
        "payout_ratio_max_pct",
    )
    for k in float_keys:
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

    if "max_results" in values:
        raw = values["max_results"]
        try:
            out["max_results"] = int(float(raw)) if raw not in (None, "") else _MEDIUM_DEFAULTS["max_results"]
        except (TypeError, ValueError):
            out["max_results"] = _MEDIUM_DEFAULTS["max_results"]

    uh = values.get("universe_hint")
    if uh is not None and str(uh).strip():
        out["universe_hint"] = str(uh).strip()
    else:
        out["universe_hint"] = None

    return out


class ScreenerNode:
    """Screener: resolve a candidate universe, interrupt for HITL params, run deterministic screen."""

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
            runtime = get_runtime(AgentContext)
            context = runtime.context
            screener_model = context.get("screener_model", LLMModel.GPT4p1)
            llm = node._llm_factory(screener_model)

            symbols_ctx = list(context.get("screener_candidate_symbols") or [])
            candidate_symbols = (
                _normalize_to_nse_symbols(symbols_ctx)
                if symbols_ctx
                else _extract_candidate_symbols(llm, task)
            )
            if not candidate_symbols:
                return (
                    "ERROR: No candidate symbols to screen. "
                    "Describe a sector/universe or list tickers in your request."
                )

            # Expose for tools that read AgentContext (e.g. get_screened_stocks)
            context["screener_candidate_symbols"] = candidate_symbols

            form_json = _load_hitl_a2ui_form()
            payload = {
                "kind": "hitl_screener",
                "a2ui_form": form_json,
                "candidate_symbols": candidate_symbols,
                "task": task,
                "defaults": dict(_MEDIUM_DEFAULTS),
            }

            resume_values = interrupt(payload)
            if not isinstance(resume_values, dict):
                return "ERROR: HITL resume payload must be a dict of form field values."

            merged = {**resume_values}
            kwargs = _parse_form_values_to_kwargs(merged)

            return await asyncio.to_thread(
                partial(run_get_screened_stocks_sync, candidate_symbols, **kwargs)
            )

        return screener_analysis_tool

    def get_runnable_sequence(self) -> RunnableLambda[AgentState, AgentState]:
        """Return a runnable for direct graph wiring (unused in current hub-spoke design)."""

        async def screener_node_fn(state: AgentState) -> AgentState:
            return state

        return RunnableLambda(screener_node_fn)
