"""Credit management system for tracking and deducting LLM usage costs."""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.json_logging import logger_for
from src.models.credit_transaction import CreditTransaction
from src.models.user import User
from src.models.user_credits import UserCredits

logger = logger_for(__name__)


@dataclass
class ModelPricing:
    """Pricing per 1M tokens for a model."""

    input_cost_per_1m: float  # Cost per 1M input tokens in USD
    output_cost_per_1m: float  # Cost per 1M output tokens in USD


# Pricing as of Dec 2024 (update these periodically)
MODEL_PRICING = {
    # OpenAI Models
    "gpt-4o": ModelPricing(input_cost_per_1m=2.50, output_cost_per_1m=10.00),
    "gpt-4o-mini": ModelPricing(input_cost_per_1m=0.150, output_cost_per_1m=0.600),
    "gpt-4-turbo": ModelPricing(input_cost_per_1m=10.00, output_cost_per_1m=30.00),
    "gpt-4.1": ModelPricing(
        input_cost_per_1m=10.00, output_cost_per_1m=30.00
    ),  # GPT-4.1 (similar to turbo)
    "gpt-3.5-turbo": ModelPricing(input_cost_per_1m=0.50, output_cost_per_1m=1.50),
    # Anthropic Models
    "claude-3-5-sonnet-20241022": ModelPricing(input_cost_per_1m=3.00, output_cost_per_1m=15.00),
    "claude-3-5-haiku-20241022": ModelPricing(input_cost_per_1m=0.80, output_cost_per_1m=4.00),
    "claude-3-opus-20240229": ModelPricing(input_cost_per_1m=15.00, output_cost_per_1m=75.00),
    # Google Models
    "gemini-1.5-pro": ModelPricing(input_cost_per_1m=1.25, output_cost_per_1m=5.00),
    "gemini-1.5-flash": ModelPricing(input_cost_per_1m=0.075, output_cost_per_1m=0.30),
    # Thesys/C1 wrapped models (use base model pricing)
    "c1-exp/openai/gpt-4.1": ModelPricing(input_cost_per_1m=10.00, output_cost_per_1m=30.00),
}

# Conversion rate: 1 USD = 1000 credits
CREDITS_PER_DOLLAR = 1000


