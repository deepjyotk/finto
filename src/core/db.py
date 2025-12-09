"""Database session management with async SQLAlchemy 2.x"""

import ssl
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.core.settings import settings


def _ensure_async_driver(url: str) -> str:
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


# Create SSL context that accepts self-signed certificates
# For production, use proper certificate verification
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

# Create async engine
engine = create_async_engine(
    _ensure_async_driver(settings.database_url),
    pool_pre_ping=True,
    echo=False,  # Set to True for SQL query logging
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,  # avoid exceeding session-mode pool limits
    pool_timeout=settings.db_pool_timeout,
    connect_args={"ssl": ssl_context},
)

# Create session factory
SessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_session() -> AsyncIterator[AsyncSession]:
    """
    Dependency that provides a database session.

    The session is automatically rolled back on exit if not committed.
    This ensures clean state even if exceptions occur.
    """
    async with SessionLocal() as session:
        try:
            yield session
        finally:
            # Rollback any uncommitted work on exit
            await session.rollback()
