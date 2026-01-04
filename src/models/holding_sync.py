"""Holding Sync model for SQLAlchemy"""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base

if TYPE_CHECKING:
    from src.models.user import User


class HoldingSync(Base):
    """Holding sync model for holding_syncs table"""

    __tablename__ = "holding_syncs"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("f_users.user_id", ondelete="CASCADE"),
        nullable=False,
    )
    synced_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Relationship to user
    user: Mapped["User"] = relationship("User", back_populates="holding_syncs")

    def __repr__(self) -> str:
        return (
            f"<HoldingSync(id={self.id}, user_id={self.user_id}, "
            f"synced_count={self.synced_count}, updated_count={self.updated_count})>"
        )
