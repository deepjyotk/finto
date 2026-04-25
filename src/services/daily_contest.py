"""Service layer for the Daily Stock Game — scoring, settlement, leaderboard."""

from __future__ import annotations

import asyncio
from datetime import date, datetime
from typing import Optional
from uuid import UUID
from zoneinfo import ZoneInfo

import yfinance as yf
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.json_logging import logger_for
from src.models.daily_contest import ContestPick
from src.repositories.daily_contest_repo import DailyContestRepo
from src.tools.common_utils import normalize_symbol

logger = logger_for(__name__)

IST = ZoneInfo("Asia/Kolkata")

# Nifty 50 index ticker on Yahoo Finance
NIFTY_TICKER = "^NSEI"

# Cutoff: no picks after 9:30 AM IST (market open)
MARKET_OPEN_HOUR = 9
MARKET_OPEN_MINUTE = 30

# NSE market close: 3:30 PM IST
MARKET_CLOSE_HOUR = 15
MARKET_CLOSE_MINUTE = 30


class DailyContestService:
    """Orchestrates the daily stock-picking game."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = DailyContestRepo(session)

    # ── helpers ──────────────────────────────────────────────────────────

    @staticmethod
    def _today_ist() -> date:
        return datetime.now(IST).date()

    @staticmethod
    def _tomorrow_ist() -> date:
        from datetime import timedelta

        return datetime.now(IST).date() + timedelta(days=1)

    async def _get_active_contest_date(self) -> date:
        """Return the date users should submit picks for.

        Logic:
        - If today's contest exists AND is already settled → return tomorrow
          (market closed, users can now enter the next contest)
        - Otherwise → return today
        """
        today = self._today_ist()
        contest = await self._repo.get_contest_by_date(today)
        if contest is not None and contest.is_settled:
            return self._tomorrow_ist()
        return today

    @staticmethod
    def _is_before_market_open() -> bool:
        now = datetime.now(IST)
        return (now.hour < MARKET_OPEN_HOUR) or (
            now.hour == MARKET_OPEN_HOUR and now.minute < MARKET_OPEN_MINUTE
        )

    @staticmethod
    def _is_after_market_close() -> bool:
        now = datetime.now(IST)
        return (now.hour > MARKET_CLOSE_HOUR) or (
            now.hour == MARKET_CLOSE_HOUR and now.minute >= MARKET_CLOSE_MINUTE
        )

    async def auto_settle_if_needed(self, contest_date: Optional[date] = None) -> bool:
        """Settle today's contest automatically if market has closed and it isn't settled yet.

        Returns True if settlement was triggered, False if not needed.
        Called transparently from status + live-performance endpoints.
        """
        if not self._is_after_market_close():
            return False

        d = contest_date or self._today_ist()
        contest = await self._repo.get_contest_by_date(d)
        if contest is None or contest.is_settled:
            return False

        # Only settle if there are picks
        picks = await self._repo.get_all_picks_for_contest(contest.contest_id)
        if not picks:
            return False

        logger.info("auto_settle_triggered", extra={"date": str(d)})
        try:
            await self.settle_contest(d)
            return True
        except Exception as exc:
            logger.warning("auto_settle_failed", extra={"date": str(d), "error": str(exc)})
            return False

    @staticmethod
    def _pick_stocks(pick: ContestPick) -> list[str]:
        return [pick.stock_1, pick.stock_2, pick.stock_3, pick.stock_4, pick.stock_5]

    @staticmethod
    def _compute_vibe(excess_return: float | None) -> dict:
        """Turn a numeric excess return into a fun battle-tier label for the UI.

        Returns a dict the UI renders directly — no logic needed on the frontend.
        """
        if excess_return is None:
            return {
                "tier": "loading",
                "emoji": "⏳",
                "label": "Fetching prices…",
                "message": "Hang tight, we're getting live quotes.",
                "vs_bar": 0,  # -100 (full Nifty) ↔ +100 (full portfolio)
                "color": "gray",
            }

        # vs_bar: clamp excess_return to [-3%, +3%] and scale to [-100, +100]
        vs_bar = round(max(-100, min(100, excess_return / 3 * 100)), 1)

        if excess_return >= 2.0:
            return {
                "tier": "legendary",
                "emoji": "🚀",
                "label": "Nifty Destroyer",
                "message": "You're absolutely crushing the index today!",
                "vs_bar": vs_bar,
                "color": "emerald",
            }
        elif excess_return >= 1.0:
            return {
                "tier": "fire",
                "emoji": "🔥",
                "label": "On Fire",
                "message": "Outpacing Nifty by a full percent — keep it up!",
                "vs_bar": vs_bar,
                "color": "green",
            }
        elif excess_return >= 0.25:
            return {
                "tier": "winning",
                "emoji": "💪",
                "label": "Beating the Market",
                "message": "Your picks are ahead of the benchmark. Nice work.",
                "vs_bar": vs_bar,
                "color": "green",
            }
        elif excess_return >= -0.25:
            return {
                "tier": "neck_and_neck",
                "emoji": "⚔️",
                "label": "Neck & Neck",
                "message": "Dead heat with Nifty. One good move can tip the scales.",
                "vs_bar": vs_bar,
                "color": "yellow",
            }
        elif excess_return >= -1.0:
            return {
                "tier": "trailing",
                "emoji": "😓",
                "label": "Slightly Behind",
                "message": "Nifty has a small edge. The day isn't over yet.",
                "vs_bar": vs_bar,
                "color": "orange",
            }
        elif excess_return >= -2.0:
            return {
                "tier": "losing",
                "emoji": "💨",
                "label": "Nifty is Winning",
                "message": "The index is pulling ahead. Time to hope for a reversal.",
                "vs_bar": vs_bar,
                "color": "red",
            }
        else:
            return {
                "tier": "crushed",
                "emoji": "😭",
                "label": "Getting Rekt",
                "message": "Nifty is on a rampage. At least you're learning!",
                "vs_bar": vs_bar,
                "color": "red",
            }

    # ── Submit picks ────────────────────────────────────────────────────

    @staticmethod
    def _snapshot_prices(normalized: list[str]) -> list[float]:
        """Validate symbols against known NSE list, then fetch current prices."""
        from src.services.stock_search import validate_symbol

        snapshot: list[float] = []
        for sym in normalized:
            bare = sym.upper().removesuffix(".NS")
            if not validate_symbol(bare):
                raise ValueError(
                    f"'{bare}' is not a valid NSE stock symbol. Please pick from the search list."
                )
            try:
                import yfinance as yf

                ticker = yf.Ticker(sym)
                price = ticker.info.get("regularMarketPrice")
                if price is None:
                    raise ValueError(
                        f"Could not fetch price for {bare}. It may be delisted or suspended."
                    )
                snapshot.append(float(price))
            except ValueError:
                raise
            except Exception:
                raise ValueError(f"Could not verify symbol: {bare}")
        return snapshot

    async def submit_picks(
        self,
        user_id: UUID,
        stocks: list[str],
        display_name: str | None = None,
        ip_address: str | None = None,
    ) -> tuple[ContestPick, date]:
        """Lock in 5 stocks for today's or next contest (authenticated user)."""
        target_date = await self._get_active_contest_date()
        normalized = [normalize_symbol(s) for s in stocks]

        loop = asyncio.get_event_loop()
        snapshot_prices = await loop.run_in_executor(None, self._snapshot_prices, normalized)

        contest = await self._repo.get_or_create_contest(target_date)

        existing = await self._repo.get_user_pick(contest.contest_id, user_id)
        if existing:
            raise ValueError("You have already submitted picks for today's contest.")

        pick = await self._repo.create_pick(
            contest_id=contest.contest_id,
            stocks=normalized,
            snapshot_prices=snapshot_prices,
            user_id=user_id,
            display_name=display_name,
            ip_address=ip_address,
        )
        await self._session.commit()
        await self._session.refresh(pick)

        logger.info(
            "contest_pick_submitted",
            extra={"user_id": str(user_id), "stocks": normalized, "date": str(target_date)},
        )
        return pick, target_date

    async def submit_anon_picks(
        self,
        anon_id: str,
        display_name: str,
        stocks: list[str],
        ip_address: str | None = None,
    ) -> tuple[ContestPick, date]:
        """Lock in picks for an anonymous (unauthenticated) user.

        Limits:
        - One submission per anon_id (client UUID from localStorage) per day.
        - One submission per IP address per day (secondary dedup).
        """
        today = await self._get_active_contest_date()
        normalized = [normalize_symbol(s) for s in stocks]

        loop = asyncio.get_event_loop()
        snapshot_prices = await loop.run_in_executor(None, self._snapshot_prices, normalized)

        contest = await self._repo.get_or_create_contest(today)

        # Primary limit: one per anon_id
        if await self._repo.get_anon_pick(contest.contest_id, anon_id):
            raise ValueError("This device has already submitted picks for today's contest.")

        # Secondary limit: max 5 submissions per IP per day (covers households / shared WiFi)
        _MAX_PICKS_PER_IP = 5
        if (
            ip_address
            and await self._repo.count_picks_by_ip(contest.contest_id, ip_address)
            >= _MAX_PICKS_PER_IP
        ):
            raise ValueError(
                "Too many submissions have been made from your network today (limit: 5)."
            )

        pick = await self._repo.create_pick(
            contest_id=contest.contest_id,
            stocks=normalized,
            snapshot_prices=snapshot_prices,
            anon_id=anon_id,
            display_name=display_name,
            ip_address=ip_address,
        )
        await self._session.commit()
        await self._session.refresh(pick)

        logger.info(
            "anon_pick_submitted",
            extra={
                "anon_id": anon_id,
                "display_name": display_name,
                "stocks": normalized,
                "date": str(today),
            },
        )
        return pick, today

    # ── Contest status ──────────────────────────────────────────────────

    async def get_contest_status(self, user_id: UUID, contest_date: Optional[date] = None):
        """Check submission state and what phase the game is in."""
        # Auto-settle if market has closed
        await self.auto_settle_if_needed()

        today = self._today_ist()
        active_date = contest_date or await self._get_active_contest_date()
        today_contest = await self._repo.get_contest_by_date(today)
        today_settled = today_contest is not None and today_contest.is_settled

        # Resolve the contest to query for has_submitted / participant count
        target_contest = (
            await self._repo.get_contest_by_date(active_date)
            if active_date != today
            else today_contest
        )

        has_submitted = False
        count = 0
        if target_contest:
            pick = await self._repo.get_user_pick(target_contest.contest_id, user_id)
            has_submitted = pick is not None
            count = await self._repo.count_participants(target_contest.contest_id)
        elif today_contest and not today_settled:
            pick = await self._repo.get_user_pick(today_contest.contest_id, user_id)
            has_submitted = pick is not None
            count = await self._repo.count_participants(today_contest.contest_id)

        if today_settled:
            phase = "settled"
        elif has_submitted:
            phase = "submitted"
        else:
            phase = "open"

        from datetime import timedelta

        return {
            "contest_date": today,
            "active_contest_date": active_date,
            "has_submitted": has_submitted,
            "is_settled": today_settled,
            "phase": phase,
            "total_participants": count,
        }

    # ── My result ───────────────────────────────────────────────────────

    async def get_my_result(self, user_id: UUID, contest_date: Optional[date] = None):
        """Get user's own result + rank for a given contest day."""
        d = contest_date or self._today_ist()
        contest = await self._repo.get_contest_by_date(d)
        if contest is None:
            return None

        pick = await self._repo.get_user_pick(contest.contest_id, user_id)
        if pick is None:
            return None

        count = await self._repo.count_participants(contest.contest_id)
        stocks = self._pick_stocks(pick)
        return {
            "contest_date": d,
            "stocks": [
                {"symbol": stocks[i], "return_pct": getattr(pick, f"stock_{i+1}_return_pct")}
                for i in range(5)
            ],
            "portfolio_return_pct": pick.portfolio_return_pct,
            "nifty_return_pct": contest.nifty_return_pct,
            "excess_return_pct": pick.excess_return_pct,
            "rank": pick.rank,
            "total_participants": count,
            "is_settled": contest.is_settled,
        }

    # ── Leaderboard ─────────────────────────────────────────────────────

    async def get_leaderboard(self, contest_date: Optional[date] = None):
        """Return ranked list of all participants for a contest day."""
        d = contest_date or self._today_ist()
        contest = await self._repo.get_contest_by_date(d)
        if contest is None:
            return {
                "contest_date": d,
                "nifty_return_pct": None,
                "is_settled": False,
                "total_participants": 0,
                "leaderboard": [],
            }

        picks = await self._repo.get_all_picks_for_contest(contest.contest_id)
        count = len(picks)

        # Build leaderboard entries (need username — join via user_id)
        from sqlalchemy import select
        from src.models.user import User

        user_ids = [p.user_id for p in picks]
        if user_ids:
            stmt = select(User.user_id, User.username).where(User.user_id.in_(user_ids))
            result = await self._session.execute(stmt)
            user_map = {row.user_id: row.username for row in result}
        else:
            user_map = {}

        entries = []
        for p in picks:
            is_anon = p.user_id is None
            name = p.display_name or (user_map.get(p.user_id) if p.user_id else None) or "Anonymous"
            entries.append(
                {
                    "rank": p.rank or 0,
                    "user_id": p.user_id,
                    "display_name": name,
                    "is_anonymous": is_anon,
                    "stocks": self._pick_stocks(p),
                    "portfolio_return_pct": p.portfolio_return_pct or 0.0,
                    "excess_return_pct": p.excess_return_pct or 0.0,
                }
            )

        # Sort by excess return descending
        entries.sort(key=lambda e: e["excess_return_pct"], reverse=True)

        return {
            "contest_date": d,
            "nifty_return_pct": contest.nifty_return_pct,
            "is_settled": contest.is_settled,
            "total_participants": count,
            "leaderboard": entries,
        }

    # ── Live performance (polled every 5s by UI) ─────────────────────────

    async def _live_performance_from_pick(
        self, pick: "ContestPick", contest: "DailyContest"
    ) -> dict:
        """Shared implementation — works for both auth and anon users."""
        symbols = [pick.stock_1, pick.stock_2, pick.stock_3, pick.stock_4, pick.stock_5]
        entry_prices = [
            pick.stock_1_entry_price,
            pick.stock_2_entry_price,
            pick.stock_3_entry_price,
            pick.stock_4_entry_price,
            pick.stock_5_entry_price,
        ]

        all_symbols = symbols + [NIFTY_TICKER]

        def _fetch_current_prices() -> dict:
            """Sync yfinance calls — run inside thread pool."""
            data: dict[str, dict] = {}
            tickers = yf.Tickers(" ".join(all_symbols))
            for sym in all_symbols:
                try:
                    fi = tickers.tickers[sym].fast_info
                    data[sym] = {
                        "current": fi.last_price,
                        "prev_close": fi.previous_close,
                    }
                except Exception:
                    data[sym] = {"current": None, "prev_close": None}
            return data

        loop = asyncio.get_event_loop()
        prices = await loop.run_in_executor(None, _fetch_current_prices)

        stocks_live = []
        total_return_pct = 0.0
        for i, sym in enumerate(symbols):
            entry = entry_prices[i] or prices[sym].get("prev_close")
            current = prices[sym].get("current")
            if entry and current and entry > 0:
                ret = round((current - entry) / entry * 100, 4)
            else:
                ret = None
            total_return_pct += ret or 0.0
            stocks_live.append(
                {
                    "symbol": sym,
                    "entry_price": entry,
                    "current_price": current,
                    "return_pct": ret,
                }
            )

        portfolio_return = round(total_return_pct / 5, 4)

        nifty_prices = prices.get(NIFTY_TICKER, {})
        nifty_prev = nifty_prices.get("prev_close")
        nifty_current = nifty_prices.get("current")
        if nifty_prev and nifty_current and nifty_prev > 0:
            nifty_return = round((nifty_current - nifty_prev) / nifty_prev * 100, 4)
        else:
            nifty_return = None

        excess_return = (
            round(portfolio_return - nifty_return, 4) if nifty_return is not None else None
        )

        vibe = self._compute_vibe(excess_return)

        return {
            "contest_date": contest.contest_date,
            "is_settled": contest.is_settled,
            "stocks": stocks_live,
            "portfolio_return_pct": portfolio_return,
            "nifty_return_pct": nifty_return,
            "nifty_current_price": nifty_current,
            "excess_return_pct": excess_return,
            "vibe": vibe,
            "refreshed_at": datetime.now(IST).isoformat(),
        }

    async def get_live_performance_anon(
        self, anon_id: str, contest_date: Optional[date] = None
    ) -> Optional[dict]:
        """Same as get_live_performance but looks up pick by anon_id."""
        await self.auto_settle_if_needed()
        d = contest_date or self._today_ist()
        contest = await self._repo.get_contest_by_date(d)
        if contest is None:
            return None
        pick = await self._repo.get_anon_pick(contest.contest_id, anon_id)
        if pick is None:
            return None
        # Re-use the same logic by temporarily binding user_id
        # We pass the pick directly to the shared helper
        return await self._live_performance_from_pick(pick, contest)

    async def get_live_performance(
        self, user_id: UUID, contest_date: Optional[date] = None
    ) -> Optional[dict]:
        """Return real-time portfolio P&L for the user's picks."""
        await self.auto_settle_if_needed()
        d = contest_date or self._today_ist()
        contest = await self._repo.get_contest_by_date(d)
        if contest is None:
            return None
        pick = await self._repo.get_user_pick(contest.contest_id, user_id)
        if pick is None:
            return None
        return await self._live_performance_from_pick(pick, contest)

    # ── Picks history ───────────────────────────────────────────────────

    async def get_picks_history(self, user_id: UUID, limit: int = 30) -> list[dict]:
        """Return all past picks for a user with per-day scores, newest first."""
        rows = await self._repo.get_user_picks_history(user_id, limit=limit)
        history = []
        for pick, contest in rows:
            stocks = self._pick_stocks(pick)
            history.append(
                {
                    "contest_date": contest.contest_date,
                    "is_settled": contest.is_settled,
                    "stocks": [
                        {
                            "symbol": stocks[i],
                            "entry_price": getattr(pick, f"stock_{i+1}_entry_price"),
                            "return_pct": getattr(pick, f"stock_{i+1}_return_pct"),
                        }
                        for i in range(5)
                    ],
                    "portfolio_return_pct": pick.portfolio_return_pct,
                    "nifty_return_pct": contest.nifty_return_pct,
                    "excess_return_pct": pick.excess_return_pct,
                    "rank": pick.rank,
                }
            )
        return history

    async def get_user_profile(self, user_id: UUID, limit: int = 30) -> dict | None:
        """Return public profile data for a user. Returns None if user not found."""
        from src.repositories.user_repo import UserRepository

        user = await UserRepository(self._session).by_id(user_id)
        if user is None:
            return None

        rows = await self._repo.get_user_picks_history_with_counts(user_id, limit=limit)

        total_games = 0
        wins = 0
        history = []
        for pick, contest, total_participants in rows:
            stocks = self._pick_stocks(pick)
            if contest.is_settled:
                total_games += 1
                if pick.excess_return_pct is not None and pick.excess_return_pct > 0:
                    wins += 1
            history.append(
                {
                    "contest_date": contest.contest_date,
                    "is_settled": contest.is_settled,
                    "stocks": stocks,
                    "portfolio_return_pct": pick.portfolio_return_pct,
                    "nifty_return_pct": contest.nifty_return_pct,
                    "excess_return_pct": pick.excess_return_pct,
                    "rank": pick.rank,
                    "total_participants": total_participants,
                }
            )

        return {
            "user_id": str(user.user_id),
            "username": user.username,
            "full_name": user.full_name or None,
            "total_games": total_games,
            "wins": wins,
            "history": history,
        }

    # ── Settlement (called after market close) ──────────────────────────

    async def settle_contest(self, contest_date: Optional[date] = None) -> dict:
        """Calculate all scores for a contest day. Call after 3:30 PM IST.

        1. Fetch Nifty 50 open/close for the day
        2. For each pick, fetch open/close for all 5 stocks
        3. Calculate equal-weight portfolio return
        4. Compute excess return vs Nifty
        5. Rank all participants
        """
        d = contest_date or self._today_ist()
        contest = await self._repo.get_contest_by_date(d)
        if contest is None:
            raise ValueError(f"No contest found for {d}")
        if contest.is_settled:
            raise ValueError(f"Contest for {d} is already settled")

        # Fetch Nifty data
        nifty_data = self._fetch_day_return(NIFTY_TICKER, d)
        if nifty_data is None:
            raise ValueError(f"Could not fetch Nifty data for {d}. Market may be closed.")

        nifty_open, nifty_close, nifty_return = nifty_data

        # Score each participant using their entry (snapshot) prices vs close
        picks = await self._repo.get_all_picks_for_contest(contest.contest_id)
        scored: list[tuple[ContestPick, float, float, list[float]]] = []

        for pick in picks:
            stocks = self._pick_stocks(pick)
            entry_prices = [
                pick.stock_1_entry_price,
                pick.stock_2_entry_price,
                pick.stock_3_entry_price,
                pick.stock_4_entry_price,
                pick.stock_5_entry_price,
            ]
            per_stock_returns = []
            for i, sym in enumerate(stocks):
                close_data = self._fetch_close_price(sym, d)
                ep = entry_prices[i]
                if close_data is not None and ep and ep > 0:
                    ret = ((close_data - ep) / ep) * 100
                    per_stock_returns.append(ret)
                else:
                    per_stock_returns.append(0.0)

            # Equal-weight portfolio return
            portfolio_ret = sum(per_stock_returns) / 5
            excess_ret = portfolio_ret - nifty_return
            scored.append((pick, portfolio_ret, excess_ret, per_stock_returns))

        # Sort by excess return descending for ranking
        scored.sort(key=lambda x: x[2], reverse=True)

        # Persist scores
        for rank_idx, (pick, port_ret, excess_ret, per_stock_rets) in enumerate(scored, 1):
            await self._repo.update_pick_scores(
                pick_id=pick.pick_id,
                portfolio_return_pct=round(port_ret, 4),
                excess_return_pct=round(excess_ret, 4),
                rank=rank_idx,
                per_stock_returns=[round(r, 4) for r in per_stock_rets],
            )

        # Persist Nifty data
        await self._repo.update_contest_nifty(
            contest_id=contest.contest_id,
            nifty_open=nifty_open,
            nifty_close=nifty_close,
            nifty_return_pct=round(nifty_return, 4),
        )

        await self._session.commit()
        logger.info("contest_settled", extra={"date": str(d), "participants": len(scored)})

        return {
            "contest_date": d,
            "nifty_return_pct": round(nifty_return, 4),
            "participants_scored": len(scored),
        }

    @staticmethod
    def _fetch_close_price(symbol: str, d: date) -> Optional[float]:
        """Fetch the closing price for *symbol* on date *d*. Returns None on failure."""
        try:
            from datetime import timedelta

            df = yf.download(
                symbol,
                start=str(d),
                end=str(d + timedelta(days=1)),
                progress=False,
                auto_adjust=False,
            )
            if df is None or df.empty:
                return None
            return float(df.iloc[0]["Close"])
        except Exception as e:
            logger.warning("fetch_close_price_failed", extra={"symbol": symbol, "error": str(e)})
            return None

    @staticmethod
    def _fetch_day_return(symbol: str, d: date) -> Optional[tuple[float, float, float]]:
        """Fetch open & close price for a symbol on date *d*.

        Returns (open, close, return_pct) or None if no data.
        """
        try:
            from datetime import timedelta

            df = yf.download(
                symbol,
                start=str(d),
                end=str(d + timedelta(days=1)),
                progress=False,
                auto_adjust=False,
            )
            if df is None or df.empty:
                return None
            row = df.iloc[0]
            open_price = float(row["Open"])
            close_price = float(row["Close"])
            if open_price <= 0:
                return None
            return_pct = ((close_price - open_price) / open_price) * 100
            return (open_price, close_price, return_pct)
        except Exception as e:
            logger.warning("fetch_day_return_failed", extra={"symbol": symbol, "error": str(e)})
            return None
