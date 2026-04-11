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
from typing import Any, Literal

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

# Low-level LangChain runnables that fire many nested ``on_chain_*`` events — surfacing
# them would spam the timeline with duplicate "Thinking" rows without adding signal.
_SUPPRESSED_AUX_CHAIN_NAMES: frozenset[str] = frozenset(
    {
        "RunnableSequence",
        "RunnableParallel",
        "RunnableLambda",
        "RunnableAssign",
        "RunnablePassthrough",
        "RunnableBranch",
        "RunnableBinding",
        "RunnablePick",
        "RunnableMap",
        "RunnableGenerator",
        "RunnableEach",
        "RunnableRetry",
        "RunnableWithFallbacks",
    }
)


def _aux_chain_step_name(chain_name: str) -> str:
    """Stable id for a non–graph-node chain; must match between start and end events."""
    return f"__chain:{chain_name}"

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


def _stream_delta_to_text(content: Any) -> str | None:
    """Extract text from one chat-model stream chunk without trimming.

    Per-chunk :meth:`str.strip` would remove leading/trailing spaces from each
    token delta; spaces often arrive as the first character of the following
    chunk, so stripping breaks JSON string literals (e.g. ``Top`` + `` 5`` →
    ``Top5``).
    """
    if content is None:
        return None
    if isinstance(content, str):
        return content if content else None
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict):
                parts.append(str(block.get("text") or block.get("content") or ""))
            else:
                parts.append(str(block))
        joined = "".join(parts)
        return joined if joined else None
    text = str(content)
    return text if text else None


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
# Main transformer — per LangChain ``astream_events`` event type
# ---------------------------------------------------------------------------


def _handle_on_chain_start(
    _lg_event: dict[str, Any], name: str, _data: dict[str, Any]
) -> A2UIEvent | None:
    """Graph / chain step started → ``step_start`` or ``None``."""
    if name in _TRACKED_NODES:
        meta = _NODE_LABELS[name]
        return make_step_start(
            step_name=name,
            title=meta["title"],
            description=meta.get("description"),
        )
    if not (name and str(name).strip()):
        return None
    if name in _SUPPRESSED_AUX_CHAIN_NAMES:
        return None
    step_name = _aux_chain_step_name(name)
    return None
    # return make_step_start(
    #     step_name=step_name,
    #     title="Thinking…",
    #     description="Working through the next step before continuing",
    # )


def _handle_on_chain_end(
    _lg_event: dict[str, Any], name: str, data: dict[str, Any]
) -> A2UIEvent | None:
    """Graph / chain step finished → ``step_complete`` or ``None``."""
    if name in _TRACKED_NODES:
        meta = _NODE_LABELS[name]
        return make_step_complete(step_name=name, title=meta["title"], status="done")
    if not (name and str(name).strip()):
        return None
    if name in _SUPPRESSED_AUX_CHAIN_NAMES:
        return None
    step_name = _aux_chain_step_name(name)
    output = data.get("output")
    err = data.get("error")
    status: Literal["done", "error"] = (
        "error" if (err is not None or isinstance(output, Exception)) else "done"
    )
    return make_step_complete(step_name=step_name, title="Thinking…", status=status)


def _handle_on_tool_start(
    lg_event: dict[str, Any], name: str, data: dict[str, Any]
) -> A2UIEvent | None:
    """Tool invocation started → ``tool_call``."""
    parent_node = _extract_parent_node(lg_event)
    return make_tool_call(
        tool_name=name,
        display_name=_tool_display_name(name),
        step_name=parent_node or "orchestrator_node",
        input_summary=_safe_input_summary(data),
    )


def _handle_on_tool_end(
    lg_event: dict[str, Any], name: str, data: dict[str, Any]
) -> A2UIEvent | None:
    """Tool finished → ``tool_result``."""
    parent_node = _extract_parent_node(lg_event)
    output = data.get("output")
    status = "error" if isinstance(output, Exception) else "success"
    return make_tool_result(
        tool_name=name,
        step_name=parent_node or "orchestrator_node",
        output_summary=_safe_output_summary(data),
        status=status,
    )


def _handle_on_chat_model_stream(
    lg_event: dict[str, Any], _name: str, data: dict[str, Any]
) -> A2UIEvent | None:
    """Chat model token chunk → ``message_chunk`` only from the final response node."""
    parent_node = _extract_parent_node(lg_event)
    if parent_node != "final_response_generation_node":
        return None
    chunk_data = data.get("chunk")
    if chunk_data is None:
        return None
    content = getattr(chunk_data, "content", None)
    text = _stream_delta_to_text(content)
    if text is None:
        return None
    return make_message_chunk(text)


def build_a2ui_event(lg_event: dict[str, Any]) -> A2UIEvent | None:
    """Convert one LangGraph astream_events (v2) event into an A2UI event.

    Returns ``None`` for events that should not be forwarded to the client
    (e.g. internal plumbing, duplicate chain events, unknown nodes).
    """
    event_type: str = lg_event.get("event", "")
    name: str = lg_event.get("name", "")
    data: dict[str, Any] = lg_event.get("data", {}) or {}

    match event_type:
        case "on_chain_start":
            return _handle_on_chain_start(lg_event, name, data)
        case "on_chain_end":
            return _handle_on_chain_end(lg_event, name, data)
        case "on_tool_start":
            return _handle_on_tool_start(lg_event, name, data)
        case "on_tool_end":
            return _handle_on_tool_end(lg_event, name, data)
        case "on_chat_model_stream":
            return _handle_on_chat_model_stream(lg_event, name, data)
        case _:
            # e.g. on_llm_*, on_prompt_*, on_retriever_*, on_chain_stream, model start/end
            return None
