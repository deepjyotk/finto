"""Pending registration repository - data access for OTP verification during registration"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.pending_registration import PendingRegistration


class PendingRegistrationRepository:
    """Repository for pending registration data access operations"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def by_email(self, email: str) -> Optional[PendingRegistration]:
        """Find pending registration by email."""
        result = await self.session.execute(
            select(PendingRegistration).where(PendingRegistration.email == email)
        )
        return result.scalar_one_or_none()

    async def add(
        self,
        id: UUID,
        email: str,
        username: str,
        full_name: str,
        password_hash: str,
        otp_hash: str,
        expires_at: datetime,
    ) -> PendingRegistration:
        """Add a new pending registration."""
        pending = PendingRegistration(
            id=id,
            email=email,
            username=username,
            full_name=full_name,
            password_hash=password_hash,
            otp_hash=otp_hash,
            expires_at=expires_at,
            attempts=0,
        )
        self.session.add(pending)
        await self.session.flush()
        return pending

    async def increment_attempts(self, pending: PendingRegistration) -> None:
        """Increment the OTP verification attempts."""
        pending.attempts += 1
        await self.session.flush()

    async def delete_by_email(self, email: str) -> None:
        """Delete pending registration by email."""
        await self.session.execute(
            delete(PendingRegistration).where(PendingRegistration.email == email)
        )
        await self.session.flush()

    async def delete_expired(self, before: datetime) -> int:
        """Delete all expired pending registrations. Returns count of deleted rows."""
        result = await self.session.execute(
            delete(PendingRegistration).where(PendingRegistration.expires_at < before)
        )
        await self.session.flush()
        return result.rowcount
