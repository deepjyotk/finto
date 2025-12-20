"""Broker service - handles broker-related operations including file parsing"""

import io
from decimal import Decimal
from typing import Any
from uuid import UUID

import pandas as pd

from src.api.schemas.holdings import HoldingsRequestSchema
from src.core.json_logging import logger_for
from src.repositories.broker_repo import BrokerRepository

logger = logger_for(__name__)


class BrokerService:
    """Service layer for broker operations"""

    COLUMN_MAPPING = {
        "Symbol": "symbol",
        "Company Name": "company_name",
        "Sector": "sector",
        "Quantity Available": "qty_available",
        "Quantity Long Term": "qty_long_term",
        "Quantity Pledged (Margin)": "qty_pledged_margin",
        "Average Price": "avg_price",
        "Previous Closing Price": "prev_close_price",
    }
    EXISTING_ZEODHA_SYMBOL_MAPPINGS_DISCREPANCY = {
        "HBLPOWER.NS": "HBLENGINE.NS",
        "RSIL.NS": "RSYSTEMS.NS",
    }

    def __init__(self, repo: BrokerRepository):
        self.repo = repo

    async def get_all_brokers(self) -> list[dict[str, Any]]:
        brokers = await self.repo.get_all_brokers()
        return [
            {
                "broker_id": str(broker["broker_id"]),
                "broker_name": broker["broker_name"],
                "broker_type": broker["broker_type"],
                "country": broker["country"],
            }
            for broker in brokers
        ]

    async def parse_holdings_file(
        self, file_content: bytes, filename: str, broker_id: UUID
    ) -> (list[HoldingsRequestSchema], dict[str, str]):
        file_lower = filename.lower()

        try:
            if file_lower.endswith((".xlsx", ".xls")):
                df = pd.read_excel(io.BytesIO(file_content))
            elif file_lower.endswith(".csv"):
                df = pd.read_csv(io.BytesIO(file_content))
            else:
                raise ValueError(f"Unsupported file format: {filename}.")
        except Exception as e:
            raise ValueError(f"Failed to read file: {str(e)}") from e

        df = df.rename(columns=self.COLUMN_MAPPING)

        broker_name = await self.repo.get_broker_name_by_id(broker_id)
        is_zerodha = broker_name and broker_name.lower() == "zerodha"

        if is_zerodha:
            required_fields = {"symbol", "qty_available", "avg_price", "prev_close_price"}
            missing = required_fields - set(df.columns)
            if missing:
                raise ValueError(f"Missing required columns for Zerodha: {', '.join(missing)}")

            discrepancies = {}
            original_symbols = df["symbol"].str.strip().tolist()

            # Track remapped symbols
            for s in original_symbols:
                if s in self.EXISTING_ZEODHA_SYMBOL_MAPPINGS_DISCREPANCY:
                    discrepancies[s] = (
                        f"remapped to {self.EXISTING_ZEODHA_SYMBOL_MAPPINGS_DISCREPANCY[s]}"
                    )

            symbols = [
                self.EXISTING_ZEODHA_SYMBOL_MAPPINGS_DISCREPANCY.get(s, s) for s in original_symbols
            ]
            symbols = [s[:-3] if s.endswith(".NS") or s.endswith(".BO") else s for s in symbols]
            symbol_to_company = await self.repo.get_company_names_by_symbols(symbols)

            # Track missing symbols
            for s in symbols:
                if s not in symbol_to_company:
                    discrepancies[s] = "not found in in_equities, using symbol as company_name"

            if discrepancies:
                logger.warning(f"Symbol discrepancies: {discrepancies}")

            # Clean symbols and update DataFrame
            df["symbol"] = (
                df["symbol"].str.strip().replace(self.EXISTING_ZEODHA_SYMBOL_MAPPINGS_DISCREPANCY)
            )
            df["symbol"] = df["symbol"].str.replace(r"\.(NS|BO)$", "", regex=True)
            df["company_name"] = df["symbol"].map(lambda s: symbol_to_company.get(s, s))
        else:
            discrepancies = {}
            required_fields = ["symbol", "company_name", "avg_price", "prev_close_price"]
            missing = [f for f in required_fields if f not in df.columns]
            if missing:
                raise ValueError(f"Missing required columns: {', '.join(missing)}")

        for col in ["sector", "qty_available", "qty_long_term", "qty_pledged_margin"]:
            if col not in df.columns:
                df[col] = None if col == "sector" else 0

        for col in ["qty_available", "qty_long_term", "qty_pledged_margin"]:
            df[col] = df[col].fillna(0)

        holdings_list = []
        for idx, row in df.iterrows():
            try:
                holding = HoldingsRequestSchema(
                    broker_id=broker_id,
                    symbol=str(row["symbol"]).strip(),
                    company_name=str(row["company_name"]).strip(),
                    sector=str(row["sector"]).strip() if pd.notna(row.get("sector")) else None,
                    qty_available=int(row["qty_available"]),
                    qty_long_term=int(row["qty_long_term"]),
                    qty_pledged_margin=int(row["qty_pledged_margin"]),
                    avg_price=Decimal(str(row["avg_price"])),
                    prev_close_price=Decimal(str(row["prev_close_price"])),
                )
                holdings_list.append(holding)
            except Exception as e:
                raise ValueError(f"Error parsing row {idx + 2}: {str(e)}") from e

        if not holdings_list:
            raise ValueError("No valid holdings found in file")

        return holdings_list, discrepancies
