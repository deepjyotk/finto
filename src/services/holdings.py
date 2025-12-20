"""Holdings service - pure class for business logic, no FastAPI imports"""

from typing import Optional
from uuid import UUID

import pandas as pd

from src.api.schemas.holdings import HoldingsRequestSchema
from src.core.schema import EquityHoldingSchema
from src.models.equity_holding import EquityHolding
from src.models.equity_holding_metadata import UploadedVia
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

    async def save_user_holdings(
        self,
        holdings_list: list[HoldingsRequestSchema],
        user_id: UUID,
        uploaded_via: UploadedVia = UploadedVia.USER_FILE_UPLOAD,
    ) -> int:
        """
        Save multiple equity holdings for a user (upsert).

        If holdings already exist for the user-broker pair:
        - Updates existing holdings (matched by ISIN)
        - Inserts new holdings
        - Deletes holdings that are not in the new list

        This is the use-case boundary - handles the full bulk holding transaction.

        Args:
            holdings_list: List of holdings data to save
            user_id: UUID of the user
            uploaded_via: How the holdings were uploaded

        Returns:
            Number of holdings processed (updated + inserted)
        """
        if not holdings_list:
            return 0

        # All holdings in the list share the same broker_id
        broker_id = holdings_list[0].broker_id

        # Create list of EquityHolding objects (user_broker_id will be set by upsert_holdings)
        holdings = [
            EquityHolding(
                user_broker_id=None,  # Will be set by upsert_holdings
                symbol=holding.symbol,
                company_name=holding.company_name,
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
            user_id=user_id,
            broker_id=broker_id,
            holdings=holdings,
            uploaded_via=uploaded_via,
        )

        # Commit at the use-case boundary
        await self.repo.session.commit()

        return updated_count + inserted_count

    async def upsert_user_holdings(
        self,
        holdings_list: list[HoldingsRequestSchema],
        user_id: UUID,
        user_broker_id: UUID,
    ) -> tuple[int, int, int]:
        """
        Upsert equity holdings for a user using user_broker_id.

        Compares symbols in holdings_list with existing DB records:
        - Updates existing holdings (matched by symbol)
        - Inserts new holdings
        - Deletes holdings that are not in the new list
        - Updates the updated_at timestamp in metadata

        Args:
            holdings_list: List of holdings data to upsert
            user_id: UUID of the user
            user_broker_id: UUID of the user-broker metadata

        Returns:
            Tuple of (updated_count, inserted_count, deleted_count)

        Raises:
            ValueError: If user_broker_id not found or doesn't belong to user
        """
        # Verify metadata exists and belongs to user
        metadata = await self.repo.get_metadata_by_user_broker_id(user_broker_id, user_id)
        if metadata is None:
            raise ValueError("Holdings metadata not found or access denied")

        if not holdings_list:
            return 0, 0, 0

        # Create list of EquityHolding objects
        holdings = [
            EquityHolding(
                user_broker_id=user_broker_id,
                symbol=holding.symbol,
                company_name=holding.company_name,
                sector=holding.sector,
                qty_available=holding.qty_available,
                qty_long_term=holding.qty_long_term,
                qty_pledged_margin=holding.qty_pledged_margin,
                avg_price=holding.avg_price,
                prev_close_price=holding.prev_close_price,
            )
            for holding in holdings_list
        ]

        # Upsert holdings
        updated_count, inserted_count, deleted_count = (
            await self.repo.upsert_holdings_by_user_broker_id(
                user_broker_id=user_broker_id,
                holdings=holdings,
            )
        )

        # Update metadata timestamp
        await self.repo.update_metadata_timestamp(user_broker_id)

        # Commit at the use-case boundary
        await self.repo.session.commit()

        return updated_count, inserted_count, deleted_count

    async def get_portfolio_df(
        self, user_id: UUID, broker_id: Optional[UUID] = None
    ) -> pd.DataFrame:
        """
        Retrieve the full portfolio for a user and return it as a DataFrame.

        Args:
            user_id: UUID of the user
            broker_id: Optional UUID of the broker. If None, returns holdings for all brokers.

        Returns:
            pandas.DataFrame of holdings with id/user_broker_id columns removed
        """
        # Use the table definition to keep a stable column order and drop identity fields
        columns = [
            column.name
            for column in EquityHolding.__table__.columns
            if column.name not in {"id", "user_broker_id"}
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

    async def get_portfolio_updates(self, user_id: UUID) -> list[dict]:
        metadata_list = await self.repo.get_metadata_with_broker_name(user_id)
        return [
            {
                "broker_id": str(m["broker_id"]),
                "broker_name": m["broker_name"],
                "broker_user_id": str(m["user_broker_id"]),
                "last_updated_at": m["updated_at"],
                "uploaded_via": m["uploaded_via"],
                "additional_metadata": m["extra_metadata"] or {},
            }
            for m in metadata_list
        ]
