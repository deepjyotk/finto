"""Chat session models for SQLAlchemy"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from sqlalchemy import Boolean, DateTime
from sqlalchemy import Enum as SQLEnum
from sqlalchemy import ForeignKey, Index, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from src.models.base import Base


class WhatsappChatSessionClosedReason(str, Enum):
    """Enum for WhatsApp chat session closure reasons."""

    TIMEOUT = "timeout"
    USER_NEW_CHAT = "user_new_chat"


class WhatsappChatSession(Base):
    """WhatsApp chat session model for whatsapp_chat_sessions table."""

    __tablename__ = "whatsapp_chat_sessions"
    __table_args__ = (
        Index(
            "idx_whatsapp_chat_sessions_active_expiry",
            "whatsapp_expires_at",
            postgresql_where=text("whatsapp_is_active = TRUE"),
        ),
        Index(
            "idx_whatsapp_chat_sessions_user_active_expiry",
            "user_id",
            postgresql_where=text("whatsapp_is_active = TRUE"),
        ),
        Index(
            "uq_whatsapp_chat_sessions_user_active",
            "user_id",
            unique=True,
            postgresql_where=text("whatsapp_is_active = TRUE"),
        ),
    )

    whatsapp_session_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("f_users.user_id", ondelete="CASCADE"),
        nullable=False,
    )
    whatsapp_started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    whatsapp_last_activity_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    whatsapp_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    whatsapp_is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("TRUE"), index=True
    )
    whatsapp_closed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    whatsapp_closed_reason: Mapped[WhatsappChatSessionClosedReason | None] = (
        mapped_column(
            SQLEnum(
                WhatsappChatSessionClosedReason,
                name="whatsapp_chat_session_closed_reason",
            ),
            nullable=True,
        )
    )
    whatsapp_metadata: Mapped[dict[str, Any]] = mapped_column(
        "whatsapp_metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )

    def __repr__(self) -> str:
        return (
            f"<WhatsappChatSession(whatsapp_session_id={self.whatsapp_session_id}, user_id={self.user_id}, "
            f"whatsapp_is_active={self.whatsapp_is_active})>"
        )


class ChatSession(Base):
    """Simple chat session model for chat_sessions table."""

    __tablename__ = "chat_sessions"

    chat_session_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("f_users.user_id", ondelete="CASCADE"),
        nullable=False,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<ChatSession(chat_session_id={self.chat_session_id}, user_id={self.user_id})>"
