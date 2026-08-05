"""A2UI event schemas.

Each SSE frame carries one self-contained event JSON object. The frontend
consumes a mix of app-specific progress events and official A2UI v0.9
server-to-client messages.

No raw prompt text or chain-of-thought is ever included - only
user-visible summaries of what the agent is doing.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Annotated, Any, Literal, Optional, Union
from uuid import uuid4

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Event type discriminant
# ---------------------------------------------------------------------------


class A2UIEventType(str, Enum):
    STEP_START = "step_start"
    STEP_COMPLETE = "step_complete"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    A2UI_MESSAGE = "a2ui_message"
    MESSAGE_CHUNK = "message_chunk"
    MESSAGE_COMPLETE = "message_complete"
    HITL_FORM = "hitl_form"
    ERROR = "error"


# ---------------------------------------------------------------------------
# Payload models
# ---------------------------------------------------------------------------


class StepStartPayload(BaseModel):
    step_name: str = Field(description="Internal node identifier (sanitised)")
    title: str = Field(description="Short user-facing label for this step")
    description: Optional[str] = Field(default=None, description="Optional detail sentence")


class StepCompletePayload(BaseModel):
    step_name: str
    title: str
    status: Literal["done", "error"] = "done"


class ToolCallPayload(BaseModel):
    tool_name: str = Field(description="Public tool name")
    display_name: str = Field(description="User-friendly tool label")
    step_name: str = Field(description="Parent step this tool belongs to")
    input_summary: Optional[str] = Field(
        default=None,
        description="One-line summary of what the tool was asked to do (no raw prompt)",
    )


class ToolResultPayload(BaseModel):
    tool_name: str
    step_name: str
    output_summary: Optional[str] = Field(
        default=None,
        description="Brief, sanitised summary of what the tool returned",
    )
    status: Literal["success", "error"] = "success"


class MessageChunkPayload(BaseModel):
    chunk: str = Field(description="Incremental text token from the final answer")


class A2UIMessagePayload(BaseModel):
    message: dict[str, Any] = Field(description="A2UI v0.9 server-to-client message")


class MessageCompletePayload(BaseModel):
    content: str = Field(description="Full assembled final answer")


class ErrorPayload(BaseModel):
    message: str = Field(description="User-facing error description")
    code: Optional[str] = Field(default=None)


class HITLFormPayload(BaseModel):
    """Payload when the graph pauses for human input (LangGraph interrupt)."""

    thread_id: str = Field(description="Chat session / LangGraph thread id")
    surface_id: str = Field(description="Surface id to render in the side panel")
    task: Optional[str] = Field(default=None, description="Optional user-facing task summary")


# ---------------------------------------------------------------------------
# Typed event envelopes  (discriminated union on `event`)
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id() -> str:
    return str(uuid4())


class StepStartEvent(BaseModel):
    event: Literal[A2UIEventType.STEP_START] = A2UIEventType.STEP_START
    id: str = Field(default_factory=_new_id)
    timestamp: str = Field(default_factory=_now_iso)
    payload: StepStartPayload


class StepCompleteEvent(BaseModel):
    event: Literal[A2UIEventType.STEP_COMPLETE] = A2UIEventType.STEP_COMPLETE
    id: str = Field(default_factory=_new_id)
    timestamp: str = Field(default_factory=_now_iso)
    payload: StepCompletePayload


class ToolCallEvent(BaseModel):
    event: Literal[A2UIEventType.TOOL_CALL] = A2UIEventType.TOOL_CALL
    id: str = Field(default_factory=_new_id)
    timestamp: str = Field(default_factory=_now_iso)
    payload: ToolCallPayload


class ToolResultEvent(BaseModel):
    event: Literal[A2UIEventType.TOOL_RESULT] = A2UIEventType.TOOL_RESULT
    id: str = Field(default_factory=_new_id)
    timestamp: str = Field(default_factory=_now_iso)
    payload: ToolResultPayload


class MessageChunkEvent(BaseModel):
    event: Literal[A2UIEventType.MESSAGE_CHUNK] = A2UIEventType.MESSAGE_CHUNK
    id: str = Field(default_factory=_new_id)
    timestamp: str = Field(default_factory=_now_iso)
    payload: MessageChunkPayload


class A2UIMessageEvent(BaseModel):
    event: Literal[A2UIEventType.A2UI_MESSAGE] = A2UIEventType.A2UI_MESSAGE
    id: str = Field(default_factory=_new_id)
    timestamp: str = Field(default_factory=_now_iso)
    payload: A2UIMessagePayload


class MessageCompleteEvent(BaseModel):
    event: Literal[A2UIEventType.MESSAGE_COMPLETE] = A2UIEventType.MESSAGE_COMPLETE
    id: str = Field(default_factory=_new_id)
    timestamp: str = Field(default_factory=_now_iso)
    payload: MessageCompletePayload


class ErrorEvent(BaseModel):
    event: Literal[A2UIEventType.ERROR] = A2UIEventType.ERROR
    id: str = Field(default_factory=_new_id)
    timestamp: str = Field(default_factory=_now_iso)
    payload: ErrorPayload


class HITLFormEvent(BaseModel):
    event: Literal[A2UIEventType.HITL_FORM] = A2UIEventType.HITL_FORM
    id: str = Field(default_factory=_new_id)
    timestamp: str = Field(default_factory=_now_iso)
    payload: HITLFormPayload


# Discriminated union used as the single public type
A2UIEvent = Annotated[
    Union[
        StepStartEvent,
        StepCompleteEvent,
        ToolCallEvent,
        ToolResultEvent,
        A2UIMessageEvent,
        MessageChunkEvent,
        MessageCompleteEvent,
        HITLFormEvent,
        ErrorEvent,
    ],
    Field(discriminator="event"),
]


# ---------------------------------------------------------------------------
# Factory helpers — the only public constructors callers should use
# ---------------------------------------------------------------------------


def make_step_start(step_name: str, title: str, description: str | None = None) -> StepStartEvent:
    return StepStartEvent(
        payload=StepStartPayload(step_name=step_name, title=title, description=description)
    )


def make_step_complete(
    step_name: str, title: str, status: Literal["done", "error"] = "done"
) -> StepCompleteEvent:
    return StepCompleteEvent(
        payload=StepCompletePayload(step_name=step_name, title=title, status=status)
    )


def make_tool_call(
    tool_name: str,
    display_name: str,
    step_name: str,
    input_summary: str | None = None,
) -> ToolCallEvent:
    return ToolCallEvent(
        payload=ToolCallPayload(
            tool_name=tool_name,
            display_name=display_name,
            step_name=step_name,
            input_summary=input_summary,
        )
    )


def make_tool_result(
    tool_name: str,
    step_name: str,
    output_summary: str | None = None,
    status: Literal["success", "error"] = "success",
) -> ToolResultEvent:
    return ToolResultEvent(
        payload=ToolResultPayload(
            tool_name=tool_name,
            step_name=step_name,
            output_summary=output_summary,
            status=status,
        )
    )


def make_message_chunk(chunk: str) -> MessageChunkEvent:
    return MessageChunkEvent(payload=MessageChunkPayload(chunk=chunk))


def make_a2ui_message(message: dict[str, Any]) -> A2UIMessageEvent:
    return A2UIMessageEvent(payload=A2UIMessagePayload(message=message))


def make_message_complete(content: str) -> MessageCompleteEvent:
    return MessageCompleteEvent(payload=MessageCompletePayload(content=content))


def make_error(message: str, code: str | None = None) -> ErrorEvent:
    return ErrorEvent(payload=ErrorPayload(message=message, code=code))


def make_hitl_form(*, thread_id: str, surface_id: str, task: str | None = None) -> HITLFormEvent:
    return HITLFormEvent(
        payload=HITLFormPayload(thread_id=thread_id, surface_id=surface_id, task=task)
    )
