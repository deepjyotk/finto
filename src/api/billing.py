"""API routes for credit management."""

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth import get_current_user
from src.billing.credit_manager import CREDITS_PER_DOLLAR, CreditManager
from src.core.db import get_session
from src.models.user import User

router = APIRouter(prefix="/billing", tags=["billing"])


class AddCreditsRequest(BaseModel):
    amount: int = Field(..., gt=0, description="Amount of credits to add (must be positive)")


class CreditBalanceResponse(BaseModel):
    user_id: str
    balance: int
    balance_usd: float


class UsageRecord(BaseModel):
    timestamp: str
    model: str
    input_tokens: int
    output_tokens: int
    usd_cost: float
    credits_deducted: int
    balance_after: int


class UsageSummaryResponse(BaseModel):
    current_balance: int
    current_balance_usd: float
    total_credits_spent: int
    total_usd_spent: float
    request_count: int
    recent_requests: List[UsageRecord]


@router.post("/credits/add", response_model=CreditBalanceResponse)
async def add_credits(
    request: AddCreditsRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """Add credits to the current user's account."""
    manager = CreditManager(current_user.user_id, db)
    new_balance = await manager.add_credits(request.amount)

    return CreditBalanceResponse(
        user_id=str(current_user.user_id),
        balance=new_balance,
        balance_usd=round(new_balance / CREDITS_PER_DOLLAR, 2),
    )


@router.get("/credits/balance", response_model=CreditBalanceResponse)
async def get_balance(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """Get current user's credit balance."""
    manager = CreditManager(current_user.user_id, db)
    balance = await manager.get_balance()

    return CreditBalanceResponse(
        user_id=str(current_user.user_id),
        balance=balance,
        balance_usd=round(balance / CREDITS_PER_DOLLAR, 2),
    )


@router.get("/usage/summary", response_model=UsageSummaryResponse)
async def get_usage_summary(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """Get user's credit usage summary."""
    manager = CreditManager(current_user.user_id, db)
    summary = await manager.get_usage_summary()

    return UsageSummaryResponse(
        current_balance=summary["current_balance"],
        current_balance_usd=round(summary["current_balance"] / CREDITS_PER_DOLLAR, 2),
        total_credits_spent=summary["total_credits_spent"],
        total_usd_spent=summary["total_usd_spent"],
        request_count=summary["request_count"],
        recent_requests=[UsageRecord(**record) for record in summary["recent_requests"]],
    )


@router.get("/transactions")
async def get_transaction_history(
    limit: int = 50,
    offset: int = 0,
    transaction_type: str | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """Get user's credit transaction history with pagination.

    Query Parameters:
    - limit: Maximum number of transactions to return (default 50, max 200)
    - offset: Number of transactions to skip (for pagination)
    - transaction_type: Filter by type ('addition', 'deduction', 'initial', 'refund')
    """
    # Enforce max limit
    if limit > 200:
        limit = 200

    manager = CreditManager(current_user.user_id, db)
    transactions = await manager.get_transaction_history(limit, offset, transaction_type)
    total_count = await manager.get_transaction_count(transaction_type)
    
    return {
        "transactions": transactions,
        "limit": limit,
        "offset": offset,
        "count": len(transactions),
        "total_count": total_count,
    }


@router.post("/admin/credits/add/{user_id}", response_model=CreditBalanceResponse)
async def admin_add_credits(
    user_id: UUID,
    request: AddCreditsRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """Admin endpoint to add credits to any user's account."""
    # TODO: Add admin role check
    # if not current_user.is_admin:
    #     raise HTTPException(403, "Admin access required")

    manager = CreditManager(user_id, db)
    new_balance = await manager.add_credits(request.amount)

    return CreditBalanceResponse(
        user_id=str(user_id),
        balance=new_balance,
        balance_usd=round(new_balance / CREDITS_PER_DOLLAR, 2),
    )
