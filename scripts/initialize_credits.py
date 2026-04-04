"""Script to initialize user credits."""

import asyncio
import sys
from pathlib import Path
from uuid import UUID

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.billing.credit_manager import CREDITS_PER_DOLLAR, CreditManager
from src.core.db import get_session


async def initialize_user_credits(user_id: str, amount_usd: float = 5.0):
    """
    Initialize credits for a user.

    Args:
        user_id: User UUID as string
        amount_usd: Amount in USD to initialize (default $5)
    """
    credits = int(amount_usd * CREDITS_PER_DOLLAR)

    async for db in get_session():
        try:
            manager = CreditManager(user_id, db)

            current_balance = await manager.get_balance()
            if current_balance > 0:
                print(
                    f"User {user_id} already has {current_balance} credits (${current_balance/CREDITS_PER_DOLLAR:.2f})"
                )
                response = input("Add more credits? (y/n): ")
                if response.lower() != "y":
                    return

            new_balance = await manager.add_credits(credits)
            print(f"✅ Added {credits} credits (${amount_usd:.2f}) to user {user_id}")
            print(f"   New balance: {new_balance} credits (${new_balance/CREDITS_PER_DOLLAR:.2f})")
        except ValueError as e:
            print(f"❌ Error: {e}")
            sys.exit(1)
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            sys.exit(1)
        break


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python initialize_credits.py <user_id> [amount_usd]")
        print("Example: python initialize_credits.py 123e4567-e89b-12d3-a456-426614174000 5.0")
        sys.exit(1)

    user_id = sys.argv[1]
    amount_usd = float(sys.argv[2]) if len(sys.argv) > 2 else 5.0

    # Validate user_id is a valid UUID
    try:
        UUID(user_id)
    except ValueError:
        print(f"Error: '{user_id}' is not a valid UUID")
        sys.exit(1)

    asyncio.run(initialize_user_credits(user_id, amount_usd))
