from decimal import Decimal
from typing import Any, Optional

from pydantic import BaseModel, Field


class AgentMessage(BaseModel):
    role: str
    content: str
    metadata: Optional[Any] = None


class EquityHoldingSchema(BaseModel):
    """DTO for EquityHolding table"""

    symbol: str = Field(..., description="Trading symbol")
    sector: Optional[str] = Field(None, description="Sector of the equity")

    # Quantities
    qty_available: int = Field(..., description="Available quantity")

    # Prices
    avg_price: Decimal = Field(..., description="Average purchase price")

    model_config = {
        "from_attributes": True,
    }

    @staticmethod
    def get_supported_columns() -> list[str]:
        return ["symbol", "company_name", "sector", "qty_available", "avg_price"]

    @staticmethod
    def get_holdings_schema() -> str:
        """Returns a string representation of column names and their descriptions"""
        schema_list = []
        for field_name, field_info in EquityHoldingSchema.model_fields.items():
            description = field_info.description or ""
            schema_list.append({field_name: description})
        return str(schema_list)
