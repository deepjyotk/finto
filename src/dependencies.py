"""Dependency injection providers - thin wiring layer only"""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.db import get_session
from src.core.settings import settings
from src.nodes.portfolio import PortfolioNode
from src.repositories.user_repo import UserRepository
from src.services.auth import AuthService
from src.services.chat import ChatService


def _get_auth_repository(session: Annotated[AsyncSession, Depends(get_session)]) -> UserRepository:
    """
    Provide UserRepository instance.

    Returns:
        Configured UserRepository instance
    """
    return UserRepository(session)


def get_auth_service(
    repo: Annotated[UserRepository, Depends(_get_auth_repository)],
) -> AuthService:
    """
    Provide AuthService with its dependencies.

    This is the only place where we wire together:
    Session → Repository → Service

    Args:
        session: Database session from get_session dependency

    Returns:
        Configured AuthService instance
    """
    return AuthService(repo=repo, secret_key=settings.secret_key, algorithm=settings.algorithm)


def get_chat_service() -> ChatService:
    """
    Provide ChatService instance.
    Returns:
        Configured ChatService instance
    """
    return ChatService()
