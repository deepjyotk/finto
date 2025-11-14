"""WhatsApp repository - pure class for data access, no FastAPI imports"""

from typing import Optional
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.whatsapp_cache import WhatsAppCache
from src.models.whatsapp_metadata import WhatsAppMetadata


class WhatsAppRepository:
    """Repository for WhatsApp Cache and Metadata data access operations"""

    def __init__(self, session: AsyncSession):
        self.session = session

    # WhatsAppCache methods
    async def by_temporary_code(self, temporary_code: str) -> Optional[WhatsAppCache]:
        """
        Find WhatsApp cache entry by temporary code.

        Args:
            temporary_code: The temporary code to search for

        Returns:
            WhatsAppCache object if found, None otherwise
        """
        result = await self.session.execute(
            select(WhatsAppCache).where(WhatsAppCache.temporary_code == temporary_code)
        )
        return result.scalar_one_or_none()

    async def add(self, user_id: UUID, temporary_code: str) -> WhatsAppCache:
        """
        Add a new WhatsApp cache entry to the database.

        Args:
            user_id: UUID of the user
            temporary_code: Temporary code for WhatsApp connection

        Returns:
            The created WhatsAppCache object
        """
        cache_entry = WhatsAppCache(user_id=user_id, temporary_code=temporary_code)
        self.session.add(cache_entry)
        await self.session.flush()  # Get the entry with auto-generated fields
        return cache_entry

    async def delete_cache_entry(self, cache_id: UUID) -> None:
        """
        Delete a WhatsApp cache entry by ID.

        Args:
            cache_id: UUID of the cache entry to delete
        """
        await self.session.execute(delete(WhatsAppCache).where(WhatsAppCache.id == cache_id))

    # WhatsAppMetadata methods
    async def get_metadata_by_e164(self, user_e164: str) -> Optional[WhatsAppMetadata]:
        """
        Find WhatsApp metadata by user E.164 phone number.

        Args:
            user_e164: E.164 formatted phone number

        Returns:
            WhatsAppMetadata object if found, None otherwise
        """
        result = await self.session.execute(
            select(WhatsAppMetadata).where(WhatsAppMetadata.user_e164 == user_e164)
        )
        return result.scalar_one_or_none()

    async def get_metadata_by_user_id(self, user_id: UUID) -> Optional[WhatsAppMetadata]:
        """
        Find WhatsApp metadata by user ID.

        Args:
            user_id: UUID of the user

        Returns:
            WhatsAppMetadata object if found, None otherwise
        """
        result = await self.session.execute(
            select(WhatsAppMetadata).where(WhatsAppMetadata.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_metadata_by_id(self, metadata_id: UUID) -> Optional[WhatsAppMetadata]:
        """
        Find WhatsApp metadata by ID.

        Args:
            metadata_id: UUID of the metadata entry

        Returns:
            WhatsAppMetadata object if found, None otherwise
        """
        result = await self.session.execute(
            select(WhatsAppMetadata).where(WhatsAppMetadata.id == metadata_id)
        )
        return result.scalar_one_or_none()

    async def create_metadata(self, user_id: UUID, user_e164: str) -> WhatsAppMetadata:
        """
        Create a new WhatsApp metadata entry.

        Args:
            user_id: UUID of the user
            user_e164: E.164 formatted phone number

        Returns:
            The created WhatsAppMetadata object
        """
        metadata = WhatsAppMetadata(user_id=user_id, user_e164=user_e164)
        self.session.add(metadata)
        await self.session.flush()
        return metadata

    async def delete_metadata_by_id(self, metadata_id: UUID) -> None:
        """
        Delete a WhatsApp metadata entry by ID.

        Args:
            metadata_id: UUID of the metadata entry to delete
        """
        await self.session.execute(
            delete(WhatsAppMetadata).where(WhatsAppMetadata.id == metadata_id)
        )
