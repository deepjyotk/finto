#!/usr/bin/env python3
"""
Load EAV-format CSV files → f_income_statements, f_balance_sheets, f_cash_flows.

Handles both the income-statement CSV (fetch_pnl_statements.py output) and the
balance-sheet / cash-flow CSV (fetch_financials.py output). Both share the
same long/EAV CSV format:

    symbol, symbol_ns, statement_type, metric, period, value

statement_type routing
----------------------
  annual, quarterly              → f_income_statements
  annual_balance, quarterly_balance   → f_balance_sheets
  annual_cashflow, quarterly_cashflow → f_cash_flows

Usage
-----
  python scripts/db-scripts/load_pnl_statements.py                      # income CSV (default)
  python scripts/db-scripts/load_pnl_statements.py --file path/to.csv   # any EAV CSV
  python scripts/db-scripts/load_pnl_statements.py --truncate           # wipe tables first
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import os
from datetime import date
from pathlib import Path

import asyncpg
from dotenv import load_dotenv

load_dotenv()

SCRIPT_DIR = Path(__file__).parent
DEFAULT_CSV = SCRIPT_DIR.parent / "artifacts" / "pnl_statements.csv"
CHUNK_SIZE = 2_000  # rows per chunk

# ---------------------------------------------------------------------------
# Metric → column index maps
# Each dict maps every known yfinance metric name (CamelCase AND spaced/pretty)
# to an integer index into the metric-values list for that statement type.
# ---------------------------------------------------------------------------

_INCOME_COLS = [
    "total_revenue", "cost_of_revenue", "gross_profit", "operating_expense",
    "operating_income", "ebitda", "interest_expense", "tax_provision",
    "pretax_income", "net_income", "basic_eps", "diluted_eps", "total_expenses",
]

_INCOME_METRIC_MAP: dict[str, int] = {
    # CamelCase (modern yfinance)
    "TotalRevenue": 0, "CostOfRevenue": 1, "GrossProfit": 2,
    "OperatingExpense": 3, "OperatingIncome": 4, "EBITDA": 5,
    "InterestExpense": 6, "TaxProvision": 7, "PretaxIncome": 8,
    "NetIncome": 9, "BasicEPS": 10, "DilutedEPS": 11, "TotalExpenses": 12,
    # Spaced / pretty names (older yfinance or pretty=True)
    "Total Revenue": 0, "Cost Of Revenue": 1, "Gross Profit": 2,
    "Operating Expense": 3, "Operating Income": 4, "Ebitda": 5,
    "Interest Expense": 6, "Tax Provision": 7, "Pretax Income": 8,
    "Net Income": 9, "Basic EPS": 10, "Diluted EPS": 11, "Total Expenses": 12,
}

_BALANCE_COLS = [
    "total_assets", "current_assets", "cash_and_cash_equivalents",
    "accounts_receivable", "inventory", "net_ppe", "total_non_current_assets",
    "goodwill", "total_liabilities", "current_liabilities", "current_debt",
    "accounts_payable", "long_term_debt", "total_debt", "stockholders_equity",
    "common_stock_equity", "retained_earnings", "working_capital", "net_debt",
]

_BALANCE_METRIC_MAP: dict[str, int] = {
    "TotalAssets": 0, "CurrentAssets": 1, "CashAndCashEquivalents": 2,
    "AccountsReceivable": 3, "Inventory": 4, "NetPPE": 5,
    "TotalNonCurrentAssets": 6, "Goodwill": 7,
    "TotalLiabilitiesNetMinorityInterest": 8, "CurrentLiabilities": 9,
    "CurrentDebt": 10, "AccountsPayable": 11, "LongTermDebt": 12,
    "TotalDebt": 13, "StockholdersEquity": 14, "CommonStockEquity": 15,
    "RetainedEarnings": 16, "WorkingCapital": 17, "NetDebt": 18,
    # Spaced variants
    "Total Assets": 0, "Current Assets": 1, "Cash And Cash Equivalents": 2,
    "Accounts Receivable": 3, "Net PPE": 5,
    "Total Non Current Assets": 6,
    "Total Liabilities Net Minority Interest": 8, "Current Liabilities": 9,
    "Current Debt": 10, "Accounts Payable": 11, "Long Term Debt": 12,
    "Total Debt": 13, "Stockholders Equity": 14, "Common Stock Equity": 15,
    "Retained Earnings": 16, "Working Capital": 17, "Net Debt": 18,
}

_CASHFLOW_COLS = [
    "operating_cash_flow", "net_income_from_continuing_ops",
    "depreciation_and_amortization", "change_in_working_capital",
    "change_in_receivables", "change_in_inventory", "change_in_payable",
    "investing_cash_flow", "capital_expenditure", "capital_expenditure_reported",
    "purchase_of_ppe", "sale_of_ppe", "purchase_of_investment", "sale_of_investment",
    "financing_cash_flow", "net_issuance_payments_of_debt",
    "long_term_debt_issuance", "long_term_debt_payments",
    "common_stock_issuance", "cash_dividends_paid",
    "free_cash_flow", "changes_in_cash", "end_cash_position",
]

_CASHFLOW_METRIC_MAP: dict[str, int] = {
    "OperatingCashFlow": 0,
    "NetIncomeFromContinuingOperations": 1,
    "DepreciationAndAmortization": 2,
    "ChangeInWorkingCapital": 3, "ChangeInReceivables": 4,
    "ChangeInInventory": 5, "ChangeInPayable": 6,
    "InvestingCashFlow": 7, "CapitalExpenditure": 8,
    "CapitalExpenditureReported": 9, "PurchaseOfPPE": 10,
    "SaleOfPPE": 11, "PurchaseOfInvestment": 12, "SaleOfInvestment": 13,
    "FinancingCashFlow": 14, "NetIssuancePaymentsOfDebt": 15,
    "LongTermDebtIssuance": 16, "LongTermDebtPayments": 17,
    "CommonStockIssuance": 18, "CashDividendsPaid": 19,
    "FreeCashFlow": 20, "ChangesInCash": 21, "EndCashPosition": 22,
    # Spaced variants
    "Operating Cash Flow": 0,
    "Net Income From Continuing Operations": 1,
    "Depreciation And Amortization": 2,
    "Change In Working Capital": 3, "Change In Receivables": 4,
    "Change In Inventory": 5, "Change In Payable": 6,
    "Investing Cash Flow": 7, "Capital Expenditure": 8,
    "Capital Expenditure Reported": 9, "Purchase Of PPE": 10,
    "Sale Of PPE": 11, "Purchase Of Investment": 12, "Sale Of Investment": 13,
    "Financing Cash Flow": 14, "Net Issuance Payments Of Debt": 15,
    "Long Term Debt Issuance": 16, "Long Term Debt Payments": 17,
    "Common Stock Issuance": 18, "Cash Dividends Paid": 19,
    "Free Cash Flow": 20, "Changes In Cash": 21, "End Cash Position": 22,
}

# statement_type → (table_name, col_list, metric_map, normalized_type)
_STMT_ROUTING: dict[str, tuple[str, list[str], dict[str, int], str]] = {
    "annual":             ("f_income_statements", _INCOME_COLS,   _INCOME_METRIC_MAP,   "annual"),
    "quarterly":          ("f_income_statements", _INCOME_COLS,   _INCOME_METRIC_MAP,   "quarterly"),
    "annual_balance":     ("f_balance_sheets",    _BALANCE_COLS,  _BALANCE_METRIC_MAP,  "annual"),
    "quarterly_balance":  ("f_balance_sheets",    _BALANCE_COLS,  _BALANCE_METRIC_MAP,  "quarterly"),
    "annual_cashflow":    ("f_cash_flows",         _CASHFLOW_COLS, _CASHFLOW_METRIC_MAP, "annual"),
    "quarterly_cashflow": ("f_cash_flows",         _CASHFLOW_COLS, _CASHFLOW_METRIC_MAP, "quarterly"),
}

# Unique constraint name per table (used in ON CONFLICT clause)
_UQ_CONSTRAINT: dict[str, str] = {
    "f_income_statements": "uq_income_equity_type_period",
    "f_balance_sheets":    "uq_balance_equity_type_period",
    "f_cash_flows":        "uq_cashflow_equity_type_period",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_date(s: str) -> date | None:
    try:
        return date.fromisoformat(s)
    except (ValueError, TypeError):
        return None


def _parse_value(s: str) -> float | None:
    try:
        return float(s)
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# Pivot
# ---------------------------------------------------------------------------

def pivot_csv(csv_path: Path) -> dict[str, list[tuple]]:
    """
    Read the long/EAV CSV and pivot into typed rows per destination table.

    Returns a dict keyed by table name, each value is a list of tuples:
        (symbol_bare, stmt_type_normalized, period, metric_val_0, metric_val_1, ...)
    """
    # key = (symbol_bare, stmt_type_raw, period) → metric values list
    groups: dict[tuple, list[float | None]] = {}
    group_meta: dict[tuple, tuple[str, str]] = {}  # key → (table_name, normalized_type)

    print(f"Reading {csv_path} …")
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            d = _parse_date(row.get("period", ""))
            if d is None:
                continue
            v = _parse_value(row.get("value", ""))
            if v is None:
                continue
            metric = row.get("metric", "").strip()
            if not metric:
                continue

            symbol_ns = row.get("symbol_ns", "").strip()
            symbol_bare = row.get("symbol", symbol_ns.split(".")[0]).strip().upper()
            stmt_type = row.get("statement_type", "").strip()

            routing = _STMT_ROUTING.get(stmt_type)
            if routing is None:
                continue  # unknown statement type

            table_name, col_list, metric_map, normalized_type = routing
            col_idx = metric_map.get(metric)
            if col_idx is None:
                continue  # unknown metric for this statement type

            key = (symbol_bare, stmt_type, d)
            if key not in groups:
                groups[key] = [None] * len(col_list)
                group_meta[key] = (table_name, normalized_type)

            groups[key][col_idx] = v

            if (i + 1) % 100_000 == 0:
                print(f"  … read {i+1:,} CSV rows, {len(groups):,} typed rows so far")

    result: dict[str, list[tuple]] = {
        "f_income_statements": [],
        "f_balance_sheets": [],
        "f_cash_flows": [],
    }
    for (symbol_bare, _stmt_type, period), metric_vals in groups.items():
        table_name, normalized_type = group_meta[(symbol_bare, _stmt_type, period)]
        result[table_name].append((symbol_bare, normalized_type, period, *metric_vals))

    for tbl, rows in result.items():
        print(f"  {tbl}: {len(rows):,} typed rows")
    return result


# ---------------------------------------------------------------------------
# Upsert
# ---------------------------------------------------------------------------

async def _upsert_table_chunk(
    conn: asyncpg.Connection,
    table: str,
    col_list: list[str],
    rows: list[tuple],
) -> None:
    """Upsert one chunk into a typed financial table via temp stage + INSERT."""
    if not rows:
        return

    temp = f"_stage_{table.replace('f_', '')}"
    metric_col_defs = ", ".join(f"{c} NUMERIC" for c in col_list)
    metric_col_names = ", ".join(col_list)
    metric_select = ", ".join(f"s.{c}" for c in col_list)
    metric_updates = ", ".join(f"{c} = EXCLUDED.{c}" for c in col_list)
    all_cols = ["symbol", "statement_type", "period"] + col_list

    async with conn.transaction():
        await conn.execute(
            f"""
            CREATE TEMP TABLE IF NOT EXISTS {temp} (
                symbol         TEXT,
                statement_type TEXT,
                period         DATE,
                {metric_col_defs}
            ) ON COMMIT DELETE ROWS
            """
        )

        await conn.copy_records_to_table(temp, records=rows, columns=all_cols)

        await conn.execute(
            f"""
            INSERT INTO {table}
                (in_equity_id, statement_type, period, {metric_col_names})
            SELECT
                ie.id, s.statement_type, s.period, {metric_select}
            FROM {temp} AS s
            JOIN in_equities AS ie ON ie.symbol = upper(btrim(s.symbol))
            ON CONFLICT ON CONSTRAINT {_UQ_CONSTRAINT[table]}
            DO UPDATE SET
                {metric_updates},
                updated_at = now()
            """
        )


async def load(csv_path: Path, truncate: bool) -> None:
    raw_url = os.environ["DATABASE_URL"]
    url = raw_url.replace("postgresql+asyncpg://", "postgresql://")

    print("Connecting to DB …")
    conn = await asyncpg.connect(url)

    try:
        if truncate:
            print("Truncating typed financial tables …")
            for tbl in ("f_income_statements", "f_balance_sheets", "f_cash_flows"):
                await conn.execute(f"TRUNCATE TABLE {tbl} RESTART IDENTITY")

        table_rows = pivot_csv(csv_path)

        for table, rows in table_rows.items():
            if not rows:
                print(f"  {table}: no rows, skipping")
                continue

            col_list = (
                _INCOME_COLS   if table == "f_income_statements" else
                _BALANCE_COLS  if table == "f_balance_sheets"    else
                _CASHFLOW_COLS
            )

            total = len(rows)
            upserted = 0
            for i in range(0, total, CHUNK_SIZE):
                chunk = rows[i : i + CHUNK_SIZE]
                await _upsert_table_chunk(conn, table, col_list, chunk)
                upserted += len(chunk)
                print(f"  {table}: {upserted:,}/{total:,}", end="\r")
            print()

        print("\nRow counts:")
        for tbl in ("f_income_statements", "f_balance_sheets", "f_cash_flows"):
            count = await conn.fetchval(f"SELECT COUNT(*) FROM {tbl}")
            print(f"  {tbl}: {count:,}")

    finally:
        await conn.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--file",
        type=Path,
        default=DEFAULT_CSV,
        help="Path to EAV CSV (pnl_statements.csv or financial_statements.csv)",
    )
    parser.add_argument(
        "--truncate",
        action="store_true",
        help="Truncate all three financial tables before loading",
    )
    args = parser.parse_args()

    if not args.file.exists():
        raise SystemExit(f"CSV not found: {args.file}")

    asyncio.run(load(args.file, args.truncate))


if __name__ == "__main__":
    main()
