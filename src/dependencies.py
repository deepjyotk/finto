"""Dependency injection providers - thin wiring layer only"""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.db import get_session
from src.core.settings import settings, tavily_settings
from src.nodes.computation import ComputationNode
from src.repositories.user_repo import UserRepository
from src.services.auth import AuthService
from src.services.chat import ChatService
from src.tools.tavily_web_search import TavilySearchTool


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


def _get_computation_node() -> ComputationNode:
    """
    Provide ComputationNode instance.

    Returns:
        Configured ComputationNode instance
    """
    return ComputationNode()


def get_chat_service(
    computation_node: Annotated[ComputationNode, Depends(_get_computation_node)],
) -> ChatService:
    """
    Provide ChatService with its dependencies.

    This is the only place where we wire together:
    ComputationNode → ChatService

    Args:
        computation_node: ComputationNode instance from _get_computation_node dependency

    Returns:
        Configured ChatService instance
    """
    return ChatService(computation_node=computation_node)


def get_tavily_search_tool() -> TavilySearchTool:
    """
    Provide TavilySearchTool with its dependencies.

    This is the only place where we wire together:
    TavilySettings → TavilySearchTool

    Returns:
        Configured TavilySearchTool instance
    """
    return TavilySearchTool(settings=tavily_settings)
