"""Holdings service - pure class for business logic, no FastAPI imports"""

from typing import Optional
from uuid import UUID

import pandas as pd

from src.api.schemas.holdings import HoldingsRequestSchema, HoldingsResponseSchema
from src.core.schema import EquityHoldingSchema
from src.models.equity_holding import EquityHolding
from src.repositories.holdings_repo import HoldingsRepository


class HoldingsService:
    """Service layer for holdings operations"""

    def __init__(self, repo: HoldingsRepository):
        """
        Initialize HoldingsService.

        Args:
            repo: HoldingsRepository instance for data access
        """
        self.repo = repo

    async def save_user_holding(
        self, holding_schema: HoldingsRequestSchema, user_id: UUID
    ) -> HoldingsResponseSchema:
        """
        Save a new equity holding for a user.

        This is the use-case boundary - handles the full holding creation transaction.

        Args:
            holding_schema: Holdings data to save
            user_id: UUID of the user

        Returns:
            HoldingsResponseSchema with the created holding
        """
        # Create holding
        holding = await self.repo.add(
            user_id=user_id,
            broker_id=holding_schema.broker_id,
            symbol=holding_schema.symbol,
            isin=holding_schema.isin,
            sector=holding_schema.sector,
            qty_available=holding_schema.qty_available,
            qty_long_term=holding_schema.qty_long_term,
            qty_pledged_margin=holding_schema.qty_pledged_margin,
            avg_price=holding_schema.avg_price,
            prev_close_price=holding_schema.prev_close_price,
        )

        # Commit at the use-case boundary
        await self.repo.session.commit()

        return HoldingsResponseSchema.model_validate(holding)

    async def save_user_holdings(
        self, holdings_list: list[HoldingsRequestSchema], user_id: UUID
    ) -> int:
        """
        Save multiple equity holdings for a user (upsert).

        If holdings already exist for the user-broker pair:
        - Updates existing holdings (matched by ISIN), preserving created_at
        - Inserts new holdings
        - Deletes holdings that are not in the new list

        This is the use-case boundary - handles the full bulk holding transaction.

        Args:
            holdings_list: List of holdings data to save
            user_id: UUID of the user

        Returns:
            Number of holdings processed (updated + inserted)
        """
        if not holdings_list:
            return 0

        # All holdings in the list share the same broker_id
        broker_id = holdings_list[0].broker_id

        # Create list of EquityHolding objects
        holdings = [
            EquityHolding(
                user_id=user_id,
                broker_id=holding.broker_id,
                symbol=holding.symbol,
                isin=holding.isin,
                sector=holding.sector,
                qty_available=holding.qty_available,
                qty_long_term=holding.qty_long_term,
                qty_pledged_margin=holding.qty_pledged_margin,
                avg_price=holding.avg_price,
                prev_close_price=holding.prev_close_price,
            )
            for holding in holdings_list
        ]

        # Upsert holdings (update existing, insert new, delete removed)
        updated_count, inserted_count = await self.repo.upsert_holdings(
            user_id=user_id, broker_id=broker_id, holdings=holdings
        )

        # Commit at the use-case boundary
        await self.repo.session.commit()

        return updated_count + inserted_count

    async def get_portfolio_df(
        self, user_id: UUID, broker_id: Optional[UUID] = None
    ) -> pd.DataFrame:
        """
        Retrieve the full portfolio for a user and return it as a DataFrame.

        Args:
            user_id: UUID of the user
            broker_id: Optional UUID of the broker. If None, returns holdings for all brokers.

        Returns:
            pandas.DataFrame of holdings with id/user_id/broker_id columns removed
        """
        # Use the table definition to keep a stable column order and drop identity fields
        columns = [
            column.name
            for column in EquityHolding.__table__.columns
            if column.name not in {"id", "user_id", "broker_id"}
        ]

        # Get holdings based on whether broker_id is provided
        if broker_id is not None:
            holdings = await self.repo.by_user_and_broker(user_id=user_id, broker_id=broker_id)
        else:
            holdings = await self.repo.by_user_id(user_id=user_id)

        if not holdings:
            return pd.DataFrame(columns=EquityHoldingSchema.get_supported_columns())

        data = [{col: getattr(holding, col) for col in columns} for holding in holdings]
        return pd.DataFrame(data, columns=EquityHoldingSchema.get_supported_columns())
