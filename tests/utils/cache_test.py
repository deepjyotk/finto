"""Unit tests for src/utils/cache.py.

Tests cover:
  - TableCache primitives (get/set/invalidate/clear, TTL expiry)
  - InEquitiesCache.get_or_fetch cache-aside behaviour
  - Key normalisation (case-insensitive, whitespace-stripped)
  - No DB call on cache hit; exactly one DB call on cache miss
  - None propagation when the DB returns no row
  - Module-level singleton is an InEquitiesCache instance
"""

from __future__ import annotations

import time
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio  # noqa: F401  (needed for asyncio mode)

from src.utils.cache import InEquitiesCache, TableCache, in_equities_cache


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

_SAMPLE_ROW: dict[str, Any] = {
    "id": uuid.uuid4(),
    "symbol": "RELIANCE",
    "company_name": "Reliance Industries Limited",
    "series": "EQ",
    "date_of_listing": date(1995, 11, 29),
    "paid_up_value": Decimal("10.0000"),
    "market_lot": 1,
    "isin_number": "INE002A01018",
    "face_value": Decimal("10.0000"),
    "created_at": datetime(2024, 1, 1, 0, 0, 0),
    "updated_at": datetime(2024, 1, 1, 0, 0, 0),
    "company_metadata": {"longName": "Reliance Industries Limited"},
}


def _make_session(row: dict | None = _SAMPLE_ROW) -> AsyncMock:
    """Return a mock AsyncSession whose execute() returns the given row."""
    mock_row = None
    if row is not None:
        mock_row = MagicMock()
        for k, v in row.items():
            setattr(mock_row, k, v)

    mock_result = MagicMock()
    mock_result.fetchone.return_value = mock_row

    session = AsyncMock()
    session.execute = AsyncMock(return_value=mock_result)
    return session


# ---------------------------------------------------------------------------
# Concrete subclass of TableCache for testing the base in isolation
# ---------------------------------------------------------------------------


class _StringCache(TableCache[str]):
    """Simple concrete TableCache that echoes the key as the DB value."""

    def __init__(self, ttl_seconds: float = 60.0, db_value: str | None = "db-result") -> None:
        super().__init__(ttl_seconds=ttl_seconds)
        self._db_value = db_value
        self.fetch_call_count = 0

    async def _fetch_from_db(self, key: str, session: Any) -> str | None:
        self.fetch_call_count += 1
        return self._db_value


# ---------------------------------------------------------------------------
# TableCache base — primitives
# ---------------------------------------------------------------------------


class TestTableCacheGet:
    def test_get_returns_none_when_empty(self) -> None:
        cache = _StringCache()
        assert cache.get("foo") is None

    def test_get_returns_value_after_set(self) -> None:
        cache = _StringCache()
        cache.set("foo", "bar")
        assert cache.get("foo") == "bar"

    def test_get_is_case_insensitive(self) -> None:
        cache = _StringCache()
        cache.set("foo", "bar")
        assert cache.get("FOO") == "bar"
        assert cache.get("Foo") == "bar"

    def test_get_strips_whitespace(self) -> None:
        cache = _StringCache()
        cache.set("  foo  ", "bar")
        assert cache.get("foo") == "bar"

    def test_get_returns_none_after_ttl_expires(self) -> None:
        cache = _StringCache(ttl_seconds=0.05)
        cache.set("foo", "bar")
        time.sleep(0.1)
        assert cache.get("foo") is None

    def test_get_does_not_return_none_before_ttl_expires(self) -> None:
        cache = _StringCache(ttl_seconds=60.0)
        cache.set("foo", "bar")
        assert cache.get("foo") == "bar"


class TestTableCacheInvalidateAndClear:
    def test_invalidate_removes_entry(self) -> None:
        cache = _StringCache()
        cache.set("foo", "bar")
        cache.invalidate("foo")
        assert cache.get("foo") is None

    def test_invalidate_is_noop_for_missing_key(self) -> None:
        cache = _StringCache()
        cache.invalidate("nonexistent")  # should not raise

    def test_clear_removes_all_entries(self) -> None:
        cache = _StringCache()
        cache.set("a", "1")
        cache.set("b", "2")
        cache.clear()
        assert cache.get("a") is None
        assert cache.get("b") is None

    def test_size_reflects_stored_entries(self) -> None:
        cache = _StringCache()
        assert cache.size == 0
        cache.set("a", "1")
        cache.set("b", "2")
        assert cache.size == 2
        cache.clear()
        assert cache.size == 0


# ---------------------------------------------------------------------------
# TableCache base — cache-aside (get_or_fetch)
# ---------------------------------------------------------------------------


