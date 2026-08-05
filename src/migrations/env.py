import os
import re
from logging.config import fileConfig

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import create_async_engine

# Import SQLAlchemy metadata for autogenerate
from src.models.base import Base

# Import all models here to ensure they're registered with Base
from src.models.broker import Broker  # noqa: F401
from src.models.chat_session import ChatSession  # noqa: F401

# src.models.demo_us_stock is intentionally not imported: those tables live in
# TimescaleDB (see finto/timescale/schema.sql) and must stay out of this
# metadata, otherwise autogenerate would recreate them in Supabase.
from src.models.equity_holding import EquityHolding  # noqa: F401
from src.models.price_bar_1d import PriceBar1d  # noqa: F401
from src.models.user import User  # noqa: F401
from src.models.whatsapp_cache import WhatsAppCache  # noqa: F401
from src.models.whatsapp_metadata import WhatsAppMetadata  # noqa: F401

load_dotenv()
target_metadata = Base.metadata

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Read DATABASE_URL from env
DATABASE_URL = os.getenv("DATABASE_URL", "")

# Debug: Print connection info (hide password)
if DATABASE_URL:
    safe_url = DATABASE_URL[:30] + "***" + DATABASE_URL[-20:] if len(DATABASE_URL) > 50 else "***"
    print(f"🔗 Connecting to: {safe_url}")
else:
    print("⚠️  WARNING: DATABASE_URL not set!")

# Convert postgresql:// to postgresql+asyncpg:// for async support
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

# Remove sslmode from URL as asyncpg doesn't accept it as URL parameter
# (For production, configure SSL via connect_args in create_async_engine)
if DATABASE_URL and "sslmode=" in DATABASE_URL:
    DATABASE_URL = re.sub(r"[?&]sslmode=[^&]*", "", DATABASE_URL)
    DATABASE_URL = DATABASE_URL.rstrip("?&")


def run_migrations_offline():
    """Offline mode: emits SQL to script output."""
    url = DATABASE_URL or config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        version_table_schema="public",  # Supabase default
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online():
    """Online mode: runs migrations against DB (asyncpg)."""
    url = DATABASE_URL or config.get_main_option("sqlalchemy.url")
    connectable = create_async_engine(url, poolclass=pool.NullPool)

    async with connectable.connect() as connection:
        await connection.run_sync(
            lambda sync_conn: context.configure(
                connection=sync_conn,
                target_metadata=target_metadata,
                version_table_schema="public",
                compare_type=True,
                compare_server_default=True,
            )
        )

        async with connection.begin():
            await connection.run_sync(lambda _: context.run_migrations())

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    import asyncio

    asyncio.run(run_migrations_online())
