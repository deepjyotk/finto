"""User repository - pure class for data access, no FastAPI imports"""

from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.user import User


class UserRepository:
    """Repository for User data access operations"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def by_username(self, username: str) -> Optional[User]:
        """
        Find user by username.

        Args:
            username: The username to search for

        Returns:
            User object if found, None otherwise
        """
        result = await self.session.execute(select(User).where(User.username == username))
        return result.scalar_one_or_none()

    async def by_email(self, email: str) -> Optional[User]:
        """
        Find user by email.

        Args:
            email: The email to search for

        Returns:
            User object if found, None otherwise
        """
        result = await self.session.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def by_id(self, user_id: UUID) -> Optional[User]:
        """
        Find user by ID.

        Args:
            user_id: The user ID to search for

        Returns:
            User object if found, None otherwise
        """
        result = await self.session.execute(select(User).where(User.user_id == user_id))
        return result.scalar_one_or_none()

    async def add(
        self,
        user_id: UUID,
        username: str,
        email: str,
        full_name: str,
        password_hash: str,
    ) -> User:
        """
        Add a new user to the database.

        Args:
            user_id: UUID for the new user
            username: Username
            email: Email address
            full_name: User's full name
            password_hash: Hashed password

        Returns:
            The created User object
        """
        user = User(
            user_id=user_id,
            username=username,
            email=email,
            full_name=full_name,
            password_hash=password_hash,
        )
        self.session.add(user)
        await self.session.flush()  # Get the user with auto-generated fields
        return user
