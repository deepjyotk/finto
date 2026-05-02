"""In-service cache utilities (cache-aside pattern).

Hierarchy
---------
TableCache[T]          — generic TTL-aware in-memory base
  └─ InEquitiesCache   — caches in_equities rows keyed by symbol (TTL = 1 day)

Usage
-----
    from src.utils.cache import in_equities_cache

    row = await in_equities_cache.get_or_fetch("RELIANCE", session)
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

T = TypeVar("T")

_ONE_DAY_SECONDS: float = 86_400.0


# ---------------------------------------------------------------------------
# Generic base
# ---------------------------------------------------------------------------


class TableCache(ABC, Generic[T]):
    """TTL-aware in-memory cache with cache-aside semantics.

    Subclasses implement :meth:`_fetch_from_db` to define the DB fallback.
    All keys are normalised to lowercase before storage so that lookups are
    case-insensitive by default; override :meth:`_normalise_key` to change
    this behaviour.

    Parameters
    ----------
    ttl_seconds:
        How long (in seconds) a cached entry is considered fresh.
    """

    def __init__(self, ttl_seconds: float = _ONE_DAY_SECONDS) -> None:
        self._ttl = ttl_seconds
        # {normalised_key: (value, expires_at_monotonic)}
        self._store: dict[str, tuple[T, float]] = {}

    # ── public cache primitives ───────────────────────────────────────────

    def get(self, key: str) -> T | None:
        """Return the cached value for *key*, or ``None`` if absent / expired."""
        nk = self._normalise_key(key)
        entry = self._store.get(nk)
        if entry is None:
            return None
        value, expires_at = entry
        if time.monotonic() >= expires_at:
            del self._store[nk]
            return None
        return value

    def set(self, key: str, value: T) -> None:
        """Store *value* under *key* with the configured TTL."""
        nk = self._normalise_key(key)
        self._store[nk] = (value, time.monotonic() + self._ttl)

    def invalidate(self, key: str) -> None:
        """Remove a single entry from the cache (no-op if not present)."""
        self._store.pop(self._normalise_key(key), None)

    def clear(self) -> None:
        """Evict all entries."""
        self._store.clear()

    @property
    def size(self) -> int:
        """Number of entries currently in the cache (may include stale ones)."""
        return len(self._store)

    # ── cache-aside ───────────────────────────────────────────────────────

    async def get_or_fetch(self, key: str, session: AsyncSession) -> T | None:
        """Cache-aside lookup.

        1. Return immediately if a fresh entry is present.
        2. Otherwise call :meth:`_fetch_from_db`, populate the cache, and
           return the result (``None`` if the DB returned nothing).
        """
        cached = self.get(key)
        if cached is not None:
            return cached

        value = await self._fetch_from_db(key, session)
        if value is not None:
            self.set(key, value)
        return value

    # ── extension points ──────────────────────────────────────────────────

    @abstractmethod
    async def _fetch_from_db(self, key: str, session: AsyncSession) -> T | None:
        """Fetch the value for *key* from the database.

        Return ``None`` if no matching row exists.
        """

    def _normalise_key(self, key: str) -> str:
        """Normalise a raw lookup key before storage/retrieval.

        Default: strip whitespace and uppercase (suitable for stock symbols).
        Override in subclasses if a different normalisation is required.
        """
        return key.strip().upper()


# ---------------------------------------------------------------------------
# in_equities cache
# ---------------------------------------------------------------------------


class InEquitiesCache(TableCache[dict]):
    """Cache for the ``in_equities`` table, keyed by stock symbol.

    Each entry is the full equity row returned as a plain ``dict``::

        {
            "id":               <UUID>,
            "symbol":           "RELIANCE",
            "company_name":     "Reliance Industries Limited",
            "series":           "EQ",
            "date_of_listing":  <date | None>,
            "paid_up_value":    <Decimal | None>,
            "market_lot":       <int | None>,
            "isin_number":      "INE002A01018",
            "face_value":       <Decimal | None>,
            "created_at":       <datetime>,
            "updated_at":       <datetime>,
            "company_metadata": <dict | None>,
        }

    TTL is one day (86 400 seconds).
    """

    def __init__(self) -> None:
        super().__init__(ttl_seconds=_ONE_DAY_SECONDS)

    async def get_company_info_batch(
        self,
        symbols: list[str],
        session: AsyncSession,
    ) -> list[dict[str, str]]:
        """Return ``[{"symbol_name": ..., "company_name": ...}]`` for each symbol.

        Uses the cache-aside strategy: a cache hit per symbol avoids a DB round-trip.
        Symbols with no matching ``in_equities`` row are silently omitted.

        Parameters
        ----------
        symbols:
            List of raw ticker symbols (case-insensitive, whitespace-stripped).
        session:
            Active async SQLAlchemy session used only on cache misses.
        """
        result: list[dict[str, str]] = []
        for symbol in symbols:
            row = await self.get_or_fetch(symbol, session)
            if row is not None:
                result.append(
                    {
                        "symbol_name": row["symbol"],
                        "company_name": row["company_name"],
                    }
                )
        return result

    async def _fetch_from_db(self, key: str, session: AsyncSession) -> dict | None:
        """Query ``in_equities`` for the normalised symbol *key*."""
        symbol = self._normalise_key(key)
        result = await session.execute(
            text(
                """
                SELECT
                    id,
                    symbol,
                    company_name,
                    series,
                    date_of_listing,
                    paid_up_value,
                    market_lot,
                    isin_number,
                    face_value,
                    created_at,
                    updated_at,
                    company_metadata
                FROM   in_equities
                WHERE  symbol = :symbol
                LIMIT  1
                """
            ),
            {"symbol": symbol},
        )
        row = result.fetchone()
        if row is None:
            return None
        return {
            "id": row.id,
            "symbol": row.symbol,
            "company_name": row.company_name,
            "series": row.series,
            "date_of_listing": row.date_of_listing,
            "paid_up_value": row.paid_up_value,
            "market_lot": row.market_lot,
            "isin_number": row.isin_number,
            "face_value": row.face_value,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
            "company_metadata": row.company_metadata,
        }


# ---------------------------------------------------------------------------
# Module-level singleton — import and use directly
# ---------------------------------------------------------------------------

in_equities_cache: InEquitiesCache = InEquitiesCache()
