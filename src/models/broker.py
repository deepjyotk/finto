"""Broker model for SQLAlchemy"""

import enum
from uuid import UUID

from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class BrokerName(str, enum.Enum):
    """Broker name options"""

    ANGEL_ONE = "AngelOne"
    ZERODHA = "Zerodha"
    GROW = "Grow"


class BrokerType(str, enum.Enum):
    """Broker type options"""

    EQUITY = "Equity"
    CRYPTO = "Crypto"


class Country(str, enum.Enum):
    """Country options"""

    INDIA = "India"
    US = "US"


class Broker(Base):
    """Broker model for brokers table"""

    __tablename__ = "brokers"

    broker_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default="gen_random_uuid()"
    )
    broker_name: Mapped[BrokerName] = mapped_column(
        SQLEnum(BrokerName, name="broker_name_enum"), nullable=False
    )
    broker_type: Mapped[BrokerType] = mapped_column(
        SQLEnum(BrokerType, name="broker_type_enum"), nullable=False
    )
    country: Mapped[Country] = mapped_column(
        SQLEnum(Country, name="country_enum"), nullable=False
    )

    def __repr__(self) -> str:
        return (
            f"<Broker(broker_id={self.broker_id}, "
            f"name={self.broker_name.value}, "
            f"type={self.broker_type.value})>"
        )
