"""Holdings repository - pure class for data access, no FastAPI imports"""

from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.equity_holding import EquityHolding


class HoldingsRepository:
    """Repository for EquityHolding data access operations"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def add(
        self,
        user_id: UUID,
        broker_id: UUID,
        symbol: str,
        isin: str,
        sector: str | None,
        qty_available: int,
        qty_long_term: int,
        qty_pledged_margin: int,
        avg_price: Decimal,
        prev_close_price: Decimal,
    ) -> EquityHolding:
        """
        Add a new equity holding to the database.

        Args:
            user_id: UUID of the user
            broker_id: UUID of the broker
            symbol: Trading symbol
            isin: ISIN code
            sector: Sector (optional)
            qty_available: Available quantity
            qty_long_term: Long term quantity
            qty_pledged_margin: Quantity pledged for margin
            avg_price: Average purchase price
            prev_close_price: Previous closing price

        Returns:
            The created EquityHolding object
        """
        holding = EquityHolding(
            user_id=user_id,
            broker_id=broker_id,
            symbol=symbol,
            isin=isin,
            sector=sector,
            qty_available=qty_available,
            qty_long_term=qty_long_term,
            qty_pledged_margin=qty_pledged_margin,
            avg_price=avg_price,
            prev_close_price=prev_close_price,
        )
        self.session.add(holding)
        await self.session.flush()  # Get the holding with auto-generated fields
        return holding

    async def by_id(self, holding_id: UUID) -> Optional[EquityHolding]:
        """
        Find holding by ID.

        Args:
            holding_id: The holding ID to search for

        Returns:
            EquityHolding object if found, None otherwise
        """
        result = await self.session.execute(
            select(EquityHolding).where(EquityHolding.id == holding_id)
        )
        return result.scalar_one_or_none()

    async def by_user_id(self, user_id: UUID) -> list[EquityHolding]:
        """
        Find all holdings for a user.

        Args:
            user_id: The user ID to search for

        Returns:
            List of EquityHolding objects
        """
        result = await self.session.execute(
            select(EquityHolding).where(EquityHolding.user_id == user_id)
        )
        return list(result.scalars().all())

    async def by_user_and_broker(self, user_id: UUID, broker_id: UUID) -> list[EquityHolding]:
        """
        Find all holdings for a user with a specific broker.

        Args:
            user_id: The user ID to search for
            broker_id: The broker ID to filter by

        Returns:
            List of EquityHolding objects
        """
        result = await self.session.execute(
            select(EquityHolding).where(
                EquityHolding.user_id == user_id, EquityHolding.broker_id == broker_id
            )
        )
        return list(result.scalars().all())

    async def add_all(self, holdings: list[EquityHolding]) -> list[EquityHolding]:
        """
        Add multiple equity holdings to the database efficiently.

        Args:
            holdings: List of EquityHolding objects to add

        Returns:
            List of created EquityHolding objects
        """
        self.session.add_all(holdings)
        await self.session.flush()  # Get all holdings with auto-generated fields
        return holdings

    async def delete_by_user_and_broker(self, user_id: UUID, broker_id: UUID) -> int:
        """
        Delete all holdings for a user with a specific broker.

        Args:
            user_id: The user ID
            broker_id: The broker ID

        Returns:
            Number of deleted records
        """
        from sqlalchemy import delete

        result = await self.session.execute(
            delete(EquityHolding).where(
                EquityHolding.user_id == user_id, EquityHolding.broker_id == broker_id
            )
        )
        return result.rowcount

    async def upsert_holdings(
        self, user_id: UUID, broker_id: UUID, holdings: list[EquityHolding]
    ) -> tuple[int, int]:
        """
        Upsert holdings for a user-broker pair.

        - Updates existing holdings (matched by ISIN), preserving created_at
        - Inserts new holdings
        - Deletes holdings that are not in the new list

        Args:
            user_id: The user ID
            broker_id: The broker ID
            holdings: List of new EquityHolding objects

        Returns:
            Tuple of (updated_count, inserted_count)
        """
        from sqlalchemy import func, update

        if not holdings:
            return 0, 0

        # Get existing holdings for this user-broker pair
        existing_holdings = await self.by_user_and_broker(user_id, broker_id)

        # Create a map of normalized ISIN -> existing holding
        # Normalize ISINs to handle case/whitespace differences
        existing_by_isin: dict[str, EquityHolding] = {
            h.isin.strip().upper(): h for h in existing_holdings
        }

        # Track normalized ISINs in the new data
        new_isins: set[str] = {h.isin.strip().upper() for h in holdings}

        updated_count = 0
        inserted_count = 0

        for new_holding in holdings:
            normalized_isin = new_holding.isin.strip().upper()
            existing = existing_by_isin.get(normalized_isin)

            if existing:
                # Update existing holding using explicit UPDATE statement
                # Explicitly set updated_at since onupdate doesn't trigger for raw SQL
                stmt = (
                    update(EquityHolding)
                    .where(EquityHolding.id == existing.id)
                    .values(
                        symbol=new_holding.symbol,
                        sector=new_holding.sector,
                        qty_available=new_holding.qty_available,
                        qty_long_term=new_holding.qty_long_term,
                        qty_pledged_margin=new_holding.qty_pledged_margin,
                        avg_price=new_holding.avg_price,
                        prev_close_price=new_holding.prev_close_price,
                        updated_at=func.now(),
                    )
                )
                await self.session.execute(stmt)
                updated_count += 1
            else:
                # Insert new holding
                self.session.add(new_holding)
                inserted_count += 1

        # Delete holdings that are not in the new list
        for isin, existing in existing_by_isin.items():
            if isin not in new_isins:
                await self.session.delete(existing)

        await self.session.flush()
        return updated_count, inserted_count