class CreditManager:
    """Manages user credits and tracks LLM usage costs using database."""

    def __init__(self, user_id: UUID | str, db_session: AsyncSession):
        """Initialize credit manager with database session.

        Args:
            user_id: User UUID
            db_session: SQLAlchemy async session
        """
        self.user_id = UUID(user_id) if isinstance(user_id, str) else user_id
        self._db = db_session
        self._user_credits: UserCredits | None = None
        self._loaded = False

    async def _ensure_loaded(self) -> UserCredits:
        """Load user credits from database if not already loaded. Returns UserCredits (never None)."""
        if self._loaded and self._user_credits is not None:
            return self._user_credits

        stmt = select(UserCredits).where(UserCredits.user_id == self.user_id)
        result = await self._db.execute(stmt)
        self._user_credits = result.scalar_one_or_none()

        if not self._user_credits:
            # Verify user exists
            user_stmt = select(User).where(User.user_id == self.user_id)
            user_result = await self._db.execute(user_stmt)
            user = user_result.scalar_one_or_none()

            if not user:
                raise ValueError(f"User {self.user_id} not found in database")

            # Create credits record with initial 5000 credits
            self._user_credits = UserCredits(user_id=self.user_id, credits_left=5000)
            self._db.add(self._user_credits)

            # Log initial credit allocation
            initial_transaction = CreditTransaction(
                user_id=self.user_id,
                amount=5000,
                transaction_type="initial",
                balance_before=0,
                balance_after=5000,
                description="Initial credit allocation",
            )
            self._db.add(initial_transaction)

            await self._db.commit()
            await self._db.refresh(self._user_credits)
            logger.info(f"Created credits record for user {self.user_id} with 5000 initial credits")

        self._loaded = True
        return self._user_credits

    async def add_credits(self, amount: int, description: str | None = None) -> int:
        """Add credits to user account and log transaction."""
        user_credits = await self._ensure_loaded()

        if amount <= 0:
            raise ValueError("Amount must be positive")

        balance_before = user_credits.credits_left
        user_credits.credits_left += amount
        user_credits.updated_at = datetime.utcnow()

        # Log transaction
        transaction = CreditTransaction(
            user_id=self.user_id,
            amount=amount,
            transaction_type="addition",
            balance_before=balance_before,
            balance_after=user_credits.credits_left,
            description=description,
        )
        self._db.add(transaction)

        await self._db.commit()
        await self._db.refresh(user_credits)

        logger.info(
            f"Added {amount} credits to user {self.user_id}. "
            f"New balance: {user_credits.credits_left}"
        )
        return user_credits.credits_left

    async def get_balance(self) -> int:
        """Get current credit balance."""
        user_credits = await self._ensure_loaded()
        await self._db.refresh(user_credits)
        return user_credits.credits_left

    def calculate_cost(
        self, model_name: str, input_tokens: int, output_tokens: int
    ) -> tuple[float, int]:
        """
        Calculate USD cost and credit cost for token usage.

        Returns:
            tuple[float, int]: (usd_cost, credit_cost)
        """
        # Try to find exact model match, otherwise use base model name
        pricing = MODEL_PRICING.get(model_name)

        if not pricing:
            # Try to match base model (e.g., "gpt-4o-2024-08-06" -> "gpt-4o")
            for known_model in MODEL_PRICING.keys():
                if model_name.startswith(known_model):
                    pricing = MODEL_PRICING[known_model]
                    break

        if not pricing:
            logger.warning(f"Unknown model pricing for {model_name}, using gpt-4o-mini as fallback")
            pricing = MODEL_PRICING["gpt-4o-mini"]

        # Calculate cost in USD
        input_cost = (input_tokens / 1_000_000) * pricing.input_cost_per_1m
        output_cost = (output_tokens / 1_000_000) * pricing.output_cost_per_1m
        total_usd = input_cost + output_cost

        # Convert to credits (round up to nearest credit)
        total_credits = int(total_usd * CREDITS_PER_DOLLAR) + (
            1 if (total_usd * CREDITS_PER_DOLLAR) % 1 > 0 else 0
        )

        return total_usd, total_credits

    async def deduct_for_usage(
        self,
        model_name: str,
        input_tokens: int,
        output_tokens: int,
        request_id: Optional[str] = None,
    ) -> tuple[bool, int, str]:
        """
        Deduct credits for LLM usage.

        Returns:
            tuple[bool, int, str]: (success, credits_deducted, message)
        """
        user_credits = await self._ensure_loaded()
        usd_cost, credit_cost = self.calculate_cost(model_name, input_tokens, output_tokens)

        current_balance = await self.get_balance()

        if current_balance < credit_cost:
            msg = f"Insufficient credits. Required: {credit_cost}, Available: {current_balance}"
            logger.warning(f"User {self.user_id}: {msg}")
            return False, 0, msg

        # Deduct credits
        balance_before = user_credits.credits_left
        user_credits.credits_left -= credit_cost
        user_credits.updated_at = datetime.utcnow()

        # Log transaction
        transaction = CreditTransaction(
            user_id=self.user_id,
            amount=-credit_cost,  # Negative for deduction
            transaction_type="deduction",
            balance_before=balance_before,
            balance_after=user_credits.credits_left,
            model_name=model_name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            usd_cost=usd_cost,
            request_id=request_id,
            description=f"LLM API usage: {model_name}",
        )
        self._db.add(transaction)

        await self._db.commit()
        await self._db.refresh(user_credits)

        msg = f"Deducted {credit_cost} credits (${usd_cost:.4f}). Remaining: {user_credits.credits_left}"
        logger.info(f"User {self.user_id}: {msg}")

        return True, credit_cost, msg

    async def get_usage_summary(self) -> dict:
        """Get summary of credit usage from transaction history."""
        from sqlalchemy import desc

        balance = await self.get_balance()

        # Query all deduction transactions
        stmt = select(CreditTransaction).where(
            CreditTransaction.user_id == self.user_id,
            CreditTransaction.transaction_type == "deduction",
        )
        result = await self._db.execute(stmt)
        deductions = result.scalars().all()

        total_credits_spent = sum(abs(t.amount) for t in deductions)
        total_usd_spent = sum(float(t.usd_cost or 0) for t in deductions)
        request_count = len(deductions)

        # Query recent deduction transactions (last 10)
        recent_stmt = (
            select(CreditTransaction)
            .where(
                CreditTransaction.user_id == self.user_id,
                CreditTransaction.transaction_type == "deduction",
            )
            .order_by(desc(CreditTransaction.created_at))
            .limit(10)
        )
        recent_result = await self._db.execute(recent_stmt)
        recent_deductions = recent_result.scalars().all()

        # Format recent requests
        recent_requests = [
            {
                "timestamp": t.created_at.isoformat(),
                "model": t.model_name or "unknown",
                "input_tokens": t.input_tokens or 0,
                "output_tokens": t.output_tokens or 0,
                "usd_cost": float(t.usd_cost or 0),
                "credits_deducted": abs(t.amount),
                "balance_after": t.balance_after,
            }
            for t in recent_deductions
        ]

        return {
            "current_balance": balance,
            "user_id": str(self.user_id),
            "total_credits_spent": total_credits_spent,
            "total_usd_spent": total_usd_spent,
            "request_count": request_count,
            "recent_requests": recent_requests,
        }

    async def get_transaction_count(self, transaction_type: str | None = None) -> int:
        """Get total count of transactions for the user.

        Args:
            transaction_type: Filter by type ('addition', 'deduction', 'initial', 'refund')

        Returns:
            Total number of transactions
        """
        from sqlalchemy import func

        stmt = select(func.count(CreditTransaction.id)).where(
            CreditTransaction.user_id == self.user_id
        )

        if transaction_type:
            stmt = stmt.where(CreditTransaction.transaction_type == transaction_type)

        result = await self._db.execute(stmt)
        return result.scalar() or 0

    async def get_transaction_history(
        self, limit: int = 50, offset: int = 0, transaction_type: str | None = None
    ) -> list[dict]:
        """Get transaction history for the user with pagination.

        Args:
            limit: Maximum number of transactions to return (default 50)
            offset: Number of transactions to skip (for pagination)
            transaction_type: Filter by type ('addition', 'deduction', 'initial', 'refund')

        Returns:
            List of transaction dictionaries
        """
        from sqlalchemy import desc

        stmt = select(CreditTransaction).where(CreditTransaction.user_id == self.user_id)

        if transaction_type:
            stmt = stmt.where(CreditTransaction.transaction_type == transaction_type)

        stmt = stmt.order_by(desc(CreditTransaction.created_at)).limit(limit).offset(offset)

        result = await self._db.execute(stmt)
        transactions = result.scalars().all()

        return [
            {
                "id": str(t.id),
                "amount": t.amount,
                "transaction_type": t.transaction_type,
                "balance_before": t.balance_before,
                "balance_after": t.balance_after,
                "model_used": t.model_name,
                "tokens_input": t.input_tokens,
                "tokens_output": t.output_tokens,
                "cost_usd": float(t.usd_cost) if t.usd_cost else None,
                "request_id": t.request_id,
                "description": t.description,
                "created_at": t.created_at.isoformat(),
            }
            for t in transactions
        ]
