"""Daily Stock Game models — contest picks & leaderboard."""

from datetime import date, datetime
from uuid import UUID

from sqlalchemy import (
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base


class DailyContest(Base):
    """One row per calendar trading day. Created lazily on first pick submission."""

    __tablename__ = "f_daily_contests"

    contest_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    contest_date: Mapped[date] = mapped_column(Date, unique=True, nullable=False, index=True)
    nifty_open: Mapped[float | None] = mapped_column(Float, nullable=True)
    nifty_close: Mapped[float | None] = mapped_column(Float, nullable=True)
    nifty_return_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_settled: Mapped[bool] = mapped_column(
        default=False, server_default=text("false"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    picks: Mapped[list["ContestPick"]] = relationship(
        "ContestPick", back_populates="contest", lazy="selectin"
    )


class ContestPick(Base):
    """A user's portfolio of 5 stocks for a given contest day."""

    __tablename__ = "f_contest_picks"
    __table_args__ = (
        UniqueConstraint("contest_id", "user_id", name="uq_contest_user"),
    )

    pick_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    contest_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("f_daily_contests.contest_id"), nullable=False, index=True
    )
    user_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("f_users.user_id"), nullable=True, index=True
    )
    # Anonymous identity — client-generated UUID stored in localStorage
    anon_id: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    # Display name shown on leaderboard (username for auth users, random name for anon)
    display_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Submission IP — used as secondary dedup for anonymous picks
    ip_address: Mapped[str | None] = mapped_column(Text, nullable=True)

    # 5 stock symbols (equal-weight 20% each)
    stock_1: Mapped[str] = mapped_column(Text, nullable=False)
    stock_2: Mapped[str] = mapped_column(Text, nullable=False)
    stock_3: Mapped[str] = mapped_column(Text, nullable=False)
    stock_4: Mapped[str] = mapped_column(Text, nullable=False)
    stock_5: Mapped[str] = mapped_column(Text, nullable=False)

    # Snapshot prices captured at submission time (used as entry price for scoring)
    stock_1_entry_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    stock_2_entry_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    stock_3_entry_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    stock_4_entry_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    stock_5_entry_price: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Scores (populated after market close)
    portfolio_return_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    excess_return_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    rank: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Per-stock returns (for breakdown display)
    stock_1_return_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    stock_2_return_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    stock_3_return_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    stock_4_return_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    stock_5_return_pct: Mapped[float | None] = mapped_column(Float, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    contest: Mapped["DailyContest"] = relationship("DailyContest", back_populates="picks")