class TestTableCacheGetOrFetch:
    @pytest.mark.asyncio
    async def test_cache_miss_calls_db_and_caches_result(self) -> None:
        cache = _StringCache(db_value="from-db")
        session = AsyncMock()

        result = await cache.get_or_fetch("key", session)

        assert result == "from-db"
        assert cache.fetch_call_count == 1
        assert cache.get("key") == "from-db"

    @pytest.mark.asyncio
    async def test_cache_hit_skips_db(self) -> None:
        cache = _StringCache(db_value="from-db")
        session = AsyncMock()
        cache.set("key", "cached-value")

        result = await cache.get_or_fetch("key", session)

        assert result == "cached-value"
        assert cache.fetch_call_count == 0

    @pytest.mark.asyncio
    async def test_second_call_uses_cache(self) -> None:
        cache = _StringCache(db_value="from-db")
        session = AsyncMock()

        await cache.get_or_fetch("key", session)
        await cache.get_or_fetch("key", session)

        assert cache.fetch_call_count == 1

    @pytest.mark.asyncio
    async def test_db_none_is_not_cached(self) -> None:
        cache = _StringCache(db_value=None)
        session = AsyncMock()

        result = await cache.get_or_fetch("missing", session)

        assert result is None
        assert cache.size == 0

    @pytest.mark.asyncio
    async def test_stale_entry_triggers_db_refetch(self) -> None:
        cache = _StringCache(ttl_seconds=0.05, db_value="fresh")
        session = AsyncMock()

        await cache.get_or_fetch("key", session)
        time.sleep(0.1)
        result = await cache.get_or_fetch("key", session)

        assert result == "fresh"
        assert cache.fetch_call_count == 2


# ---------------------------------------------------------------------------
# InEquitiesCache
# ---------------------------------------------------------------------------


class TestInEquitiesCacheInit:
    def test_ttl_is_one_day(self) -> None:
        cache = InEquitiesCache()
        assert cache._ttl == 86_400.0

    def test_starts_empty(self) -> None:
        cache = InEquitiesCache()
        assert cache.size == 0


class TestInEquitiesCacheNormalisation:
    def test_symbol_uppercased_on_set(self) -> None:
        cache = InEquitiesCache()
        cache.set("reliance", _SAMPLE_ROW)
        assert cache.get("RELIANCE") == _SAMPLE_ROW

    def test_symbol_stripped_on_lookup(self) -> None:
        cache = InEquitiesCache()
        cache.set("  RELIANCE  ", _SAMPLE_ROW)
        assert cache.get("reliance") == _SAMPLE_ROW


class TestInEquitiesCacheGetOrFetch:
    @pytest.mark.asyncio
    async def test_cache_miss_fetches_full_row(self) -> None:
        cache = InEquitiesCache()
        session = _make_session(_SAMPLE_ROW)

        result = await cache.get_or_fetch("RELIANCE", session)

        assert result is not None
        assert result["symbol"] == "RELIANCE"
        assert result["company_name"] == "Reliance Industries Limited"
        assert result["isin_number"] == "INE002A01018"
        assert result["company_metadata"] == {"longName": "Reliance Industries Limited"}
        session.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_cache_hit_returns_cached_row_without_db(self) -> None:
        cache = InEquitiesCache()
        cache.set("RELIANCE", _SAMPLE_ROW)
        session = _make_session(_SAMPLE_ROW)

        result = await cache.get_or_fetch("RELIANCE", session)

        assert result == _SAMPLE_ROW
        session.execute.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_lowercase_symbol_resolves_to_cached_entry(self) -> None:
        cache = InEquitiesCache()
        cache.set("RELIANCE", _SAMPLE_ROW)
        session = _make_session(_SAMPLE_ROW)

        result = await cache.get_or_fetch("reliance", session)

        assert result == _SAMPLE_ROW
        session.execute.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_db_returns_none_propagates_correctly(self) -> None:
        cache = InEquitiesCache()
        session = _make_session(row=None)

        result = await cache.get_or_fetch("UNKNOWN", session)

        assert result is None
        assert cache.size == 0

    @pytest.mark.asyncio
    async def test_multiple_symbols_cached_independently(self) -> None:
        reliance_row = {**_SAMPLE_ROW, "symbol": "RELIANCE"}
        tcs_row = {**_SAMPLE_ROW, "symbol": "TCS", "isin_number": "INE467B01029"}

        cache = InEquitiesCache()

        session_rel = _make_session(reliance_row)
        session_tcs = _make_session(tcs_row)

        await cache.get_or_fetch("RELIANCE", session_rel)
        await cache.get_or_fetch("TCS", session_tcs)

        assert cache.get("RELIANCE")["symbol"] == "RELIANCE"  # type: ignore[index]
        assert cache.get("TCS")["symbol"] == "TCS"  # type: ignore[index]

    @pytest.mark.asyncio
    async def test_invalidate_forces_db_refetch(self) -> None:
        cache = InEquitiesCache()
        session = _make_session(_SAMPLE_ROW)

        await cache.get_or_fetch("RELIANCE", session)
        cache.invalidate("RELIANCE")
        await cache.get_or_fetch("RELIANCE", session)

        assert session.execute.await_count == 2

    @pytest.mark.asyncio
    async def test_result_is_populated_in_cache_after_fetch(self) -> None:
        cache = InEquitiesCache()
        session = _make_session(_SAMPLE_ROW)

        assert cache.get("RELIANCE") is None
        await cache.get_or_fetch("RELIANCE", session)
        assert cache.get("RELIANCE") is not None


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------


class TestModuleLevelSingleton:
    def test_singleton_is_in_equities_cache_instance(self) -> None:
        assert isinstance(in_equities_cache, InEquitiesCache)

    def test_singleton_is_same_object_on_repeated_import(self) -> None:
        from src.utils.cache import in_equities_cache as second_import

        assert in_equities_cache is second_import
