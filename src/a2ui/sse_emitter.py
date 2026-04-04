"""A2UI SSE emitter.

Provides a single async generator, ``a2ui_sse_generator``, that wraps an
async iterable of A2UI events and yields properly formatted SSE frames.

SSE wire format (per frame)::

    data: {<json>}\n\n

Stream termination::

    data: [DONE]\n\n

Usage::

    from fastapi.responses import StreamingResponse
    from src.a2ui.sse_emitter import a2ui_sse_generator

    return StreamingResponse(
        a2ui_sse_generator(event_stream),
        media_type="text/event-stream",
    )
"""

from __future__ import annotations

import json
from typing import AsyncIterable, AsyncIterator

from src.a2ui.schemas import (
    ErrorEvent,
    MessageCompleteEvent,
    StepCompleteEvent,
    StepStartEvent,
    ToolCallEvent,
    ToolResultEvent,
    MessageChunkEvent,
    A2UIEvent,
    make_error,
)


def _serialize(event: A2UIEvent) -> str:  # type: ignore[type-arg]
    """Serialize a typed A2UI event to a JSON string."""
    # Pydantic v2 model_dump + json.dumps for clean serialisation
    if hasattr(event, "model_dump"):
        return json.dumps(event.model_dump(mode="json"), ensure_ascii=False)
    return json.dumps(event.dict(), ensure_ascii=False)  # pydantic v1 fallback


def _sse_frame(payload: str) -> str:
    return f"data: {payload}\n\n"


async def a2ui_sse_generator(
    event_stream: AsyncIterable[A2UIEvent],  # type: ignore[type-arg]
) -> AsyncIterator[str]:
    """Yield SSE-formatted strings from an async A2UI event stream.

    The generator forwards all events, emits a ``[DONE]`` sentinel on clean
    completion, and emits an ``error`` event followed by ``[DONE]`` when the
    underlying stream raises an exception.
    """
    try:
        async for event in event_stream:
            yield _sse_frame(_serialize(event))
    except Exception as exc:
        error_event = make_error(
            message="An unexpected error occurred while processing your request.",
            code=type(exc).__name__,
        )
        yield _sse_frame(_serialize(error_event))
    finally:
        yield _sse_frame("[DONE]")
