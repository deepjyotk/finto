"""A2UI event builder.

Converts raw LangGraph ``astream_events`` (v2) output into typed A2UI events
that are safe to expose to end-users.  Only user-visible node transitions
and sanitised tool summaries are surfaced — raw LLM prompts / chain-of-thought
are never included.

Public API
----------
build_a2ui_event(lg_event) -> A2UIEvent | None
    Returns a structured A2UI event or None if the LangGraph event should be
    silently dropped (e.g. internal bookkeeping events).
"""

from __future__ import annotations

import json
from typing import Any

from langchain_core.messages import BaseMessage

from src.a2ui.schemas import (
    A2UIEvent,
    make_message_chunk,
    make_step_complete,
    make_step_start,
    make_tool_call,
    make_tool_result,
)

# ---------------------------------------------------------------------------
# Node name → user-facing display metadata
# ---------------------------------------------------------------------------

_NODE_LABELS: dict[str, dict[str, str]] = {
    "orchestrator_node": {
        "title": "Analyzing request",
        "description": "Planning how to best answer your question",
    },
    "financial_analysis_tool_node": {
        "title": "Calling Arthik Agent",
        "description": "Running financial analysis with your portfolio context",
    },
    "web_search_tool_node": {
        "title": "Searching the web",
        "description": "Gathering latest market and news information",
    },
    "final_response_generation_node": {
        "title": "Generating answer",
        "description": "Composing a clear, structured response",
    },
}

# Nodes that should produce step events (others are silently dropped)
_TRACKED_NODES: frozenset[str] = frozenset(_NODE_LABELS)

# ---------------------------------------------------------------------------
# Tool name → display label
# ---------------------------------------------------------------------------

_TOOL_LABELS: dict[str, str] = {
    "financial_analysis_tool": "Financial Analysis",
    "web_search_worker": "Web search",
    "get_portfolio_metrics": "Portfolio metrics",
    "get_holdings": "Holdings lookup",
    "execute_code": "Code execution",
    "tavily_search": "Market search",
    "tavily_search_results_json": "Market search",
}


def _tool_display_name(tool_name: str) -> str:
    """Return a clean label for a tool name, falling back gracefully."""
    return _TOOL_LABELS.get(tool_name, tool_name.replace("_", " ").title())


def _extract_parent_node(event: dict[str, Any]) -> str:
    """Best-effort extraction of the parent node name from event tags/metadata."""
    tags: list[str] = event.get("tags", []) or []
    # LangGraph injects the parent node name as a tag in the form 'seq:step:N'
    # The metadata dict also carries langgraph_node for recent versions.
    meta: dict[str, Any] = event.get("metadata", {}) or {}
    return meta.get("langgraph_node", "") or ""


def _safe_input_summary(data: dict[str, Any]) -> str | None:
    """Return a one-line, CoT-free summary of tool input data."""
    inp = data.get("input") or {}
    if not inp:
        return None
    if isinstance(inp, dict):
        # Show only the first top-level key/value pair to avoid leaking prompts
        first_key = next(iter(inp), None)
        if first_key:
            val = inp[first_key]
            if isinstance(val, str) and len(val) > 120:
                val = val[:117] + "…"
            return f"{first_key}: {val}"
    return None


def _content_blocks_to_text(content: Any) -> str | None:
    """Normalize LangChain message content (str or multimodal blocks) to plain text."""
    if content is None:
        return None
    if isinstance(content, str):
        stripped = content.strip()
        return stripped or None
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict):
                parts.append(str(block.get("text") or block.get("content") or ""))
            else:
                parts.append(str(block))
        joined = "".join(parts).strip()
        return joined or None
    text = str(content).strip()
    return text or None


