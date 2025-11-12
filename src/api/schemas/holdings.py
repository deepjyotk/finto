"""Holdings request and response schemas"""

from decimal import Decimal
from uuid import UUID

from fastapi import UploadFile
from pydantic import BaseModel, Field


class HoldingsRequestSchema(BaseModel):
    """Schema for creating a new equity holding"""

    broker_id: UUID = Field(
        ..., description="ID of the broker", example="123e4567-e89b-12d3-a456-426614174000"
    )
    symbol: str = Field(..., description="Trading symbol", example="RELIANCE")
    isin: str = Field(..., description="ISIN code", example="INE002A01018")
    sector: str | None = Field(None, description="Sector of the equity", example="Energy")

    # Quantities
    qty_available: int = Field(default=0, description="Available quantity", example=100)
    qty_discrepant: int = Field(default=0, description="Discrepant quantity", example=0)
    qty_long_term: int = Field(default=0, description="Long term quantity", example=50)
    qty_pledged_margin: int = Field(default=0, description="Quantity pledged for margin", example=0)
    qty_pledged_loan: int = Field(default=0, description="Quantity pledged for loan", example=0)

    # Prices
    avg_price: Decimal = Field(..., description="Average purchase price", example=2450.75)
    prev_close_price: Decimal = Field(..., description="Previous closing price", example=2500.00)

    # PnL
    unrealized_pnl: Decimal = Field(..., description="Unrealized profit/loss", example=4925.00)
    unrealized_pnl_pct: Decimal = Field(..., description="Unrealized PnL percentage", example=2.01)

    model_config = {
        "json_schema_extra": {
            "example": {
                "broker_id": "123e4567-e89b-12d3-a456-426614174000",
                "symbol": "RELIANCE",
                "isin": "INE002A01018",
                "sector": "Energy",
                "qty_available": 100,
                "qty_discrepant": 0,
                "qty_long_term": 50,
                "qty_pledged_margin": 0,
                "qty_pledged_loan": 0,
                "avg_price": 2450.75,
                "prev_close_price": 2500.00,
                "unrealized_pnl": 4925.00,
                "unrealized_pnl_pct": 2.01,
            }
        }
    }


class HoldingsResponseSchema(BaseModel):
    """Schema for equity holding response"""

    id: UUID = Field(..., description="Unique holding identifier")
    user_id: UUID = Field(..., description="User identifier")
    broker_id: UUID = Field(..., description="Broker identifier")
    symbol: str = Field(..., description="Trading symbol")
    isin: str = Field(..., description="ISIN code")
    sector: str | None = Field(None, description="Sector of the equity")

    qty_available: int = Field(..., description="Available quantity")
    qty_discrepant: int = Field(..., description="Discrepant quantity")
    qty_long_term: int = Field(..., description="Long term quantity")
    qty_pledged_margin: int = Field(..., description="Quantity pledged for margin")
    qty_pledged_loan: int = Field(..., description="Quantity pledged for loan")

    avg_price: Decimal = Field(..., description="Average purchase price")
    prev_close_price: Decimal = Field(..., description="Previous closing price")

    unrealized_pnl: Decimal = Field(..., description="Unrealized profit/loss")
    unrealized_pnl_pct: Decimal = Field(..., description="Unrealized PnL percentage")

    model_config = {
        "from_attributes": True,
    }


class BulkHoldingsUploadResponse(BaseModel):
    """Schema for bulk holdings upload response"""

    success: bool = Field(..., description="Whether the upload was successful")
    records_processed: int = Field(..., description="Number of records processed")
    message: str = Field(..., description="Response message")
