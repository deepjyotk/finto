"""Database session management with async SQLAlchemy 2.x"""

from typing import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.core.settings import settings


def _ensure_async_driver(url: str) -> str:
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


# Create async engine
engine = create_async_engine(
    _ensure_async_driver(settings.database_url),
    pool_pre_ping=True,
    echo=False,  # Set to True for SQL query logging
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
