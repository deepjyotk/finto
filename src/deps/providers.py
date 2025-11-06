"""Dependency injection providers - thin wiring layer only"""
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.db import get_session
from src.core.settings import settings
from src.repositories.user_repo import UserRepository
from src.services.auth_service import AuthService


def get_auth_service(
    session: Annotated[AsyncSession, Depends(get_session)]
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
    repo = UserRepository(session)
    return AuthService(
        repo=repo,
        secret_key=settings.secret_key,
        algorithm=settings.algorithm
    )

