"""Holdings repository - pure class for data access, no FastAPI imports"""

from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import and_, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.broker import Broker
from src.models.equity_holding import EquityHolding
from src.models.equity_holding_metadata import EquityHoldingMetadata, UploadedVia
from src.models.holding_sync import HoldingSync


class HoldingsRepository:
    """Repository for EquityHolding data access operations"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_or_create_metadata(
        self,
        user_id: UUID,
        broker_id: UUID,
        uploaded_via: UploadedVia = UploadedVia.USER_FILE_UPLOAD,
    ) -> EquityHoldingMetadata:
        """
        Get existing metadata record or create a new one for the user-broker pair.

        Args:
            user_id: UUID of the user
            broker_id: UUID of the broker
            uploaded_via: How the holdings were uploaded

        Returns:
            The existing or newly created EquityHoldingMetadata object
        """
        result = await self.session.execute(
            select(EquityHoldingMetadata).where(
                and_(
                    EquityHoldingMetadata.user_id == user_id,
                    EquityHoldingMetadata.broker_id == broker_id,
                )
            )
        )
        metadata = result.scalar_one_or_none()

        if metadata is None:
            metadata = EquityHoldingMetadata(
                user_id=user_id,
                broker_id=broker_id,
                uploaded_via=uploaded_via,
            )
            self.session.add(metadata)
            await self.session.flush()

        return metadata

    async def get_metadata_by_user_and_broker(
        self, user_id: UUID, broker_id: UUID
    ) -> Optional[EquityHoldingMetadata]:
        """
        Get metadata record for a user-broker pair.

        Args:
            user_id: UUID of the user
            broker_id: UUID of the broker

        Returns:
            EquityHoldingMetadata object if found, None otherwise
        """
        result = await self.session.execute(
            select(EquityHoldingMetadata).where(
                and_(
                    EquityHoldingMetadata.user_id == user_id,
                    EquityHoldingMetadata.broker_id == broker_id,
                )
            )
        )
        return result.scalar_one_or_none()

    async def get_metadata_by_user_broker_id(
        self, user_broker_id: UUID, user_id: UUID
    ) -> Optional[EquityHoldingMetadata]:
        """
        Get metadata record by user_broker_id, verifying it belongs to the user.

        Args:
            user_broker_id: UUID of the user-broker metadata
            user_id: UUID of the user (for ownership verification)

        Returns:
            EquityHoldingMetadata object if found and owned by user, None otherwise
        """
        result = await self.session.execute(
            select(EquityHoldingMetadata).where(
                and_(
                    EquityHoldingMetadata.user_broker_id == user_broker_id,
                    EquityHoldingMetadata.user_id == user_id,
                )
            )
        )
        return result.scalar_one_or_none()

    async def get_user_brokers(self, user_id: UUID) -> list[dict]:
        """
        Get all brokers that a user has holdings with.

        Args:
            user_id: UUID of the user

        Returns:
            List of dicts with broker_id and broker_name
        """
        from sqlalchemy import cast
        from sqlalchemy.types import String

        result = await self.session.execute(
            select(
                Broker.broker_id,
                cast(Broker.broker_name, String).label("broker_name"),
            )
            .join(
                EquityHoldingMetadata,
                EquityHoldingMetadata.broker_id == Broker.broker_id,
            )
            .where(EquityHoldingMetadata.user_id == user_id)
        )

        return [{"broker_id": row.broker_id, "broker_name": row.broker_name} for row in result]

    async def get_metadata_by_user_id(self, user_id: UUID) -> list[EquityHoldingMetadata]:
        result = await self.session.execute(
            select(EquityHoldingMetadata).where(EquityHoldingMetadata.user_id == user_id)
        )
        return list(result.scalars().all())

    async def get_metadata_with_broker_name(self, user_id: UUID) -> list[dict]:
        from sqlalchemy import cast
        from sqlalchemy.types import String

        result = await self.session.execute(
            select(
                EquityHoldingMetadata.broker_id,
                cast(Broker.broker_name, String).label("broker_name"),
                EquityHoldingMetadata.user_broker_id,
                EquityHoldingMetadata.updated_at,
                cast(EquityHoldingMetadata.uploaded_via, String).label("uploaded_via"),
                EquityHoldingMetadata.extra_metadata,
            )
            .join(Broker, Broker.broker_id == EquityHoldingMetadata.broker_id)
            .where(EquityHoldingMetadata.user_id == user_id)
        )
        return [
            {
                "broker_id": row.broker_id,
                "broker_name": row.broker_name,
                "user_broker_id": row.user_broker_id,
                "updated_at": row.updated_at,
                "uploaded_via": row.uploaded_via,
                "extra_metadata": row.extra_metadata,
            }
            for row in result
        ]

    async def add(
        self,
        user_id: UUID,
        broker_id: UUID,
        symbol: str,
        company_name: str,
        sector: str | None,
        qty_available: int,
        qty_long_term: int,
        qty_pledged_margin: int,
        avg_price: Decimal,
        prev_close_price: Decimal,
        uploaded_via: UploadedVia = UploadedVia.USER_FILE_UPLOAD,
    ) -> EquityHolding:
        """
        Add a new equity holding to the database.

        Args:
            user_id: UUID of the user
            broker_id: UUID of the broker
            symbol: Trading symbol (FK to in_equities.symbol)
            company_name: Company name (FK to in_equities.company_name)
            sector: Sector (optional)
            qty_available: Available quantity
            qty_long_term: Long term quantity
            qty_pledged_margin: Quantity pledged for margin
            avg_price: Average purchase price
            prev_close_price: Previous closing price
            uploaded_via: How the holdings were uploaded

        Returns:
            The created EquityHolding object
        """
        # Get or create metadata for this user-broker pair
        metadata = await self.get_or_create_metadata(user_id, broker_id, uploaded_via)

        holding = EquityHolding(
            user_broker_id=metadata.user_broker_id,
            symbol=symbol,
            company_name=company_name,
            sector=sector,
            qty_available=qty_available,
            qty_long_term=qty_long_term,
            qty_pledged_margin=qty_pledged_margin,
            avg_price=avg_price,
            prev_close_price=prev_close_price,
        )
        self.session.add(holding)
        await self.session.flush()
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
        # Get all metadata records for this user
        metadata_list = await self.get_metadata_by_user_id(user_id)
        if not metadata_list:
            return []

        user_broker_ids = [m.user_broker_id for m in metadata_list]

        result = await self.session.execute(
            select(EquityHolding).where(EquityHolding.user_broker_id.in_(user_broker_ids))
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
        # Get the metadata for this user-broker pair
        metadata = await self.get_metadata_by_user_and_broker(user_id, broker_id)
        if metadata is None:
            return []

        result = await self.session.execute(
            select(EquityHolding).where(EquityHolding.user_broker_id == metadata.user_broker_id)
        )
        return list(result.scalars().all())

    async def by_user_broker_id(self, user_broker_id: UUID) -> list[EquityHolding]:
        """
        Find all holdings for a user_broker_id.

        Args:
            user_broker_id: The user_broker_id to search for

        Returns:
            List of EquityHolding objects
        """
        result = await self.session.execute(
            select(EquityHolding).where(EquityHolding.user_broker_id == user_broker_id)
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
        await self.session.flush()
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

        # Get the metadata for this user-broker pair
        metadata = await self.get_metadata_by_user_and_broker(user_id, broker_id)
        if metadata is None:
            return 0

        result = await self.session.execute(
            delete(EquityHolding).where(EquityHolding.user_broker_id == metadata.user_broker_id)
        )
        return result.rowcount

    async def delete_by_user_broker_id(self, user_broker_id: UUID) -> int:
        """
        Delete all holdings for a user_broker_id.

        Args:
            user_broker_id: The user_broker_id

        Returns:
            Number of deleted records
        """
        from sqlalchemy import delete

        result = await self.session.execute(
            delete(EquityHolding).where(EquityHolding.user_broker_id == user_broker_id)
        )
        return result.rowcount

    async def upsert_holdings(
        self,
        user_id: UUID,
        broker_id: UUID,
        holdings: list[EquityHolding],
        uploaded_via: UploadedVia = UploadedVia.USER_FILE_UPLOAD,
    ) -> tuple[int, int]:
        """
        Upsert holdings for a user-broker pair.

        - Updates existing holdings (matched by ISIN)
        - Inserts new holdings
        - Deletes holdings that are not in the new list

        Args:
            user_id: The user ID
            broker_id: The broker ID
            holdings: List of new EquityHolding objects
            uploaded_via: How the holdings were uploaded

        Returns:
            Tuple of (updated_count, inserted_count)
        """
        if not holdings:
            return 0, 0

        # Get or create metadata for this user-broker pair
        metadata = await self.get_or_create_metadata(user_id, broker_id, uploaded_via)

        # Get existing holdings for this user-broker pair
        existing_holdings = await self.by_user_broker_id(metadata.user_broker_id)

        # Create a map of normalized company_name -> existing holding
        # Normalize company_name to handle case/whitespace differences
        existing_by_company_name: dict[str, EquityHolding] = {
            h.company_name.strip().upper(): h for h in existing_holdings
        }

        # Track normalized company_names in the new data
        new_company_names: set[str] = {h.company_name.strip().upper() for h in holdings}

        updated_count = 0
        inserted_count = 0

        for new_holding in holdings:
            normalized_company_name = new_holding.company_name.strip().upper()
            existing = existing_by_company_name.get(normalized_company_name)

            if existing:
                # Update existing holding using explicit UPDATE statement
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
                    )
                )
                await self.session.execute(stmt)
                updated_count += 1
            else:
                # Insert new holding with the correct user_broker_id
                new_holding.user_broker_id = metadata.user_broker_id
                self.session.add(new_holding)
                inserted_count += 1

        # Delete holdings that are not in the new list
        for company_name, existing in existing_by_company_name.items():
            if company_name not in new_company_names:
                await self.session.delete(existing)

        await self.session.flush()
        return updated_count, inserted_count

    async def upsert_holdings_by_user_broker_id(
        self,
        user_broker_id: UUID,
        holdings: list[EquityHolding],
    ) -> tuple[int, int, int]:
        """
        Upsert holdings for a given user_broker_id.

        - Updates existing holdings (matched by symbol)
        - Inserts new holdings
        - Deletes holdings that are not in the new list

        Args:
            user_broker_id: The user_broker_id (metadata PK)
            holdings: List of new EquityHolding objects

        Returns:
            Tuple of (updated_count, inserted_count, deleted_count)
        """
        if not holdings:
            return 0, 0, 0

        # Get existing holdings for this user_broker_id
        existing_holdings = await self.by_user_broker_id(user_broker_id)

        # Create a map of normalized symbol -> existing holding
        existing_by_symbol: dict[str, EquityHolding] = {
            h.symbol.strip().upper(): h for h in existing_holdings
        }

        # Track normalized symbols in the new data
        new_symbols: set[str] = {h.symbol.strip().upper() for h in holdings}

        updated_count = 0
        inserted_count = 0
        deleted_count = 0

        for new_holding in holdings:
            normalized_symbol = new_holding.symbol.strip().upper()
            existing = existing_by_symbol.get(normalized_symbol)

            if existing:
                # Update existing holding using explicit UPDATE statement
                stmt = (
                    update(EquityHolding)
                    .where(EquityHolding.id == existing.id)
                    .values(
                        company_name=new_holding.company_name,
                        sector=new_holding.sector,
                        qty_available=new_holding.qty_available,
                        qty_long_term=new_holding.qty_long_term,
                        qty_pledged_margin=new_holding.qty_pledged_margin,
                        avg_price=new_holding.avg_price,
                        prev_close_price=new_holding.prev_close_price,
                    )
                )
                await self.session.execute(stmt)
                updated_count += 1
            else:
                # Insert new holding with the correct user_broker_id
                new_holding.user_broker_id = user_broker_id
                self.session.add(new_holding)
                inserted_count += 1

        # Delete holdings that are not in the new list
        for symbol, existing in existing_by_symbol.items():
            if symbol not in new_symbols:
                await self.session.delete(existing)
                deleted_count += 1

        await self.session.flush()
        return updated_count, inserted_count, deleted_count

    async def update_metadata_timestamp(self, user_broker_id: UUID) -> None:
        """
        Update the updated_at timestamp for a metadata record.

        Args:
            user_broker_id: The user_broker_id (metadata PK)
        """
        stmt = (
            update(EquityHoldingMetadata)
            .where(EquityHoldingMetadata.user_broker_id == user_broker_id)
            .values(updated_at=func.now())
        )
        await self.session.execute(stmt)

    async def get_holding_by_symbol(
        self, user_broker_id: UUID, symbol: str
    ) -> Optional[EquityHolding]:
        """
        Get a specific holding by symbol for a user-broker pair.

        Args:
            user_broker_id: The user_broker_id (metadata PK)
            symbol: The trading symbol to search for

        Returns:
            EquityHolding object if found, None otherwise
        """
        result = await self.session.execute(
            select(EquityHolding).where(
                and_(
                    EquityHolding.user_broker_id == user_broker_id,
                    EquityHolding.symbol == symbol,
                )
            )
        )
        return result.scalar_one_or_none()

    async def create_sync_record(
        self, user_id: UUID, synced_count: int, updated_count: int
    ) -> HoldingSync:
        """
        Create a holding sync record.

        Args:
            user_id: The user ID
            synced_count: Number of holdings synced
            updated_count: Number of holdings updated

        Returns:
            The created HoldingSync object
        """
        sync = HoldingSync(
            user_id=user_id, synced_count=synced_count, updated_count=updated_count
        )
        self.session.add(sync)
        await self.session.flush()
        return sync

    async def get_most_recent_sync(self, user_id: UUID) -> Optional[HoldingSync]:
        """
        Get the most recent sync record for a user.

        Args:
            user_id: The user ID

        Returns:
            The most recent HoldingSync object if found, None otherwise
        """
        result = await self.session.execute(
            select(HoldingSync)
            .where(HoldingSync.user_id == user_id)
            .order_by(HoldingSync.synced_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()
