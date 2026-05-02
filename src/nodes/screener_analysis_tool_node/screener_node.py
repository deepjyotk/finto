"""Screener node: deterministic screening with HITL parameter form (LangGraph interrupt)."""

from __future__ import annotations

from typing import Any, TypeVar

from langchain_core.runnables import RunnableLambda
from langchain_core.tools import BaseTool, tool
from langgraph.types import interrupt
from sqlalchemy import text

from src.a2ui.catalog import A2UI_HITL_SURFACE_ID
from src.core.db import SessionLocal
from src.core.json_logging import logger_for
from src.core.llm import LLMFactory
from src.nodes.screener_analysis_tool_node.screener_hitl_form_builder import (
    build_category_form_a2ui_messages,
)
from src.nodes.screener_analysis_tool_node.screener_intent_classifier import (
    ScreenerIntentForm,
    classify_screener_intent,
)
from src.schemas.agent_state import AgentState
from src.schemas.screener_tool_schemas import SCREENER_CATEGORY_FORMS
from src.schemas.screener_tool_schemas.base import (
    BaseScreenerForm,
    ScreenerFormField,
)
from src.tools.screener_tool import run_get_screened_stocks_async

logger = logger_for(__name__)

TForm = TypeVar("TForm", bound=BaseScreenerForm)


def _is_dirty_field(field_meta: dict[str, Any], field_name: str) -> bool:
    meta = field_meta.get(field_name)
    return isinstance(meta, dict) and meta.get("dirty") is True


def _dirty_fields_only(fields: dict[str, Any], field_meta: Any) -> dict[str, Any]:
    if not isinstance(field_meta, dict):
        return dict(fields)
    return {
        field_name: value
        for field_name, value in fields.items()
        if field_name != "_intent" and _is_dirty_field(field_meta, field_name)
    }


def _extract_resume_form_values(resume_values: dict[str, Any]) -> dict[str, Any]:
    """Return dirty form values from action context or synced A2UI data model."""
    fields = resume_values.get("fields")
    if isinstance(fields, dict):
        return _dirty_fields_only(fields, resume_values.get("fieldMeta"))

    surfaces = resume_values.get("surfaces")
    if isinstance(surfaces, dict):
        hitl_surface = surfaces.get(A2UI_HITL_SURFACE_ID)
        if isinstance(hitl_surface, dict) and isinstance(hitl_surface.get("fields"), dict):
            return _dirty_fields_only(hitl_surface["fields"], hitl_surface.get("fieldMeta"))

    return dict(resume_values)


def _empty_string_to_none(value: Any) -> Any:
    if isinstance(value, str) and value.strip() == "":
        return None
    return value


def _bind_resume_values_to_form(
    form: TForm,
    resume_values: dict[str, Any],
) -> TForm:
    """Bind submitted HITL values into a typed category form.

    Only fields present in the submitted resume payload stay dirty and keep a value.
    Every other screener field is explicitly cleared so downstream screening cannot
    accidentally apply defaults that the user did not submit.
    """
    submitted_values = _extract_resume_form_values(resume_values)
    next_form_data = form.model_dump()

    for field_name in form.__class__.model_fields:
        field_model = getattr(form, field_name, None)
        if not isinstance(field_model, ScreenerFormField):
            continue

        is_submitted = field_name in submitted_values
        next_form_data[field_name] = {
            "value": (
                _empty_string_to_none(submitted_values[field_name]) if is_submitted else None
            ),
            "dirty": is_submitted,
            "is_advanced_filter": field_model.is_advanced_filter,
            "enabled": field_model.enabled,
        }

    return form.__class__.model_validate(next_form_data)


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


class ScreenerNode:
    """Screener: load all equities, collect HITL params, run deterministic screen."""

    def __init__(self, llm_factory: LLMFactory) -> None:
        self._llm_factory = llm_factory

    def create_worker_tool(self) -> BaseTool:
        """Build screener_analysis_tool for the orchestrator (HITL + deterministic screen)."""

        llm_factory = self._llm_factory

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

            intent: ScreenerIntentForm = await classify_screener_intent(task, llm_factory)
            form = SCREENER_CATEGORY_FORMS[intent]()
            form_messages = build_category_form_a2ui_messages(form, intent=intent)

            payload = {
                "kind": "hitl_screener",
                "a2ui_messages": form_messages,
                "all_equities_count": len(all_equities),
                "task": task,
                "intent": intent,
            }

            resume_values = interrupt(payload)
            if not isinstance(resume_values, dict):
                return "ERROR: HITL resume payload must be a dict of form field values."

            submitted_form = _bind_resume_values_to_form(form, resume_values)

            return await run_get_screened_stocks_async(submitted_form)

        return screener_analysis_tool

    def get_runnable_sequence(self) -> RunnableLambda[AgentState, AgentState]:
        """Return a runnable for direct graph wiring (unused in current hub-spoke design)."""

        async def screener_node_fn(state: AgentState) -> AgentState:
            return state

        return RunnableLambda(screener_node_fn)
