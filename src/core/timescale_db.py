"""Session management for the TimescaleDB instance behind the US stocks demo.

Deliberately separate from ``src.core.db``: that engine points at Supabase and
is configured for a pooler behind TLS, while this one talks to a local
TimescaleDB container over plaintext. Keeping two engines means the demo can be
down without affecting any other feature — nothing outside
``src.services.demo_us_stock`` uses this module.
"""

from typing import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.core.settings import settings


def _ensure_async_driver(url: str) -> str:
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+asyncpg://", 1)
    return url


# The demo issues a handful of small queries per page load, so a large pool
# would only hold idle connections open against the container.
timescale_engine = create_async_engine(
    _ensure_async_driver(settings.timescale_database_url),
    pool_pre_ping=True,
    echo=False,
    pool_size=5,
    max_overflow=5,
    pool_timeout=10,
)

TimescaleSessionLocal = async_sessionmaker(
    timescale_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_timescale_session() -> AsyncIterator[AsyncSession]:
    """Dependency providing a TimescaleDB session, rolled back if not committed."""
    async with TimescaleSessionLocal() as session:
        try:
            yield session
        finally:
            await session.rollback()
