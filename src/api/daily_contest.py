"""API endpoints for the Daily Stock Game."""

from __future__ import annotations

from datetime import date
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from src.api.schemas.daily_contest import (
    AnonPickConfirmation,
    AnonSubmitPicksRequest,
    ContestStatusResponse,
    LeaderboardResponse,
    LivePerformanceResponse,
    MyResultResponse,
    PickConfirmation,
    StockSearchResponse,
    SubmitPicksRequest,
)
from src.core.json_logging import logger_for
from src.core.middleware import require_auth
from src.dependencies import get_daily_contest_service
from src.services.daily_contest import DailyContestService
from src.services.stock_search import search_stocks, search_stocks_semantic

logger = logger_for(__name__)

router = APIRouter(prefix="/game", tags=["daily-stock-game"])


@router.get("/stocks/search", response_model=StockSearchResponse)
async def search_stocks_endpoint(
    q: str = Query(..., min_length=1, max_length=50, description="Symbol or company name to search"),
    semantic: bool = Query(False, description="Use Pinecone semantic search (slower, for descriptions)"),
    limit: int = Query(10, ge=1, le=30),
):
    """Autocomplete endpoint for the stock picker.

    Fast in-memory search by default (prefix/substring on symbol + company name).
    Set ?semantic=true for natural language queries like 'solar energy company'.
    No auth required.
    """
    if semantic:
        results = await search_stocks_semantic(q, limit=limit)
    else:
        results = search_stocks(q, limit=limit)
    return StockSearchResponse(query=q, results=results, semantic=semantic)


@router.post("/picks", response_model=PickConfirmation, status_code=status.HTTP_201_CREATED)
async def submit_picks(
    request: Request,
    body: SubmitPicksRequest,
    svc: Annotated[DailyContestService, Depends(get_daily_contest_service)],
    user: dict = Depends(require_auth),
):
    """Submit 5 stock picks for today's contest (authenticated)."""
    from uuid import UUID

    user_id = UUID(user["user_id"])
    ip = request.client.host if request.client else None
    try:
        pick, contest_date = await svc.submit_picks(user_id, body.stocks, ip_address=ip)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    return PickConfirmation(
        pick_id=pick.pick_id,
        contest_date=contest_date,
        stocks=[pick.stock_1, pick.stock_2, pick.stock_3, pick.stock_4, pick.stock_5],
    )


@router.post("/anon/picks", response_model=AnonPickConfirmation, status_code=status.HTTP_201_CREATED)
async def submit_anon_picks(
    request: Request,
    body: AnonSubmitPicksRequest,
    svc: Annotated[DailyContestService, Depends(get_daily_contest_service)],
):
    """Submit 5 stock picks anonymously — no login required.

    The client must generate a UUID (stored in localStorage) as `anon_id`.
    Limited to one submission per device (anon_id) and one per IP address per day.
    """
    ip = request.client.host if request.client else None
    try:
        pick, contest_date = await svc.submit_anon_picks(
            anon_id=body.anon_id,
            display_name=body.display_name,
            stocks=body.stocks,
            ip_address=ip,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    return AnonPickConfirmation(
        pick_id=pick.pick_id,
        contest_date=contest_date,
        anon_id=pick.anon_id or body.anon_id,
        display_name=pick.display_name or body.display_name,
        stocks=[pick.stock_1, pick.stock_2, pick.stock_3, pick.stock_4, pick.stock_5],
    )


@router.get("/anon/status", response_model=ContestStatusResponse)
async def anon_contest_status(
    anon_id: str,
    svc: Annotated[DailyContestService, Depends(get_daily_contest_service)],
    contest_date: Optional[date] = Query(None),
):
    """Check if an anonymous user has already submitted picks."""
    today = svc._today_ist()
    active_date = contest_date or await svc._get_active_contest_date()
    today_contest = await svc._repo.get_contest_by_date(today)
    today_settled = today_contest is not None and today_contest.is_settled

    target_contest = await svc._repo.get_contest_by_date(active_date)
    has_submitted = False
    count = 0
    if target_contest:
        pick = await svc._repo.get_anon_pick(target_contest.contest_id, anon_id)
        has_submitted = pick is not None
        count = await svc._repo.count_participants(target_contest.contest_id)

    phase = "settled" if today_settled else ("submitted" if has_submitted else "open")
    return ContestStatusResponse(
        contest_date=today,
        active_contest_date=active_date,
        has_submitted=has_submitted,
        is_settled=today_settled,
        phase=phase,
        total_participants=count,
    )


@router.get("/anon/live-performance", response_model=LivePerformanceResponse)
async def anon_live_performance(
    anon_id: str,
    svc: Annotated[DailyContestService, Depends(get_daily_contest_service)],
    contest_date: Optional[date] = Query(None),
):
    """Real-time portfolio performance for an anonymous user. Polled every 5s."""
    result = await svc.get_live_performance_anon(anon_id, contest_date)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No picks found.")
    return LivePerformanceResponse(**result)


@router.get("/status", response_model=ContestStatusResponse)
async def contest_status(
    svc: Annotated[DailyContestService, Depends(get_daily_contest_service)],
    user: dict = Depends(require_auth),
    contest_date: Optional[date] = Query(None, description="Defaults to today IST"),
):
    """Check if user has already submitted picks and if the contest is settled."""
    from uuid import UUID

    user_id = UUID(user["user_id"])
    result = await svc.get_contest_status(user_id, contest_date)
    return ContestStatusResponse(**result)


@router.get("/my-result", response_model=MyResultResponse)
async def my_result(
    svc: Annotated[DailyContestService, Depends(get_daily_contest_service)],
    user: dict = Depends(require_auth),
    contest_date: Optional[date] = Query(None, description="Defaults to today IST"),
):
    """Get user's own result and rank for a contest day."""
    from uuid import UUID

    user_id = UUID(user["user_id"])
    result = await svc.get_my_result(user_id, contest_date)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No picks found for this contest day.",
        )
    return MyResultResponse(**result)


@router.get("/live-performance", response_model=LivePerformanceResponse)
async def live_performance(
    svc: Annotated[DailyContestService, Depends(get_daily_contest_service)],
    user: dict = Depends(require_auth),
    contest_date: Optional[date] = Query(None, description="Defaults to today IST"),
):
    """Real-time portfolio performance for the authenticated user.

    Fetches current market prices and computes live P&L vs entry prices.
    Designed to be polled every 5 seconds by the UI.
    """
    from uuid import UUID

    user_id = UUID(user["user_id"])
    result = await svc.get_live_performance(user_id, contest_date)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No picks found for this contest day.",
        )
    return LivePerformanceResponse(**result)


@router.get("/leaderboard", response_model=LeaderboardResponse)
async def leaderboard(
    svc: Annotated[DailyContestService, Depends(get_daily_contest_service)],
    contest_date: Optional[date] = Query(None, description="Defaults to today IST"),
):
    """Get the full leaderboard for a contest day. No auth required."""
    result = await svc.get_leaderboard(contest_date)
    return LeaderboardResponse(**result)


@router.post("/settle", status_code=status.HTTP_200_OK)
async def settle_contest(
    svc: Annotated[DailyContestService, Depends(get_daily_contest_service)],
    user: dict = Depends(require_auth),
    contest_date: Optional[date] = Query(None, description="Defaults to today IST"),
):
    """Settle the contest — calculate scores and rank. Call after 3:30 PM IST.

    In production, trigger this via a scheduled job (Cloud Scheduler / cron).
    """
    try:
        result = await svc.settle_contest(contest_date)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return result
