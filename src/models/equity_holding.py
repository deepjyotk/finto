"""Equity Holding model for SQLAlchemy"""

from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, Integer, Numeric, Text, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base

if TYPE_CHECKING:
    from src.models.equity_holding_metadata import EquityHoldingMetadata


class EquityHolding(Base):
    """Equity holding model for equity_holdings_in table"""

    __tablename__ = "equity_holdings_in"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    user_broker_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("equity_holdings_in_metadata.user_broker_id", ondelete="CASCADE"),
        nullable=False,
    )
    symbol: Mapped[str] = mapped_column(Text, nullable=False)
    company_name: Mapped[str] = mapped_column(Text, nullable=False)
    sector: Mapped[str] = mapped_column(Text, nullable=True)

    # Quantities (integer values)
    qty_available: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    qty_long_term: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    qty_pledged_margin: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Prices (decimal with precision)
    avg_price: Mapped[Decimal] = mapped_column(
        Numeric(precision=20, scale=4), nullable=False
    )
    prev_close_price: Mapped[Decimal] = mapped_column(
        Numeric(precision=20, scale=4), nullable=False
    )

    # Relationship to metadata
    holding_metadata: Mapped["EquityHoldingMetadata"] = relationship(
        "EquityHoldingMetadata", back_populates="holdings"
    )

    def __repr__(self) -> str:
        return (
            f"<EquityHolding(id={self.id}, user_broker_id={self.user_broker_id}, "
            f"symbol={self.symbol}, qty={self.qty_available})>"
        )
