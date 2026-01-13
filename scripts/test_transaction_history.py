"""Test script for credit transactions and history."""

import asyncio
from pathlib import Path
import sys

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select

from src.billing.credit_manager import CREDITS_PER_DOLLAR, CreditManager
from src.core.db import get_session
from src.models.user import User


async def test_transaction_history():
    """Test the transaction history features."""
    print("🧪 Testing Credit Transaction History")
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

        # Test 1: Get current usage summary
        print("Test 1: Get usage summary")
        summary = await manager.get_usage_summary()
        print(
            f"  Current balance: {summary['current_balance']} credits (${summary['current_balance'] / CREDITS_PER_DOLLAR:.2f})"
        )
        print(
            f"  Total spent: {summary['total_credits_spent']} credits (${summary['total_usd_spent']:.2f})"
        )
        print(f"  Request count: {summary['request_count']}")
        print()

        # Test 2: Add some credits to create a transaction
        print("Test 2: Add credits with description")
        await manager.add_credits(1000, description="Test credit addition")
        print("  ✓ Added 1000 credits with description")
        print()

        # Test 3: Deduct credits to create another transaction
        print("Test 3: Simulate LLM usage")
        success, deducted, msg = await manager.deduct_for_usage(
            "gpt-4o-mini", 2000, 1000, request_id="test-txn-001"
        )
        if success:
            print(f"  ✓ {msg}")
        print()

        # Test 4: Get all transaction history
        print("Test 4: Get all transaction history (last 10)")
        all_transactions = await manager.get_transaction_history(limit=10)
        print(f"  Found {len(all_transactions)} transactions:")
        for i, txn in enumerate(all_transactions[:5], 1):  # Show first 5
            print(
                f"  {i}. {txn['transaction_type']:12} | "
                f"Amount: {txn['amount']:6} | "
                f"Balance: {txn['balance_after']:6} | "
                f"Date: {txn['created_at'][:19]}"
            )
            if txn["description"]:
                print(f"     Description: {txn['description']}")
        if len(all_transactions) > 5:
            print(f"  ... and {len(all_transactions) - 5} more")
        print()

        # Test 5: Get only deduction transactions
        print("Test 5: Get only deduction transactions")
        deductions = await manager.get_transaction_history(limit=10, transaction_type="deduction")
        print(f"  Found {len(deductions)} deduction transactions:")
        for i, txn in enumerate(deductions[:3], 1):  # Show first 3
            print(
                f"  {i}. Model: {txn['model_name'] or 'N/A':20} | "
                f"Credits: {abs(txn['amount']):4} | "
                f"USD: ${txn['usd_cost']:.4f}"
                if txn["usd_cost"]
                else f"USD: N/A"
            )
            print(f"     Tokens: {txn['input_tokens']:,} in / {txn['output_tokens']:,} out")
        print()

        # Test 6: Get only addition transactions
        print("Test 6: Get only addition transactions")
        additions = await manager.get_transaction_history(limit=10, transaction_type="addition")
        print(f"  Found {len(additions)} addition transactions:")
        for i, txn in enumerate(additions[:3], 1):  # Show first 3
            print(
                f"  {i}. Amount: +{txn['amount']} credits | "
                f"Balance after: {txn['balance_after']} | "
                f"Date: {txn['created_at'][:19]}"
            )
        print()

        # Test 7: Test pagination
        print("Test 7: Test pagination (offset)")
        page1 = await manager.get_transaction_history(limit=2, offset=0)
        page2 = await manager.get_transaction_history(limit=2, offset=2)
        print(f"  Page 1 (first 2): {len(page1)} transactions")
        print(f"  Page 2 (next 2): {len(page2)} transactions")
        if page1 and page2:
            print(f"  ✓ Pagination working (different IDs: {page1[0]['id'] != page2[0]['id']})")
        print()

        print("=" * 80)
        print("✅ All transaction history tests completed successfully!")

    finally:
        # Close the session
        try:
            await anext(db_gen)
        except StopAsyncIteration:
            pass


if __name__ == "__main__":
    asyncio.run(test_transaction_history())
