"""Equity Holding model for SQLAlchemy"""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, Text, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class EquityHolding(Base):
    """Equity holding model for equity_holdings_in table"""

    __tablename__ = "zerodha_equity_holdings_in"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("f_users.user_id", ondelete="CASCADE"), nullable=False
    )
    broker_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("brokers.broker_id", ondelete="CASCADE"), nullable=False
    )
    symbol: Mapped[str] = mapped_column(Text, nullable=False)
    isin: Mapped[str] = mapped_column(Text, nullable=False)
    sector: Mapped[str] = mapped_column(Text, nullable=True)

    # Quantities (integer values)
    qty_available: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    qty_long_term: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    qty_pledged_margin: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Prices (decimal with precision)
    avg_price: Mapped[Decimal] = mapped_column(Numeric(precision=20, scale=4), nullable=False)
    prev_close_price: Mapped[Decimal] = mapped_column(
        Numeric(precision=20, scale=4), nullable=False
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return (
            f"<EquityHolding(id={self.id}, user_id={self.user_id}, "
            f"symbol={self.symbol}, qty={self.qty_available})>"
        )
