"""WhatsApp Cache model for SQLAlchemy"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class WhatsAppCache(Base):
    """WhatsApp Cache model for whatsapp_cache table"""

    __tablename__ = "whatsapp_cache"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("f_users.user_id", ondelete="CASCADE"),
        nullable=False,
    )
    temporary_code: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    def __repr__(self) -> str:
        return (
            f"<WhatsAppCache(id={self.id}, user_id={self.user_id}, "
            f"temporary_code={self.temporary_code}, created_at={self.created_at})>"
        )
