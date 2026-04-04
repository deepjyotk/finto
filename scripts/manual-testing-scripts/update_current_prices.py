"""
TO run:
export GOOGLE_APPLICATION_CREDENTIALS="$PWD/finto-477904-93c8cc19777e.json"
python scripts/manual-testing-scripts/update_current_prices.py

"""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from typing import Any, Iterable

import gspread
import pandas as pd
from google.oauth2.service_account import Credentials
from gspread.utils import rowcol_to_a1
from src.tools.yfinance_wrappers import get_last_close_price

DEFAULT_SHEET_URL = (
    "https://docs.google.com/spreadsheets/d/1c6CS1Qp9hswt0MsHSyq7mny17eVXfsi2gvphgrDGPlg/edit"
)
DEFAULT_WORKSHEET = "Sheet1"
DEFAULT_SYMBOL_COLUMN = "Symbol"
DEFAULT_PRICE_COLUMN = "Current Price"
SHEETS_SCOPE = ["https://www.googleapis.com/auth/spreadsheets"]
TARGET_PRICE_COLUMN_INDEX = 11  # Column K
DEFAULT_CREDENTIALS_PATH = Path("~/.config/gspread/service_account.json").expanduser()


def extract_sheet_id(sheet_url: str) -> str:
    match = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", sheet_url)
    if not match:
        msg = f"Unable to extract sheet id from URL: {sheet_url}"
        raise ValueError(msg)
    return match.group(1)


def build_client(credentials_file: str | None, credentials_json: str | None) -> gspread.Client:
    if credentials_json:
        credentials_info: dict[str, Any] = json.loads(credentials_json)
        credentials = Credentials.from_service_account_info(credentials_info, scopes=SHEETS_SCOPE)
        return gspread.authorize(credentials)
    if credentials_file:
        if not Path(credentials_file).expanduser().exists():
            msg = (
                f"Credentials file '{credentials_file}' not found. "
                "Provide a valid path via --credentials-file or GOOGLE_APPLICATION_CREDENTIALS."
            )
            raise FileNotFoundError(msg)
        credentials = Credentials.from_service_account_file(credentials_file, scopes=SHEETS_SCOPE)
        return gspread.authorize(credentials)
    if DEFAULT_CREDENTIALS_PATH.exists():
        return gspread.service_account()
    msg = (
        "No Google service account credentials found. Set GOOGLE_APPLICATION_CREDENTIALS, "
        "GOOGLE_SHEETS_CREDENTIALS_JSON, or pass --credentials-file."
    )
    raise FileNotFoundError(msg)


def open_worksheet(
    client: gspread.Client, sheet_url: str, worksheet_name: str
) -> gspread.Worksheet:
    sheet_id = extract_sheet_id(sheet_url)
    spreadsheet = client.open_by_key(sheet_id)
    return spreadsheet.worksheet(worksheet_name)


def worksheet_to_dataframe(worksheet: gspread.Worksheet) -> pd.DataFrame:
    rows = worksheet.get_all_values()
    if not rows:
        return pd.DataFrame()
    header, *data = rows
    return pd.DataFrame(data, columns=header)


def fetch_prices(symbols: Iterable[str]) -> dict[str, float]:
    prices: dict[str, float] = {}
    for symbol in symbols:
        cleaned = symbol.strip()
        if not cleaned:
            continue
        try:
            result = get_last_close_price(cleaned)
        except Exception:
            continue
        price = result.get("last_close_price")
        if price is not None:
            prices[cleaned.upper()] = float(price)
    return prices


def update_price_column(
    worksheet: gspread.Worksheet,
    row_count: int,
    prices: list[Any],
    price_header: str,
    column_index: int = TARGET_PRICE_COLUMN_INDEX,
) -> None:
    header_cell = rowcol_to_a1(1, column_index)
    worksheet.update(header_cell, [[price_header]])
    if not prices:
        return
    start = rowcol_to_a1(2, column_index)
    end = rowcol_to_a1(row_count + 1, column_index)
    worksheet.update(f"{start}:{end}", [[value] for value in prices])


def build_price_column(df: pd.DataFrame, symbol_column: str, prices: dict[str, float]) -> list[Any]:
    symbols = df[symbol_column].fillna("").astype(str).str.strip()
    return [prices.get(symbol.upper(), "") for symbol in symbols]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Update column K in the manual testing sheet with live Yahoo Finance prices."
    )
    parser.add_argument(
        "--sheet-url",
        default=os.getenv("GOOGLE_SHEET_URL", DEFAULT_SHEET_URL),
        help="Google Sheet URL to read from and write to.",
    )
    parser.add_argument(
        "--worksheet",
        default=os.getenv("GOOGLE_SHEETS_WORKSHEET", DEFAULT_WORKSHEET),
        help="Worksheet/tab name inside the Google Sheet.",
    )
    parser.add_argument(
        "--symbol-column",
        default=os.getenv("SYMBOL_COLUMN", DEFAULT_SYMBOL_COLUMN),
        help="Column header containing ticker symbols.",
    )
    parser.add_argument(
        "--price-column",
        default=os.getenv("PRICE_COLUMN", DEFAULT_PRICE_COLUMN),
        help="Header to use for the price column (column K).",
    )
    parser.add_argument(
        "--credentials-file",
        default=os.getenv("GOOGLE_APPLICATION_CREDENTIALS"),
        help="Path to a Google service account JSON file.",
    )
    parser.add_argument(
        "--credentials-json",
        default=os.getenv("GOOGLE_SHEETS_CREDENTIALS_JSON"),
        help="Inline JSON credentials string for a Google service account.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    client = build_client(args.credentials_file, args.credentials_json)
    worksheet = open_worksheet(client, args.sheet_url, args.worksheet)
    df = worksheet_to_dataframe(worksheet)
    if df.empty:
        raise SystemExit("Worksheet is empty; nothing to update.")
    if args.symbol_column not in df.columns:
        raise SystemExit(f"Symbol column '{args.symbol_column}' not found in the sheet.")

    unique_symbols = (
        df[args.symbol_column].dropna().astype(str).str.strip().str.upper().unique().tolist()
    )
    prices_map = fetch_prices(unique_symbols)
    price_values = build_price_column(df, args.symbol_column, prices_map)
    update_price_column(worksheet, len(df), price_values, args.price_column)
    print(f"Updated {len(df)} rows in column K with latest prices.")


if __name__ == "__main__":
    main()
