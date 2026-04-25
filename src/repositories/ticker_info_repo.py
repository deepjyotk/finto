"""Repository: yfinance company snapshot from in_equities.company_metadata (JSONB)."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class TickerInfoRepo:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def get_equity(self, symbol: str) -> dict | None:
        """Return the canonical equity row for a user-provided symbol."""
        result = await self._s.execute(
            text(
                """
                SELECT id, symbol
                FROM   in_equities
                WHERE  symbol = split_part(upper(:symbol), '.', 1)
                LIMIT  1
                """
            ),
            {"symbol": symbol.strip()},
        )
        row = result.fetchone()
        if row is None:
            return None
        return {"id": row.id, "symbol": row.symbol}

    async def get_info(self, symbol_ns: str) -> dict | None:
        """
        Return the parsed info JSON object for a symbol, or None if not found.

        The `data` column is JSONB — asyncpg returns it already as a dict.
        """
        result = await self._s.execute(
            text(
                """
                SELECT company_metadata AS data
                FROM   in_equities
                WHERE  symbol = split_part(:symbol_ns, '.', 1)
                LIMIT  1
                """
            ),
            {"symbol_ns": symbol_ns},
        )
        row = result.fetchone()
        if row is None:
            return None
        return row.data or {}
