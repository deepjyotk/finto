"""Holdings request and response schemas"""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class HoldingsRequestSchema(BaseModel):
    """Schema for creating a new equity holding"""

    broker_id: UUID = Field(
        ...,
        description="ID of the broker",
        example="123e4567-e89b-12d3-a456-426614174000",
    )
    symbol: str = Field(..., description="Trading symbol", example="RELIANCE")
    company_name: str = Field(
        ..., description="Company name", example="Reliance Industries Limited"
    )
    sector: str | None = Field(None, description="Sector of the equity", example="Energy")

    # Quantities
    qty_available: int = Field(default=0, description="Available quantity", example=100)
    qty_long_term: int = Field(default=0, description="Long term quantity", example=50)
    qty_pledged_margin: int = Field(default=0, description="Quantity pledged for margin", example=0)

    # Prices
    avg_price: Decimal = Field(..., description="Average purchase price", example=2450.75)
    prev_close_price: Decimal = Field(..., description="Previous closing price", example=2500.00)

    model_config = {
        "json_schema_extra": {
            "example": {
                "broker_id": "123e4567-e89b-12d3-a456-426614174000",
                "symbol": "RELIANCE",
                "company_name": "Reliance Industries Limited",
                "sector": "Energy",
                "qty_available": 100,
                "qty_long_term": 50,
                "qty_pledged_margin": 0,
                "avg_price": 2450.75,
                "prev_close_price": 2500.00,
            }
        }
    }


class HoldingsResponseSchema(BaseModel):
    """Schema for equity holding response"""

    id: UUID = Field(..., description="Unique holding identifier")
    user_id: UUID = Field(..., description="User identifier")
    broker_id: UUID = Field(..., description="Broker identifier")
    user_broker_id: UUID = Field(..., description="User-broker metadata identifier")
    symbol: str = Field(..., description="Trading symbol")
    company_name: str = Field(..., description="Company name")
    sector: str | None = Field(None, description="Sector of the equity")

    qty_available: int = Field(..., description="Available quantity")
    qty_long_term: int = Field(..., description="Long term quantity")
    qty_pledged_margin: int = Field(..., description="Quantity pledged for margin")

    avg_price: Decimal = Field(..., description="Average purchase price")
    prev_close_price: Decimal = Field(..., description="Previous closing price")

    model_config = {
        "from_attributes": True,
    }


class FileMetadata(BaseModel):
    """Schema for file metadata"""

    is_password_protected: bool = Field(
        default=False, description="Whether the file is password-protected"
    )


class BulkHoldingsUploadResponse(BaseModel):
    """Schema for bulk holdings upload response"""

    success: bool = Field(..., description="Whether the upload was successful")
    records_processed: int = Field(..., description="Number of records processed")
    message: str = Field(..., description="Response message")


class HoldingData(BaseModel):
    """Schema for a single holding from Kite API"""

    tradingsymbol: str = Field(..., description="Trading symbol")
    quantity: int = Field(..., description="Quantity of shares")
    average_price: float = Field(..., description="Average purchase price")
    last_price: float = Field(..., description="Last traded price")
    exchange: str = Field(..., description="Exchange (e.g., NSE, BSE)")

    model_config = {
        "json_schema_extra": {
            "example": {
                "tradingsymbol": "RELIANCE",
                "quantity": 100,
                "average_price": 2450.75,
                "last_price": 2500.00,
                "exchange": "NSE",
            }
        }
    }


class SyncHoldingsRequest(BaseModel):
    """Schema for syncing holdings from Kite"""

    broker_name: str = Field(
        ..., description="Name of the broker. One of: 'Zerodha', 'AngelOne', 'Groww'"
    )
    holdings: list[HoldingData] = Field(..., description="List of holdings to sync")

    model_config = {
        "json_schema_extra": {
            "example": {
                "broker_name": "Zerodha",
                "holdings": [
                    {
                        "tradingsymbol": "RELIANCE",
                        "quantity": 100,
                        "average_price": 2450.75,
                        "last_price": 2500.00,
                        "exchange": "NSE",
                    }
                ],
            }
        }
    }


class SyncHoldingsResponse(BaseModel):
    """Schema for sync holdings response"""

    synced_count: int = Field(..., description="Number of holdings synced")
    updated_count: int = Field(..., description="Number of holdings updated")
    message: str = Field(..., description="Response message")

    model_config = {
        "json_schema_extra": {
            "example": {
                "synced_count": 10,
                "updated_count": 3,
                "message": "Successfully synced 10 holdings, updated 3",
            }
        }
    }


class SyncStatusResponse(BaseModel):
    """Schema for sync status response"""

    last_sync: str | None = Field(None, description="ISO timestamp of last sync")
    synced_count: int | None = Field(None, description="Number of holdings synced in last sync")
    updated_count: int | None = Field(None, description="Number of holdings updated in last sync")

    model_config = {
        "json_schema_extra": {
            "example": {
                "last_sync": "2026-01-02T10:30:00+00:00",
                "synced_count": 10,
                "updated_count": 3,
            }
        }
    }


class DeleteBrokerHoldingsResponse(BaseModel):
    """Schema for delete broker holdings response"""

    success: bool = Field(..., description="Whether the deletion was successful")
    deleted_holdings_count: int = Field(..., description="Number of holdings deleted")
    metadata_deleted: bool = Field(..., description="Whether metadata was deleted")
    message: str = Field(..., description="Response message")

    model_config = {
        "json_schema_extra": {
            "example": {
                "success": True,
                "deleted_holdings_count": 15,
                "metadata_deleted": True,
                "message": "Successfully deleted 15 holdings and metadata for broker",
            }
        }
    }


# ---------------------------------------------------------------------------
# Portfolio view schemas
# ---------------------------------------------------------------------------


class PortfolioHoldingItem(BaseModel):
    """A single holding row enriched with computed portfolio fields."""

    id: UUID = Field(..., description="Unique holding identifier")
    symbol: str = Field(..., description="Trading symbol")
    company_name: str = Field(..., description="Company name")
    sector: str | None = Field(None, description="Sector")

    qty_available: int = Field(..., description="Available quantity")
    qty_long_term: int = Field(..., description="Long-term quantity")
    qty_pledged_margin: int = Field(..., description="Pledged-margin quantity")

    avg_price: Decimal = Field(..., description="Average purchase price")
    ltp: Decimal = Field(..., description="Last traded price (prev close as proxy)")

    investment_value: Decimal = Field(..., description="qty_available × avg_price")
    current_value: Decimal = Field(..., description="qty_available × ltp")
    pnl_absolute: Decimal = Field(..., description="current_value − investment_value")
    pnl_percent: Decimal = Field(..., description="pnl_absolute / investment_value × 100")
    weight_percent: Decimal = Field(..., description="current_value / total_portfolio_value × 100")


class PortfolioSummary(BaseModel):
    """Aggregate portfolio-level metrics."""

    total_current_value: Decimal
    total_investment_value: Decimal
    total_pnl_absolute: Decimal
    total_pnl_percent: Decimal


class PortfolioResponse(BaseModel):
    """Full portfolio view for one user–broker pair."""

    user_broker_id: UUID
    broker_id: UUID
    broker_name: str
    last_updated_at: datetime
    uploaded_via: str

    summary: PortfolioSummary
    holdings: list[PortfolioHoldingItem]
