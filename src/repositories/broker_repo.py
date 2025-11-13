"""Broker repository - data access for broker operations"""

from typing import Any

from sqlalchemy import cast, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.types import String

from src.models.broker import Broker


class BrokerRepository:
    """Repository for Broker data access operations"""

    def __init__(self, session: AsyncSession):
        self.session = session

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
            brokers.append({
                "broker_id": row.broker_id,
                "broker_name": row.broker_name,
                "broker_type": row.broker_type,
                "country": row.country,
            })
        return brokers

