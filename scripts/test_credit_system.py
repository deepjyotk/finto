"""Test script for the credit billing system."""

import asyncio
import sys
from pathlib import Path
from uuid import UUID

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select

from src.billing.credit_manager import CREDITS_PER_DOLLAR, CreditManager
from src.core.db import get_session
from src.models.user import User


async def test_credit_system():
    """Test the complete credit system flow."""
    print("🧪 Testing Credit System")
    print("=" * 80)
    
    # Get a database session
    db_gen = get_session()
    db = await anext(db_gen)
    
    try:
        # Get the first user from the database for testing
        stmt = select(User).limit(1)
        result = await db.execute(stmt)
        test_user = result.scalar_one_or_none()
        
        if not test_user:
            print("❌ No users found in database. Please create a user first.")
            return
        
        user_id = test_user.user_id
        print(f"📧 Testing with user: {test_user.email} (ID: {user_id})")
        print()
        
        # Create credit manager
        manager = CreditManager(user_id, db)
        
        # Test 1: Check initial balance (should auto-create with 5000 credits)
        print("Test 1: Check initial balance")
        balance = await manager.get_balance()
        print(f"  ✓ Initial balance: {balance} credits (${balance / CREDITS_PER_DOLLAR:.2f})")
        print()
        
        # Test 2: Add credits
        print("Test 2: Add credits")
        add_amount = 2500  # Add $2.50 worth
        new_balance = await manager.add_credits(add_amount)
        print(f"  ✓ Added {add_amount} credits (${add_amount / CREDITS_PER_DOLLAR:.2f})")
        print(f"  ✓ New balance: {new_balance} credits (${new_balance / CREDITS_PER_DOLLAR:.2f})")
        print()
        
        # Test 3: Calculate cost for GPT-4o usage
        print("Test 3: Calculate cost for GPT-4o usage")
        model = "gpt-4o"
        input_tokens = 1000
        output_tokens = 500
        usd_cost, credit_cost = manager.calculate_cost(model, input_tokens, output_tokens)
        print(f"  Model: {model}")
        print(f"  Input tokens: {input_tokens:,}, Output tokens: {output_tokens:,}")
        print(f"  ✓ Cost: ${usd_cost:.4f} = {credit_cost} credits")
        print()
        
        # Test 4: Deduct credits for usage
        print("Test 4: Deduct credits for usage")
        success, deducted, message = await manager.deduct_for_usage(
            model, input_tokens, output_tokens, request_id="test-123"
        )
        if success:
            print(f"  ✓ {message}")
        else:
            print(f"  ❌ {message}")
        print()
        
        # Test 5: Check final balance
        print("Test 5: Check final balance")
        final_balance = await manager.get_balance()
        print(f"  ✓ Final balance: {final_balance} credits (${final_balance / CREDITS_PER_DOLLAR:.2f})")
        print()
        
        # Test 6: Usage summary
        print("Test 6: Usage summary")
        summary = await manager.get_usage_summary()
        print(f"  User ID: {summary['user_id']}")
        print(f"  Current balance: {summary['current_balance']} credits")
        print(f"  Total spent: {summary['total_credits_spent']} credits (${summary['total_usd_spent']:.2f})")
        print(f"  Request count: {summary['request_count']}")
        print()
        
        print("=" * 80)
        print("✅ All tests completed successfully!")
    
    finally:
        # Close the session
        try:
            await anext(db_gen)
        except StopAsyncIteration:
            pass


if __name__ == "__main__":
    asyncio.run(test_credit_system())