def _tool_output_to_text(output: Any) -> str | None:
    """Best-effort string for A2UI; supports ToolMessage, Tavily-style dicts, etc."""
    if isinstance(output, BaseMessage):
        return _content_blocks_to_text(output.content)
    if isinstance(output, str):
        return output.strip() or None
    if isinstance(output, dict):
        for key in ("content", "result", "answer", "message"):
            val = output.get(key)
            if isinstance(val, str) and val.strip():
                return val
        results = output.get("results")
        if isinstance(results, list) and results:
            first = results[0]
            if isinstance(first, dict):
                for rk in ("content", "title", "snippet"):
                    rv = first.get(rk)
                    if isinstance(rv, str) and rv.strip():
                        return rv
        try:
            return json.dumps(output, ensure_ascii=False, default=str)
        except Exception:
            return str(output) or None
    if isinstance(output, (list, tuple)):
        return _content_blocks_to_text(list(output))
    text = str(output).strip()
    return text or None


def _safe_output_summary(data: dict[str, Any]) -> str | None:
    """Return a sanitised one-line summary of tool output."""
    output = data.get("output")
    if output is None:
        return None
    if isinstance(output, Exception):
        text = str(output)
        return text[:200] + ("…" if len(text) > 200 else "")
    text = _tool_output_to_text(output)
    if not text:
        return None
    return text[:200] + ("…" if len(text) > 200 else "")


# ---------------------------------------------------------------------------
# Main transformer
# ---------------------------------------------------------------------------


def build_a2ui_event(lg_event: dict[str, Any]) -> A2UIEvent | None:
    """Convert one LangGraph astream_events (v2) event into an A2UI event.

    Returns ``None`` for events that should not be forwarded to the client
    (e.g. internal plumbing, duplicate chain events, unknown nodes).
    """
    event_type: str = lg_event.get("event", "")
    name: str = lg_event.get("name", "")
    data: dict[str, Any] = lg_event.get("data", {}) or {}

    # -----------------------------------------------------------------------
    # Node lifecycle events → step_start / step_complete
    # -----------------------------------------------------------------------
    if event_type == "on_chain_start" and name in _TRACKED_NODES:
        meta = _NODE_LABELS[name]
        return make_step_start(
            step_name=name,
            title=meta["title"],
            description=meta.get("description"),
        )

    if event_type == "on_chain_end" and name in _TRACKED_NODES:
        meta = _NODE_LABELS[name]
        return make_step_complete(step_name=name, title=meta["title"], status="done")

    # -----------------------------------------------------------------------
    # Tool events → tool_call / tool_result
    # -----------------------------------------------------------------------
    if event_type == "on_tool_start":
        parent_node = _extract_parent_node(lg_event)
        return make_tool_call(
            tool_name=name,
            display_name=_tool_display_name(name),
            step_name=parent_node or "orchestrator_node",
            input_summary=_safe_input_summary(data),
        )

    if event_type == "on_tool_end":
        parent_node = _extract_parent_node(lg_event)
        output = data.get("output")
        status = "error" if isinstance(output, Exception) else "success"
        return make_tool_result(
            tool_name=name,
            step_name=parent_node or "orchestrator_node",
            output_summary=_safe_output_summary(data),
            status=status,
        )

    # -----------------------------------------------------------------------
    # LLM streaming tokens from the final response node only
    # -----------------------------------------------------------------------
    if event_type == "on_chat_model_stream":
        parent_node = _extract_parent_node(lg_event)
        # Only surface tokens that come from the final response node to avoid
        # leaking reasoning / planning LLM calls to the user.
        if parent_node != "final_response_generation_node":
            return None
        chunk_data = data.get("chunk")
        if chunk_data is None:
            return None
        # AIMessageChunk has .content attribute
        content = getattr(chunk_data, "content", None)
        if not content:
            return None
        if isinstance(content, list):
            text = "".join(
                block.get("text", "") if isinstance(block, dict) else str(block)
                for block in content
            )
        else:
            text = str(content)
        if not text:
            return None
        return make_message_chunk(text)

    return None
