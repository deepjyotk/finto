"""Broker service - handles broker-related operations including file parsing"""

import io
import zipfile
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID

import msoffcrypto
import pandas as pd

from src.api.schemas.holdings import HoldingsRequestSchema
from src.core.json_logging import logger_for
from src.repositories.broker_repo import BrokerRepository

logger = logger_for(__name__)


class BrokerService:
    """Service layer for broker operations"""

    ANGELONE_HEADER_ROW = 14

    ANGELONE_MAPPING = {
        "ISIN": "isin",
        "Company Name": "company_name",
        "Sector": "sector",
        "Total Quantity": "qty_available",
        "LTCG Quantity": "qty_long_term",
        "Margin Pledged Quantity": "qty_pledged_margin",
        "Avg Trading Price": "avg_price",
        "LTP": "prev_close_price",
    }

    ZERODHA_COLUMN_MAPPING = {
        # Zerodha
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

    def _detect_excel_format(self, file_content: bytes) -> str:
        """
        Detect the actual Excel file format by checking file signatures.
        Returns 'xlsx', 'xls', or 'unknown'.
        """
        # Check for .xlsx format (ZIP signature: PK\x03\x04)
        if file_content[:4] == b"PK\x03\x04":
            # Check if it's actually an Excel file by checking if it's a valid ZIP
            try:
                zipfile.ZipFile(io.BytesIO(file_content))
                return "xlsx"
            except (zipfile.BadZipFile, Exception):
                pass

        # Check for .xls format (OLE2 signature: D0 CF 11 E0 A1 B1 1A E1)
        if file_content[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
            return "xls"

        return "unknown"

    def _decrypt_excel_file(self, file_content: bytes, password: str, filename: str) -> bytes:
        try:
            file_obj = io.BytesIO(file_content)
            decrypted_file = io.BytesIO()
            office_file = msoffcrypto.OfficeFile(file_obj)
            logger.info(
                f"File encrypted: {office_file.is_encrypted()}, password provided: {bool(password)}"
            )
            office_file.load_key(password=password)
            office_file.decrypt(decrypted_file)
            decrypted_file.seek(0)
            result = decrypted_file.read()
            logger.info(f"Decryption successful, size: {len(result)}, header: {result[:4]}")
            return result
        except Exception as e:
            logger.error(f"Decryption failed: {type(e).__name__}: {e}")
            raise ValueError(f"Decryption failed: {e}") from e

    @staticmethod
    def _is_password_protected_error(error_msg: str) -> bool:
        """Check if an error message indicates password protection."""
        password_protected_errors = [
            "OLE2 compound document",
            "Can't find workbook",
            "password",
            "encrypted",
        ]
        return any(err in error_msg for err in password_protected_errors)

    def _try_remove_password_protection(self, file_content: bytes, filename: str) -> bytes:
        """
        Attempt to automatically remove/bypass password protection from Excel file.
        Tries common passwords and empty password.
        Returns decrypted file content if successful.
        """
        # Common passwords to try (including empty string)
        passwords_to_try = [
            "",
            "password",
            "Password",
            "123456",
            "1234",
            "admin",
            "Admin",
        ]

        file_obj = io.BytesIO(file_content)

        for pwd in passwords_to_try:
            try:
                file_obj.seek(0)  # Reset to beginning
                decrypted_file = io.BytesIO()

                office_file = msoffcrypto.OfficeFile(file_obj)
                office_file.load_key(password=pwd)
                office_file.decrypt(decrypted_file)

                # Successfully decrypted
                decrypted_file.seek(0)
                logger.info(
                    f"Successfully removed password protection from Excel file (used password: '{pwd if pwd else 'empty'}')"
                )
                return decrypted_file.read()
            except Exception:
                # Try next password
                continue

        # If all passwords failed, try to check if file is actually encrypted
        try:
            file_obj.seek(0)
            office_file = msoffcrypto.OfficeFile(file_obj)
            # Check if file is encrypted
            if office_file.is_encrypted():
                raise ValueError(
                    "Unable to automatically remove password protection. "
                    "The file is encrypted and requires the correct password."
                )
        except Exception:
            pass

        # If we get here, we couldn't decrypt it
        raise ValueError(
            "Unable to automatically remove password protection. "
            "The file may require a specific password."
        )

    def _handle_password_protected_file(
        self, content: bytes, filename: str, password: Optional[str], engine: str
    ) -> bytes:
        """
        Handle password-protected Excel file by attempting automatic removal or using provided password.
        Returns decrypted file content.
        """
        try:
            logger.info("Attempting to automatically remove password protection from Excel file")
            return self._try_remove_password_protection(content, filename)
        except Exception as decrypt_error:
            # If automatic removal failed and password provided, try with password
            if password:
                logger.info("Automatic password removal failed, trying with provided password")
                return self._decrypt_excel_file(content, password, filename)
            else:
                raise ValueError(
                    "Unable to automatically remove password protection. "
                    "Please provide the password or remove the password protection manually."
                ) from decrypt_error

    def _read_xlsx_file(
        self,
        content: bytes,
        filename: str,
        password: Optional[str],
        sheet_name: Optional[str] = None,
        header_row: int = 0,
    ) -> pd.DataFrame:
        try:
            return pd.read_excel(
                io.BytesIO(content),
                engine="openpyxl",
                sheet_name=sheet_name or 0,
                header=header_row,
            )
        except Exception as e:
            error_msg = str(e)
            if self._is_password_protected_error(error_msg):
                decrypted = self._handle_password_protected_file(
                    content, filename, password, "openpyxl"
                )
                return pd.read_excel(
                    io.BytesIO(decrypted),
                    engine="openpyxl",
                    sheet_name=sheet_name or 0,
                    header=header_row,
                )
            logger.warning(f"Failed to read as .xlsx with openpyxl, trying xlrd: {error_msg}")
            try:
                return pd.read_excel(
                    io.BytesIO(content),
                    engine="xlrd",
                    sheet_name=sheet_name or 0,
                    header=header_row,
                )
            except Exception:
                raise ValueError(f"Failed to read Excel file: {error_msg}") from e

    def _read_xls_file(
        self,
        content: bytes,
        filename: str,
        password: Optional[str],
        sheet_name: Optional[str] = None,
        header_row: int = 0,
    ) -> pd.DataFrame:
        logger.info(f"_read_xls_file: sheet={sheet_name}, header={header_row}")
        try:
            return pd.read_excel(
                io.BytesIO(content),
                engine="xlrd",
                sheet_name=sheet_name or 0,
                header=header_row,
            )
        except Exception as e:
            error_msg = str(e)
            logger.info(f"xlrd failed: {error_msg}")

            if "xlsx file; not supported" in error_msg.lower() or self._is_password_protected_error(
                error_msg
            ):
                logger.info("Detected encrypted xlsx, decrypting...")
                decrypted = self._handle_password_protected_file(
                    content, filename, password, "openpyxl"
                )
                engine = "openpyxl" if decrypted[:4] == b"PK\x03\x04" else "xlrd"
                logger.info(f"Reading with {engine}, sheet={sheet_name}, header={header_row}")
                try:
                    df = pd.read_excel(
                        io.BytesIO(decrypted),
                        engine=engine,
                        sheet_name=sheet_name or 0,
                        header=header_row,
                    )
                    logger.info(f"Read success, shape: {df.shape}")
                    return df
                except Exception as read_err:
                    logger.error(f"Read failed: {read_err}")
                    raise ValueError(
                        f"Failed to read decrypted Excel file: {read_err}"
                    ) from read_err

            logger.warning(f"Failed to read as .xls with xlrd, trying openpyxl: {error_msg}")
            try:
                return pd.read_excel(
                    io.BytesIO(content),
                    engine="openpyxl",
                    sheet_name=sheet_name or 0,
                    header=header_row,
                )
            except Exception:
                raise ValueError(f"Failed to read Excel file: {error_msg}") from e

    def _read_excel_file(
        self,
        file_content: bytes,
        filename: str,
        password: Optional[str],
        sheet_name: Optional[str] = None,
        header_row: int = 0,
    ) -> pd.DataFrame:
        detected_format = self._detect_excel_format(file_content)
        logger.info(
            f"_read_excel_file: format={detected_format}, sheet={sheet_name}, header={header_row}"
        )

        if detected_format == "xlsx":
            return self._read_xlsx_file(file_content, filename, password, sheet_name, header_row)
        elif detected_format == "xls":
            return self._read_xls_file(file_content, filename, password, sheet_name, header_row)
        else:
            if filename.lower().endswith(".xlsx"):
                return self._read_xlsx_file(
                    file_content, filename, password, sheet_name, header_row
                )
            else:
                return self._read_xls_file(file_content, filename, password, sheet_name, header_row)

    def _read_file(
        self,
        file_content: bytes,
        filename: str,
        password: Optional[str],
        sheet_name: Optional[str] = None,
        header_row: int = 0,
    ) -> pd.DataFrame:
        file_lower = filename.lower()
        if file_lower.endswith((".xlsx", ".xls")):
            return self._read_excel_file(file_content, filename, password, sheet_name, header_row)
        elif file_lower.endswith(".csv"):
            return pd.read_csv(io.BytesIO(file_content), header=header_row)
        else:
            raise ValueError(f"Unsupported file format: {filename}.")

    def _normalize_error_message(self, error: Exception) -> ValueError:
        """Convert generic exceptions to user-friendly ValueError messages."""
        error_msg = str(error)

        if "not a zip file" in error_msg.lower():
            return ValueError(
                "The file extension doesn't match the file format. "
                "The file appears to be an old .xls format but has a .xlsx extension, or vice versa. "
                "Please save the file with the correct extension (.xls for older Excel files, .xlsx for newer ones)."
            )
        elif "xlrd" in error_msg.lower() or "openpyxl" in error_msg.lower():
            return ValueError(
                f"Failed to read Excel file. The file may be corrupted or in an unsupported format. "
                f"Original error: {error_msg}"
            )
        else:
            return ValueError(f"Failed to read file: {error_msg}")

    def _normalize_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """Normalize DataFrame by adding missing columns and filling NaN values."""
        for col in ["sector", "qty_available", "qty_long_term", "qty_pledged_margin"]:
            if col not in df.columns:
                df[col] = None if col == "sector" else 0

        for col in ["qty_available", "qty_long_term", "qty_pledged_margin"]:
            df[col] = df[col].fillna(0)

        return df

    async def _process_zerodha_holdings(
        self, df: pd.DataFrame
    ) -> tuple[pd.DataFrame, dict[str, str]]:
        """Process Zerodha-specific holdings data and return DataFrame with discrepancies."""
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

        return df, discrepancies

    async def _process_angelone_holdings(
        self, df: pd.DataFrame
    ) -> tuple[pd.DataFrame, dict[str, str]]:
        discrepancies = {}
        required_fields = set(self.ANGELONE_MAPPING.values())
        missing = required_fields - set(df.columns)
        if missing:
            raise ValueError(f"Missing required columns: {', '.join(missing)}")

        isins = df["isin"].dropna().str.strip().tolist()
        isin_to_symbol = await self.repo.get_symbols_by_isins(isins) if isins else {}

        for isin in isins:
            if isin and isin not in isin_to_symbol:
                discrepancies[isin] = "not found in in_equities"

        df["symbol"] = df["isin"].apply(
            lambda i: isin_to_symbol.get(str(i).strip(), i) if pd.notna(i) else i
        )
        df = df.drop(columns=["isin"])

        nan_rows = df[df[["avg_price", "prev_close_price", "qty_available"]].isna().any(axis=1)]
        if not nan_rows.empty:
            for _, row in nan_rows.iterrows():
                logger.warning(
                    f"Dropping row with NaN: company={row.get('company_name')}, avg_price={row.get('avg_price')}, prev_close={row.get('prev_close_price')}, qty={row.get('qty_available')}"
                )

        df = df.dropna(subset=["avg_price", "prev_close_price", "qty_available"])
        return df, discrepancies

    def _dataframe_to_holdings(
        self, df: pd.DataFrame, broker_id: UUID
    ) -> list[HoldingsRequestSchema]:
        """Convert DataFrame to list of HoldingsRequestSchema objects."""
        holdings_list = []
        for idx, row in df.iterrows():
            try:
                if row["qty_available"] is None or row["qty_available"] <= 0:
                    continue
                holding = HoldingsRequestSchema(
                    broker_id=broker_id,
                    symbol=str(row["symbol"]).strip(),
                    company_name=str(row["company_name"]).strip(),
                    sector=(str(row["sector"]).strip() if pd.notna(row.get("sector")) else None),
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

        return holdings_list

    async def parse_holdings_file(
        self,
        file_content: bytes,
        filename: str,
        broker_id: UUID,
        password: Optional[str] = None,
    ) -> tuple[list[HoldingsRequestSchema], dict[str, str]]:
        broker_name = await self.repo.get_broker_name_by_id(broker_id)
        broker_lower = (broker_name or "").lower()

        sheet_name = "Equity" if broker_lower == "angelone" else None
        header_row = self.ANGELONE_HEADER_ROW if broker_lower == "angelone" else 0

        try:
            df = self._read_file(file_content, filename, password, sheet_name, header_row)
        except ValueError:
            raise
        except Exception as e:
            raise self._normalize_error_message(e) from e

        if broker_lower == "zerodha":
            df = df.rename(columns=self.ZERODHA_COLUMN_MAPPING)
            df, discrepancies = await self._process_zerodha_holdings(df)
        elif broker_lower == "angelone":
            df = df.rename(columns=self.ANGELONE_MAPPING)
            df, discrepancies = await self._process_angelone_holdings(df)
        else:
            raise ValueError(f"Unsupported broker: {broker_lower}. Please use Zerodha or AngelOne.")

        df = self._normalize_dataframe(df)
        holdings_list = self._dataframe_to_holdings(df, broker_id)

        return holdings_list, discrepancies
