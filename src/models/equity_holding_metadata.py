"""Equity Holding Metadata model for SQLAlchemy"""

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import DateTime
from sqlalchemy import Enum as SQLAEnum
from sqlalchemy import ForeignKey, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base

if TYPE_CHECKING:
    from src.models.equity_holding import EquityHolding


class UploadedVia(str, Enum):
    """Enum for how holdings were uploaded"""

    USER_FILE_UPLOAD = "user_file_upload"
    CRON_JOB = "cron_job"


class EquityHoldingMetadata(Base):
    """Equity holding metadata model for equity_holdings_in_metadata table"""

    __tablename__ = "equity_holdings_in_metadata"

    user_broker_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("f_users.user_id", ondelete="CASCADE"),
        nullable=False,
    )
    broker_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("brokers.broker_id", ondelete="CASCADE"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    uploaded_via: Mapped[UploadedVia] = mapped_column(
        SQLAEnum(
            UploadedVia,
            name="uploaded_via_enum",
            create_constraint=True,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )
    extra_metadata: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB, nullable=True, default=None
    )

    # Relationship to holdings
    holdings: Mapped[list["EquityHolding"]] = relationship(
        "EquityHolding", back_populates="holding_metadata", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return (
            f"<EquityHoldingMetadata(user_broker_id={self.user_broker_id}, "
            f"user_id={self.user_id}, broker_id={self.broker_id})>"
        )
