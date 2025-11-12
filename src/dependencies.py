"""Dependency injection providers - thin wiring layer only"""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.db import get_session
from src.core.settings import settings
from src.nodes.portfolio import PortfolioNode
from src.repositories.holdings_repo import HoldingsRepository
from src.repositories.user_repo import UserRepository
from src.services.auth import AuthService
from src.services.broker import BrokerService
from src.services.chat import ChatService
from src.services.holdings import HoldingsService


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


def _get_holdings_repository(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> HoldingsRepository:
    """
    Provide HoldingsRepository instance.

    Returns:
        Configured HoldingsRepository instance
    """
    return HoldingsRepository(session)


def get_holdings_service(
    repo: Annotated[HoldingsRepository, Depends(_get_holdings_repository)],
) -> HoldingsService:
    """
    Provide HoldingsService with its dependencies.

    This wires together:
    Session → Repository → Service

    Args:
        repo: HoldingsRepository from _get_holdings_repository dependency

    Returns:
        Configured HoldingsService instance
    """
    return HoldingsService(repo=repo)


def get_chat_service() -> ChatService:
    """
    Provide ChatService instance.
    Returns:
        Configured ChatService instance
    """
    return ChatService()


def get_broker_service() -> BrokerService:
    """
    Provide BrokerService instance.

    Returns:
        Configured BrokerService instance
    """
    return BrokerService()
