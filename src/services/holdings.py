"""Holdings service - pure class for business logic, no FastAPI imports"""

from decimal import Decimal
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
        (
            updated_count,
            inserted_count,
            deleted_count,
        ) = await self.repo.upsert_holdings_by_user_broker_id(
            user_broker_id=user_broker_id,
            holdings=holdings,
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

    async def sync_holdings(
        self,
        holdings_list: list[dict],
        user_id: UUID,
        broker_id: UUID,
    ) -> tuple[int, int]:
        """
        Sync holdings from Kite API to the database.

        For each holding, check if it exists for the user by symbol.
        If exists and has changed, update it. If not, create new.

        Args:
            holdings_list: List of holding dicts from Kite API
            user_id: UUID of the user
            broker_id: UUID of the broker

        Returns:
            Tuple of (synced_count, updated_count)
        """
        if not holdings_list:
            return 0, 0

        # Get or create metadata for this user-broker pair
        # Metadata is required because holdings table has FK to it
        metadata = await self.repo.get_or_create_metadata(
            user_id, broker_id, UploadedVia.USER_FILE_UPLOAD
        )

        synced_count = 0
        updated_count = 0

        for holding_data in holdings_list:
            # Extract fields from Kite holding data
            symbol = holding_data.get("tradingsymbol", "")
            if not symbol:
                continue  # Skip if no symbol

            quantity = holding_data.get("quantity", 0)
            average_price = Decimal(str(holding_data.get("average_price", 0)))
            last_price = Decimal(str(holding_data.get("last_price", 0)))
            company_name = holding_data.get("tradingsymbol", "")  # Use symbol as fallback

            # Check if holding exists
            existing_holding = await self.repo.get_holding_by_symbol(
                metadata.user_broker_id, symbol
            )

            if existing_holding:
                # Check if any field has changed
                has_changed = (
                    existing_holding.qty_available != quantity
                    or existing_holding.avg_price != average_price
                    or existing_holding.prev_close_price != last_price
                )

                if has_changed:
                    # Update existing holding
                    existing_holding.qty_available = quantity
                    existing_holding.avg_price = average_price
                    existing_holding.prev_close_price = last_price
                    updated_count += 1
            else:
                # Create new holding
                new_holding = EquityHolding(
                    user_broker_id=metadata.user_broker_id,
                    symbol=symbol,
                    company_name=company_name,
                    sector=None,
                    qty_available=quantity,
                    qty_long_term=0,
                    qty_pledged_margin=0,
                    avg_price=average_price,
                    prev_close_price=last_price,
                )
                self.repo.session.add(new_holding)

            synced_count += 1

        # Update metadata timestamp
        await self.repo.update_metadata_timestamp(metadata.user_broker_id)

        # Create sync record
        await self.repo.create_sync_record(user_id, synced_count, updated_count)

        # Commit at the use-case boundary
        await self.repo.session.commit()

        return synced_count, updated_count

    async def get_sync_status(self, user_id: UUID) -> Optional[dict]:
        """
        Get the most recent sync status for a user.

        Args:
            user_id: UUID of the user

        Returns:
            Dict with last_sync, synced_count, updated_count, or None if no syncs found
        """
        sync_record = await self.repo.get_most_recent_sync(user_id)

        if sync_record is None:
            return None

        return {
            "last_sync": sync_record.synced_at.isoformat(),
            "synced_count": sync_record.synced_count,
            "updated_count": sync_record.updated_count,
        }

    async def delete_broker_holdings(self, user_id: UUID, broker_id: UUID) -> tuple[int, bool]:
        """
        Delete all holdings and metadata for a user-broker pair.

        This removes:
        - All equity holdings for the user-broker pair (via cascade)
        - The metadata record for the user-broker pair

        Args:
            user_id: UUID of the user
            broker_id: UUID of the broker

        Returns:
            Tuple of (deleted_holdings_count, metadata_deleted)
            - deleted_holdings_count: Number of holdings deleted (via cascade)
            - metadata_deleted: True if metadata was deleted, False if not found

        Raises:
            ValueError: If broker_id is invalid or user doesn't have holdings for this broker
        """
        # Get metadata first to count holdings before deletion
        metadata = await self.repo.get_metadata_by_user_and_broker(user_id, broker_id)
        if metadata is None:
            # Metadata not found - let's check what metadata exists for this user
            from src.core.json_logging import logger_for

            logger = logger_for(__name__)

            # Debug: Get all metadata for this user to see what exists
            all_metadata = await self.repo.get_metadata_by_user_id(user_id)
            logger.warning(
                "delete_broker_holdings_metadata_not_found_debug",
                extra={
                    "user_id": str(user_id),
                    "broker_id": str(broker_id),
                    "existing_metadata_count": len(all_metadata),
                    "existing_broker_ids": [str(m.broker_id) for m in all_metadata],
                },
            )
            return 0, False

        # Count holdings before deletion
        holdings = await self.repo.by_user_broker_id(metadata.user_broker_id)
        deleted_holdings_count = len(holdings)

        # Delete metadata record using repository method (this will cascade delete all holdings)
        metadata_deleted = await self.repo.delete_metadata_by_user_and_broker(user_id, broker_id)

        if not metadata_deleted:
            # This shouldn't happen since we found metadata above, but handle it
            return 0, False

        # Commit at the use-case boundary
        await self.repo.session.commit()

        return deleted_holdings_count, True
