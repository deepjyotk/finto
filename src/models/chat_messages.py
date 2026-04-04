"""Chat messages model for SQLAlchemy"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import BigInteger, DateTime
from sqlalchemy import Enum as SQLEnum
from sqlalchemy import ForeignKey, Index, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.core.enums import ChatMessageType
from src.models.base import Base


class ChatMessage(Base):
    """Chat message model for chat_messages table."""

    __tablename__ = "chat_messages"
    __table_args__ = (
        UniqueConstraint("session_id", "seq_no", name="uq_chat_messages_session_seq"),
        Index(
            "idx_chat_messages_session_seq",
            "session_id",
            "seq_no",
        ),
        Index(
            "idx_chat_messages_session_created_at",
            "session_id",
            "created_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    session_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("chat_sessions.chat_session_id", ondelete="CASCADE"),
        nullable=False,
    )
    seq_no: Mapped[int] = mapped_column(BigInteger, nullable=False)
    user_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("f_users.user_id", ondelete="CASCADE"),
        nullable=True,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    message_type: Mapped[ChatMessageType] = mapped_column(
        SQLEnum(
            ChatMessageType,
            name="chat_message_type",
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
            validate_strings=True,
        ),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    edited_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    def __repr__(self) -> str:
        return (
            f"<ChatMessage(id={self.id}, session_id={self.session_id}, "
            f"seq_no={self.seq_no}, message_type={self.message_type})>"
        )
