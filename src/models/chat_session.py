"""Chat session model for SQLAlchemy"""

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


class ChatSessionClosedReason(str, Enum):
    """Enum for chat session closure reasons."""

    TIMEOUT = "timeout"
    USER_NEW_CHAT = "user_new_chat"


class ChatSession(Base):
    """Chat session model for chat_sessions table."""

    __tablename__ = "chat_sessions"
    __table_args__ = (
        Index(
            "idx_chat_sessions_active_expiry",
            "expires_at",
            postgresql_where=text("is_active = TRUE"),
        ),
        Index(
            "idx_chat_sessions_user_active_expiry",
            "user_id",
            postgresql_where=text("is_active = TRUE"),
        ),
        Index(
            "uq_chat_sessions_user_active",
            "user_id",
            unique=True,
            postgresql_where=text("is_active = TRUE"),
        ),
    )

    session_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("f_users.user_id", ondelete="CASCADE"), nullable=False
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_activity_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("TRUE"), index=True
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_reason: Mapped[ChatSessionClosedReason | None] = mapped_column(
        SQLEnum(ChatSessionClosedReason, name="chat_session_closed_reason"), nullable=True
    )
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )

    def __repr__(self) -> str:
        return (
            f"<ChatSession(session_id={self.session_id}, user_id={self.user_id}, "
            f"is_active={self.is_active})>"
        )
