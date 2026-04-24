"""Repository: ticker info from f_ticker_info (JSONB schema)."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class TickerInfoRepo:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def get_info(self, symbol_ns: str) -> dict | None:
        """
        Return the parsed info JSON object for a symbol, or None if not found.

        The `data` column is JSONB — asyncpg returns it already as a dict.
        """
        result = await self._s.execute(
            text(
                """
                SELECT data
                FROM   f_ticker_info
                WHERE  symbol_ns = :symbol_ns
                LIMIT  1
                """
            ),
            {"symbol_ns": symbol_ns},
        )
        row = result.fetchone()
        if row is None:
            return None
        return row.data or {}
