"""Repository layer for Daily Stock Game — all DB queries."""

from __future__ import annotations

from datetime import date
from typing import Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.daily_contest import ContestPick, DailyContest


class DailyContestRepo:
    """Database operations for the daily stock-picking game."""

    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    # ── Contest ─────────────────────────────────────────────────────────

    async def get_or_create_contest(self, contest_date: date) -> DailyContest:
        """Return the contest for *contest_date*, creating one if it doesn't exist."""
        stmt = select(DailyContest).where(DailyContest.contest_date == contest_date)
        result = await self._s.execute(stmt)
        contest = result.scalar_one_or_none()
        if contest is None:
            contest = DailyContest(contest_date=contest_date)
            self._s.add(contest)
            await self._s.flush()
        return contest

    async def get_contest_by_date(self, contest_date: date) -> Optional[DailyContest]:
        stmt = select(DailyContest).where(DailyContest.contest_date == contest_date)
        result = await self._s.execute(stmt)
        return result.scalar_one_or_none()

    async def update_contest_nifty(
        self,
        contest_id: UUID,
        nifty_open: float,
        nifty_close: float,
        nifty_return_pct: float,
    ) -> None:
        stmt = select(DailyContest).where(DailyContest.contest_id == contest_id)
        result = await self._s.execute(stmt)
        contest = result.scalar_one()
        contest.nifty_open = nifty_open
        contest.nifty_close = nifty_close
        contest.nifty_return_pct = nifty_return_pct
        contest.is_settled = True
        await self._s.flush()

    # ── Picks ───────────────────────────────────────────────────────────

    async def get_user_pick(self, contest_id: UUID, user_id: UUID) -> Optional[ContestPick]:
        stmt = select(ContestPick).where(
            ContestPick.contest_id == contest_id,
            ContestPick.user_id == user_id,
        )
        result = await self._s.execute(stmt)
        return result.scalar_one_or_none()

    async def get_anon_pick(self, contest_id: UUID, anon_id: str) -> Optional[ContestPick]:
        stmt = select(ContestPick).where(
            ContestPick.contest_id == contest_id,
            ContestPick.anon_id == anon_id,
        )
        result = await self._s.execute(stmt)
        return result.scalar_one_or_none()

    async def count_picks_by_ip(self, contest_id: UUID, ip_address: str) -> int:
        """Count how many submissions have been made from an IP address for a contest day."""
        stmt = (
            select(func.count())
            .select_from(ContestPick)
            .where(
                ContestPick.contest_id == contest_id,
                ContestPick.ip_address == ip_address,
            )
        )
        result = await self._s.execute(stmt)
        return result.scalar_one()

    async def create_pick(
        self,
        contest_id: UUID,
        stocks: list[str],
        snapshot_prices: list[float] | None = None,
        user_id: UUID | None = None,
        anon_id: str | None = None,
        display_name: str | None = None,
        ip_address: str | None = None,
    ) -> ContestPick:
        sp = snapshot_prices or [0.0] * 5
        pick = ContestPick(
            contest_id=contest_id,
            user_id=user_id,
            anon_id=anon_id,
            display_name=display_name,
            ip_address=ip_address,
            stock_1=stocks[0],
            stock_2=stocks[1],
            stock_3=stocks[2],
            stock_4=stocks[3],
            stock_5=stocks[4],
            stock_1_entry_price=sp[0],
            stock_2_entry_price=sp[1],
            stock_3_entry_price=sp[2],
            stock_4_entry_price=sp[3],
            stock_5_entry_price=sp[4],
        )
        self._s.add(pick)
        await self._s.flush()
        return pick

    async def get_all_picks_for_contest(self, contest_id: UUID) -> list[ContestPick]:
        stmt = (
            select(ContestPick)
            .where(ContestPick.contest_id == contest_id)
            .order_by(ContestPick.created_at)
        )
        result = await self._s.execute(stmt)
        return list(result.scalars().all())

    async def count_participants(self, contest_id: UUID) -> int:
        stmt = (
            select(func.count())
            .select_from(ContestPick)
            .where(ContestPick.contest_id == contest_id)
        )
        result = await self._s.execute(stmt)
        return result.scalar_one()

    async def get_user_picks_history(
        self, user_id: UUID, limit: int = 30
    ) -> list[tuple["ContestPick", "DailyContest"]]:
        """Return all picks for a user, newest first, joined with their contest."""
        stmt = (
            select(ContestPick, DailyContest)
            .join(DailyContest, ContestPick.contest_id == DailyContest.contest_id)
            .where(ContestPick.user_id == user_id)
            .order_by(DailyContest.contest_date.desc())
            .limit(limit)
        )
        result = await self._s.execute(stmt)
        return [(row.ContestPick, row.DailyContest) for row in result]

    async def update_pick_scores(
        self,
        pick_id: UUID,
        portfolio_return_pct: float,
        excess_return_pct: float,
        rank: int,
        per_stock_returns: list[float],
    ) -> None:
        stmt = select(ContestPick).where(ContestPick.pick_id == pick_id)
        result = await self._s.execute(stmt)
        pick = result.scalar_one()
        pick.portfolio_return_pct = portfolio_return_pct
        pick.excess_return_pct = excess_return_pct
        pick.rank = rank
        pick.stock_1_return_pct = per_stock_returns[0]
        pick.stock_2_return_pct = per_stock_returns[1]
        pick.stock_3_return_pct = per_stock_returns[2]
        pick.stock_4_return_pct = per_stock_returns[3]
        pick.stock_5_return_pct = per_stock_returns[4]
        await self._s.flush()
