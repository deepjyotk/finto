"""Broker repository - data access for broker operations"""

from typing import Any
from uuid import UUID

from sqlalchemy import cast, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.types import String

from src.models.broker import Broker


class BrokerRepository:
    """Repository for Broker data access operations"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_broker_name_by_id(self, broker_id: UUID) -> str | None:
        result = await self.session.execute(
            select(cast(Broker.broker_name, String)).where(Broker.broker_id == broker_id)
        )
        return result.scalar_one_or_none()

    async def get_company_names_by_symbols(self, symbols: list[str]) -> dict[str, str]:
        result = await self.session.execute(
            text("SELECT symbol, company_name FROM in_equities WHERE symbol = ANY(:symbols)"),
            {"symbols": symbols},
        )
        return {row[0]: row[1] for row in result}

    async def get_symbols_by_isins(self, isins: list[str]) -> dict[str, str]:
        result = await self.session.execute(
            text("SELECT isin_number, symbol FROM in_equities WHERE isin_number = ANY(:isins)"),
            {"isins": isins},
        )
        return {row[0]: row[1] for row in result}

    async def get_all_brokers(self) -> list[dict[str, Any]]:
        """
        Get all available brokers.

        Returns:
            List of broker dictionaries with string values
        """
        # Cast enum columns to strings to avoid enum mismatch issues
        result = await self.session.execute(
            select(
                Broker.broker_id,
                cast(Broker.broker_name, String).label("broker_name"),
                cast(Broker.broker_type, String).label("broker_type"),
                cast(Broker.country, String).label("country"),
            )
        )

        brokers = []
        for row in result:
            brokers.append(
                {
                    "broker_id": row.broker_id,
                    "broker_name": row.broker_name,
                    "broker_type": row.broker_type,
                    "country": row.country,
                }
            )
        return brokers
