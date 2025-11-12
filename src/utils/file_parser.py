"""File parsing utilities for holdings upload"""

import io
from decimal import Decimal
from typing import BinaryIO
from uuid import UUID

import pandas as pd

from src.api.schemas.holdings import HoldingsRequestSchema


# Column mapping from Excel format to schema field names
COLUMN_MAPPING = {
    "Symbol": "symbol",
    "ISIN": "isin",
    "Sector": "sector",
    "Quantity Available": "qty_available",
    "Quantity Discrepant": "qty_discrepant",
    "Quantity Long Term": "qty_long_term",
    "Quantity Pledged (Margin)": "qty_pledged_margin",
    "Quantity Pledged (Loan)": "qty_pledged_loan",
    "Average Price": "avg_price",
    "Previous Closing Price": "prev_close_price",
    "Unrealized P&L": "unrealized_pnl",
    "Unrealized P&L Pct.": "unrealized_pnl_pct",
}


def parse_holdings_file(
    file_content: bytes, filename: str, broker_id: UUID
) -> list[HoldingsRequestSchema]:
    """
    Parse uploaded Excel or CSV file to list of HoldingsRequestSchema.

    Args:
        file_content: Binary content of the uploaded file
        filename: Name of the uploaded file (to determine file type)
        broker_id: UUID of the broker (from form data)

    Returns:
        List of HoldingsRequestSchema objects

    Raises:
        ValueError: If file format is not supported or parsing fails
    """
    # Determine file type and read into DataFrame
    file_lower = filename.lower()

    try:
        if file_lower.endswith((".xlsx", ".xls")):
            # Read Excel file
            df = pd.read_excel(io.BytesIO(file_content))
        elif file_lower.endswith(".csv"):
            # Read CSV file
            df = pd.read_csv(io.BytesIO(file_content))
        else:
            raise ValueError(
                f"Unsupported file format: {filename}. " "Please upload .xlsx, .xls, or .csv files."
            )
    except Exception as e:
        raise ValueError(f"Failed to read file: {str(e)}") from e

    # Rename columns according to mapping
    df = df.rename(columns=COLUMN_MAPPING)

    # Validate required columns exist
    required_fields = [
        "symbol",
        "isin",
        "avg_price",
        "prev_close_price",
        "unrealized_pnl",
        "unrealized_pnl_pct",
    ]
    missing_columns = [field for field in required_fields if field not in df.columns]
    if missing_columns:
        raise ValueError(
            f"Missing required columns in file: {', '.join(missing_columns)}. "
            f"Expected columns: {', '.join(COLUMN_MAPPING.keys())}"
        )

    # Fill missing optional columns with default values
    if "sector" not in df.columns:
        df["sector"] = None
    if "qty_available" not in df.columns:
        df["qty_available"] = 0
    if "qty_discrepant" not in df.columns:
        df["qty_discrepant"] = 0
    if "qty_long_term" not in df.columns:
        df["qty_long_term"] = 0
    if "qty_pledged_margin" not in df.columns:
        df["qty_pledged_margin"] = 0
    if "qty_pledged_loan" not in df.columns:
        df["qty_pledged_loan"] = 0

    # Replace NaN values with defaults (handle numeric and string columns separately)
    numeric_cols = [
        "qty_available",
        "qty_discrepant",
        "qty_long_term",
        "qty_pledged_margin",
        "qty_pledged_loan",
    ]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = df[col].fillna(0)

    # Convert DataFrame rows to HoldingsRequestSchema objects
    holdings_list = []
    for idx, row in df.iterrows():
        try:
            holding = HoldingsRequestSchema(
                broker_id=broker_id,
                symbol=str(row["symbol"]).strip(),
                isin=str(row["isin"]).strip(),
                sector=str(row["sector"]).strip() if pd.notna(row["sector"]) else None,
                qty_available=int(row["qty_available"]),
                qty_discrepant=int(row["qty_discrepant"]),
                qty_long_term=int(row["qty_long_term"]),
                qty_pledged_margin=int(row["qty_pledged_margin"]),
                qty_pledged_loan=int(row["qty_pledged_loan"]),
                avg_price=Decimal(str(row["avg_price"])),
                prev_close_price=Decimal(str(row["prev_close_price"])),
                unrealized_pnl=Decimal(str(row["unrealized_pnl"])),
                unrealized_pnl_pct=Decimal(str(row["unrealized_pnl_pct"])),
            )
            holdings_list.append(holding)
        except Exception as e:
            raise ValueError(f"Error parsing row {idx + 2}: {str(e)}") from e

    if not holdings_list:
        raise ValueError("No valid holdings found in file")

    return holdings_list
