"""WhatsApp Metadata model for SQLAlchemy"""

from uuid import UUID

from sqlalchemy import ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class WhatsAppMetadata(Base):
    """WhatsApp Metadata model for whatsapp_metadata table"""

    __tablename__ = "whatsapp_metadata"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("f_users.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_e164: Mapped[str] = mapped_column(Text, nullable=False, unique=True, index=True)

    def __repr__(self) -> str:
        return (
            f"<WhatsAppMetadata(id={self.id}, user_id={self.user_id}, "
            f"user_e164={self.user_e164})>"
        )
