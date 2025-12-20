"""Schemas for the Thesys C1 streaming chat endpoint."""

from uuid import UUID

from pydantic import BaseModel

from src.core.enums import ChatMessageType


class C1Message(BaseModel):
    content: str


class C1ChatRequest(BaseModel):
    message_payload: C1Message
    session_id: str
    broker_id: str


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


class ChatMetadataResponse(BaseModel):
    brokers: list[UserBrokerItem]
