"""
To run:
    export GOOGLE_APPLICATION_CREDENTIALS="$PWD/finto-477904-93c8cc19777e.json"
    python scripts/manual-testing-scripts/find_overall_POrL.py
"""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from typing import Any

import gspread
import pandas as pd
from google.oauth2.service_account import Credentials

DEFAULT_SHEET_URL = (
    "https://docs.google.com/spreadsheets/d/1c6CS1Qp9hswt0MsHSyq7mny17eVXfsi2gvphgrDGPlg/edit"
)
DEFAULT_WORKSHEET = "Sheet1"
DEFAULT_QUANTITY_COLUMN = "Quantity Available"
DEFAULT_AVG_PRICE_COLUMN = "Average Price"
DEFAULT_CURRENT_PRICE_COLUMN = "Current Price"
DEFAULT_CREDENTIALS_PATH = Path("~/.config/gspread/service_account.json").expanduser()
SHEETS_SCOPE = ["https://www.googleapis.com/auth/spreadsheets"]


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
        credentials_path = Path(credentials_file).expanduser()
        if not credentials_path.exists():
            msg = (
                f"Credentials file '{credentials_file}' not found. "
                "Provide a valid path via --credentials-file or GOOGLE_APPLICATION_CREDENTIALS."
            )
            raise FileNotFoundError(msg)
        credentials = Credentials.from_service_account_file(credentials_path, scopes=SHEETS_SCOPE)
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Calculate overall portfolio profit or loss and append it to the sheet."
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
        "--quantity-column",
        default=os.getenv("QUANTITY_COLUMN", DEFAULT_QUANTITY_COLUMN),
        help="Column header containing the quantity held.",
    )
    parser.add_argument(
        "--average-price-column",
        default=os.getenv("AVERAGE_PRICE_COLUMN", DEFAULT_AVG_PRICE_COLUMN),
        help="Column header containing the average purchase price.",
    )
    parser.add_argument(
        "--current-price-column",
        default=os.getenv("CURRENT_PRICE_COLUMN", DEFAULT_CURRENT_PRICE_COLUMN),
        help="Column header containing the latest price (column K).",
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


def calculate_overall_pl(
    df: pd.DataFrame, quantity_col: str, avg_col: str, price_col: str
) -> tuple[float, float]:
    for column in (quantity_col, avg_col, price_col):
        if column not in df.columns:
            raise SystemExit(f"Column '{column}' not found in the sheet.")

    raw_current_prices = pd.to_numeric(df[price_col], errors="coerce")
    valid_mask = ~raw_current_prices.isna()
    if not valid_mask.any():
        return 0.0, 0.0

    quantities = pd.to_numeric(df[quantity_col], errors="coerce").where(valid_mask).fillna(0)
    avg_prices = pd.to_numeric(df[avg_col], errors="coerce").where(valid_mask).fillna(0)
    current_prices = raw_current_prices.where(valid_mask).fillna(0)

    invested = (avg_prices * quantities).sum()
    current_value = (current_prices * quantities).sum()

    profit_amount = current_value - invested
    profit_percent = (profit_amount / invested * 100) if invested else 0.0
    return profit_percent, profit_amount


def append_overall_row(
    worksheet: gspread.Worksheet, profit_percent: float, profit_amount: float
) -> None:
    row_values = [
        "OVERALL P/L %",
        round(profit_percent, 2),
        "OVERALL P/L AMOUNT",
        round(profit_amount, 2),
    ]
    worksheet.append_row(row_values, value_input_option="USER_ENTERED")


def main() -> None:
    args = parse_args()
    client = build_client(args.credentials_file, args.credentials_json)
    worksheet = open_worksheet(client, args.sheet_url, args.worksheet)
    df = worksheet_to_dataframe(worksheet)
    if df.empty:
        raise SystemExit("Worksheet is empty; nothing to calculate.")

    profit_percent, profit_amount = calculate_overall_pl(
        df, args.quantity_column, args.average_price_column, args.current_price_column
    )
    append_overall_row(worksheet, profit_percent, profit_amount)
    print(f"Overall profit/loss: {profit_percent:.2f}% ({profit_amount:.2f})")


if __name__ == "__main__":
    main()
