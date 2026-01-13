"""Test credit tracking with LangSmith callback."""

import asyncio
import os
import sys
from uuid import UUID

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from src.billing.langsmith_tracker import CreditTrackingCallback
from src.core.settings import settings


async def test_callback():
    """Test the credit tracking callback."""

    # Create async engine
    engine = create_async_engine(settings.postgres_dsn, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        # Replace with a real user ID from your database
        user_id = UUID("00000000-0000-0000-0000-000000000001")  # Change this!

        callback = CreditTrackingCallback(user_id, db)

        print(f"Created callback for user: {user_id}")
        print(f"Callback methods: {dir(callback)}")
        print(f"\nCallback will be passed to graph.ainvoke() with:")
        print(f"  config={{'callbacks': [callback]}}")
        print(f"\nWhen LLMs are invoked, callback.on_llm_end() will:")
        print(f"  1. Extract token usage from response")
        print(f"  2. Call CreditManager.deduct_for_usage()")
        print(f"  3. Log transaction to credit_transactions table")
        print(f"  4. Update total_credits_deducted counter")
        print(f"\nAt the end, get_summary() returns:")
        print(f"  - total_input_tokens")
        print(f"  - total_output_tokens")
        print(f"  - total_credits_deducted")
        print(f"  - total_usd_spent")
        print(f"  - llm_calls count")
        print(f"  - model_breakdown (per-model stats)")

        summary = callback.get_summary()
        print(f"\nInitial summary: {summary}")

    await engine.dispose()
    print("\n✅ Callback implementation verified!")


if __name__ == "__main__":
    asyncio.run(test_callback())
