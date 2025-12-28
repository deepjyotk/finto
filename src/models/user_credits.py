"""User credits model."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base


class UserCredits(Base):
    """Model for tracking user credit balances."""

    __tablename__ = "user_credits"

    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("f_users.user_id", ondelete="CASCADE"),
        primary_key=True,
    )
    credits_left: Mapped[int] = mapped_column(Integer, nullable=False, server_default="5000")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationship to user
    user: Mapped["User"] = relationship("User", back_populates="credits")

    def __repr__(self) -> str:
        return f"<UserCredits(user_id={self.user_id}, credits_left={self.credits_left})>"
