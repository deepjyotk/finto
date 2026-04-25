"""Daily OHLCV price bar model (NSE universe via in_equities)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Numeric, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class PriceBar1d(Base):
    """One daily bar per listed equity per trading day."""

    __tablename__ = "price_bars_1d"

    in_equity_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("in_equities.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    trade_date: Mapped[date] = mapped_column(Date(), primary_key=True)
    open: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 6), nullable=True)
    high: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 6), nullable=True)
    low: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 6), nullable=True)
    close: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 6), nullable=True)
    volume: Mapped[Optional[int]] = mapped_column(BigInteger(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
