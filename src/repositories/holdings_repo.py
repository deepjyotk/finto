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
        qty_discrepant: int,
        qty_long_term: int,
        qty_pledged_margin: int,
        qty_pledged_loan: int,
        avg_price: Decimal,
        prev_close_price: Decimal,
        unrealized_pnl: Decimal,
        unrealized_pnl_pct: Decimal,
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
            qty_discrepant: Discrepant quantity
            qty_long_term: Long term quantity
            qty_pledged_margin: Quantity pledged for margin
            qty_pledged_loan: Quantity pledged for loan
            avg_price: Average purchase price
            prev_close_price: Previous closing price
            unrealized_pnl: Unrealized profit/loss
            unrealized_pnl_pct: Unrealized PnL percentage

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
            qty_discrepant=qty_discrepant,
            qty_long_term=qty_long_term,
            qty_pledged_margin=qty_pledged_margin,
            qty_pledged_loan=qty_pledged_loan,
            avg_price=avg_price,
            prev_close_price=prev_close_price,
            unrealized_pnl=unrealized_pnl,
            unrealized_pnl_pct=unrealized_pnl_pct,
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

