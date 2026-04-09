"""Schemas for the Thesys C1 streaming chat endpoint."""

from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from src.core.enums import ChatMessageType, LLMModel


class C1Message(BaseModel):
    content: str


class C1ChatRequest(BaseModel):
    message_payload: C1Message
    session_id: str
    broker_id: Optional[str] = Field(
        default=None,
        description=(
            "When omitted or empty, portfolio tools aggregate all brokers "
            "(same as HoldingsService.get_portfolio_df with broker_id=None)."
        ),
    )
    model_payload: LLMModel

    @field_validator("broker_id", mode="before")
    @classmethod
    def empty_broker_to_none(cls, v: Any) -> str | None:
        if v is None:
            return None
        if isinstance(v, str):
            s = v.strip()
            return s if s else None
        return str(v).strip() or None

    @field_validator("model_payload", mode="before")
    @classmethod
    def coerce_model_payload(cls, v: Any) -> LLMModel:
        """Accept enum, OpenAI model id string, or "auto" (server default)."""
        if isinstance(v, LLMModel):
            return v
        if isinstance(v, str):
            s = v.strip()
            if not s or s.lower() == "auto":
                return LLMModel.Auto
            return LLMModel.from_model_name(s)
        if isinstance(v, dict) and "model" in v:
            return LLMModel.from_model_name(str(v["model"]))
        raise ValueError(f"Invalid model_payload: {v!r}")


class ChatSessionSchema(BaseModel):
    """Schema for ChatSession model."""

    session_id: str
    started_at: str


class SessionResponse(BaseModel):
    session_id: str
    started_at: str


class SessionItem(BaseModel):
    session_id: str
    started_at: str


class SessionsListResponse(BaseModel):
    sessions: list[SessionItem]
    page: int
    page_limit: int
    total_sessions: int
    total_pages: int
    has_next_page: bool


class MessageItem(BaseModel):
    id: str
    seq_no: int
    message_payload: str
    message_type: ChatMessageType


class SessionMessageConfig(BaseModel):
    session_id: str
    messages: list[MessageItem]


class UserBrokerItem(BaseModel):
    broker_id: UUID
    broker_name: str


class ChatModeItem(BaseModel):
    id: str
    label: str
    description: str


class LLMModelItem(BaseModel):
    id: str
    label: str


class ChatMetadataResponse(BaseModel):
    brokers: list[UserBrokerItem]
    chat_modes: list[ChatModeItem]
    llm_models: list[LLMModelItem]
