"""Declarative base for models stored in TimescaleDB.

Separate from ``src.models.base.Base`` so Alembic — which autogenerates against
the Supabase metadata — never sees these tables and never tries to create or
drop them. The TimescaleDB schema is owned by ``finto/timescale/schema.sql``.
"""

from sqlalchemy.orm import DeclarativeBase


class TimescaleBase(DeclarativeBase):
    """Base class for models that live in the TimescaleDB instance."""
