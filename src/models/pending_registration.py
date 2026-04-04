"""Pending registration model for OTP verification during user registration."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Integer, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from src.models.base import Base


class PendingRegistration(Base):
    """Model for storing pending user registrations awaiting OTP verification."""

    __tablename__ = "pending_registrations"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    email: Mapped[str] = mapped_column(Text, unique=True, nullable=False, index=True)
    username: Mapped[str] = mapped_column(Text, nullable=False)
    full_name: Mapped[str] = mapped_column(Text, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    otp_hash: Mapped[str] = mapped_column(Text, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    attempts: Mapped[int] = mapped_column(Integer, server_default="0", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.current_timestamp()
    )

    def __repr__(self) -> str:
        return f"<PendingRegistration(id={self.id}, email={self.email}, username={self.username})>"
