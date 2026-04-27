"""split f_financial_statements JSONB into three typed tables

Revision ID: n9o0p1q2r3s4
Revises: m8n9o0p1q2r3
Create Date: 2026-04-25

Replaces the single JSONB table (f_financial_statements) with three typed tables:

  f_income_statements  — 'annual' + 'quarterly' income statements
  f_balance_sheets     — 'annual' + 'quarterly' balance sheets
  f_cash_flows         — 'annual' + 'quarterly' cash flow statements

Benefits
--------
* B-tree indexes on individual metrics → sort/filter without a sequential scan
* No schemaless JSONB blob — each metric is a typed NUMERIC column
* ~30 % smaller on-disk (no JSON key repetition overhead)

Index strategy
--------------
Each table gets:
  1. Composite B-tree on (in_equity_id, statement_type, period) — the primary
     single-stock look-up (also the unique constraint).
  2. Partial B-tree on key metric columns WHERE statement_type = 'annual' —
     powers cross-stock screener ORDER BY / WHERE without a full table scan.

Data migration
--------------
Extracts each metric from the JSONB data column using COALESCE over both
naming conventions: CamelCase (modern yfinance, e.g. 'TotalRevenue') and
spaced/pretty (older yfinance, e.g. 'Total Revenue').

Downgrade
---------
Recreates f_financial_statements (empty). Reload data from CSV with the
load_pnl_statements.py script (pass --file for each CSV artifact).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "n9o0p1q2r3s4"
down_revision: Union[str, None] = "m8n9o0p1q2r3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _coalesce(camel: str, spaced: str) -> str:
    """SQL fragment: try CamelCase JSONB key first, fall back to spaced key."""
    return (
        f"COALESCE((data->>'{camel}')::numeric, (data->>'{spaced}')::numeric)"
    )


def _stmt_normalized(col: str = "statement_type", mapping: dict | None = None) -> str:
    """CASE expression that strips suffixes (_balance, _cashflow) from statement_type."""
    if mapping is None:
        mapping = {
            "annual": "annual",
            "quarterly": "quarterly",
            "annual_balance": "annual",
            "quarterly_balance": "quarterly",
            "annual_cashflow": "annual",
            "quarterly_cashflow": "quarterly",
        }
    cases = " ".join(
        f"WHEN {col} = '{k}' THEN '{v}'" for k, v in mapping.items()
    )
    return f"CASE {cases} END"


# ---------------------------------------------------------------------------
# upgrade
# ---------------------------------------------------------------------------

def upgrade() -> None:
    # ── 1. f_income_statements ────────────────────────────────────────────
    op.create_table(
        "f_income_statements",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("in_equity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("statement_type", sa.Text(), nullable=False),   # 'annual' | 'quarterly'
        sa.Column("period", sa.Date(), nullable=False),
        # ── Income metrics ──────────────────────────────────────────────
        sa.Column("total_revenue", sa.Numeric(), nullable=True),
        sa.Column("cost_of_revenue", sa.Numeric(), nullable=True),
        sa.Column("gross_profit", sa.Numeric(), nullable=True),
        sa.Column("operating_expense", sa.Numeric(), nullable=True),
        sa.Column("operating_income", sa.Numeric(), nullable=True),
        sa.Column("ebitda", sa.Numeric(), nullable=True),
        sa.Column("interest_expense", sa.Numeric(), nullable=True),
        sa.Column("tax_provision", sa.Numeric(), nullable=True),
        sa.Column("pretax_income", sa.Numeric(), nullable=True),
        sa.Column("net_income", sa.Numeric(), nullable=True),
        sa.Column("basic_eps", sa.Numeric(), nullable=True),
        sa.Column("diluted_eps", sa.Numeric(), nullable=True),
        sa.Column("total_expenses", sa.Numeric(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["in_equity_id"],
            ["in_equities.id"],
            name="fk_f_income_statements_in_equity_id",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "in_equity_id", "statement_type", "period",
            name="uq_income_equity_type_period",
        ),
    )

    op.create_index(
        "ix_income_equity_type_period",
        "f_income_statements",
        ["in_equity_id", "statement_type", "period"],
    )
    # Key screener indexes (annual only — quarterly rarely sorted cross-stock)
    op.execute(
        "CREATE INDEX ix_income_net_income_annual "
        "ON f_income_statements (net_income) "
        "WHERE statement_type = 'annual'"
    )
    op.execute(
        "CREATE INDEX ix_income_total_revenue_annual "
        "ON f_income_statements (total_revenue) "
        "WHERE statement_type = 'annual'"
    )
    op.execute(
        "CREATE INDEX ix_income_ebitda_annual "
        "ON f_income_statements (ebitda) "
        "WHERE statement_type = 'annual'"
    )
    op.execute(
        "CREATE INDEX ix_income_basic_eps_annual "
        "ON f_income_statements (basic_eps) "
        "WHERE statement_type = 'annual'"
    )

    # ── 2. f_balance_sheets ───────────────────────────────────────────────
    op.create_table(
        "f_balance_sheets",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("in_equity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("statement_type", sa.Text(), nullable=False),
        sa.Column("period", sa.Date(), nullable=False),
        # ── Balance-sheet metrics ───────────────────────────────────────
        sa.Column("total_assets", sa.Numeric(), nullable=True),
        sa.Column("current_assets", sa.Numeric(), nullable=True),
        sa.Column("cash_and_cash_equivalents", sa.Numeric(), nullable=True),
        sa.Column("accounts_receivable", sa.Numeric(), nullable=True),
        sa.Column("inventory", sa.Numeric(), nullable=True),
        sa.Column("net_ppe", sa.Numeric(), nullable=True),
        sa.Column("total_non_current_assets", sa.Numeric(), nullable=True),
        sa.Column("goodwill", sa.Numeric(), nullable=True),
        sa.Column("total_liabilities", sa.Numeric(), nullable=True),
        sa.Column("current_liabilities", sa.Numeric(), nullable=True),
        sa.Column("current_debt", sa.Numeric(), nullable=True),
        sa.Column("accounts_payable", sa.Numeric(), nullable=True),
        sa.Column("long_term_debt", sa.Numeric(), nullable=True),
        sa.Column("total_debt", sa.Numeric(), nullable=True),
        sa.Column("stockholders_equity", sa.Numeric(), nullable=True),
        sa.Column("common_stock_equity", sa.Numeric(), nullable=True),
        sa.Column("retained_earnings", sa.Numeric(), nullable=True),
        sa.Column("working_capital", sa.Numeric(), nullable=True),
        sa.Column("net_debt", sa.Numeric(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["in_equity_id"],
            ["in_equities.id"],
            name="fk_f_balance_sheets_in_equity_id",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "in_equity_id", "statement_type", "period",
            name="uq_balance_equity_type_period",
        ),
    )

    op.create_index(
        "ix_balance_equity_type_period",
        "f_balance_sheets",
        ["in_equity_id", "statement_type", "period"],
    )
    op.execute(
        "CREATE INDEX ix_balance_total_assets_annual "
        "ON f_balance_sheets (total_assets) "
        "WHERE statement_type = 'annual'"
    )
    op.execute(
        "CREATE INDEX ix_balance_total_debt_annual "
        "ON f_balance_sheets (total_debt) "
        "WHERE statement_type = 'annual'"
    )
    op.execute(
        "CREATE INDEX ix_balance_net_debt_annual "
        "ON f_balance_sheets (net_debt) "
        "WHERE statement_type = 'annual'"
    )
    op.execute(
        "CREATE INDEX ix_balance_stockholders_equity_annual "
        "ON f_balance_sheets (stockholders_equity) "
        "WHERE statement_type = 'annual'"
    )

    # ── 3. f_cash_flows ───────────────────────────────────────────────────
    op.create_table(
        "f_cash_flows",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("in_equity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("statement_type", sa.Text(), nullable=False),
        sa.Column("period", sa.Date(), nullable=False),
        # ── Cash-flow metrics ───────────────────────────────────────────
        sa.Column("operating_cash_flow", sa.Numeric(), nullable=True),
        sa.Column("net_income_from_continuing_ops", sa.Numeric(), nullable=True),
        sa.Column("depreciation_and_amortization", sa.Numeric(), nullable=True),
        sa.Column("change_in_working_capital", sa.Numeric(), nullable=True),
        sa.Column("change_in_receivables", sa.Numeric(), nullable=True),
        sa.Column("change_in_inventory", sa.Numeric(), nullable=True),
        sa.Column("change_in_payable", sa.Numeric(), nullable=True),
        sa.Column("investing_cash_flow", sa.Numeric(), nullable=True),
        sa.Column("capital_expenditure", sa.Numeric(), nullable=True),
        sa.Column("capital_expenditure_reported", sa.Numeric(), nullable=True),
        sa.Column("purchase_of_ppe", sa.Numeric(), nullable=True),
        sa.Column("sale_of_ppe", sa.Numeric(), nullable=True),
        sa.Column("purchase_of_investment", sa.Numeric(), nullable=True),
        sa.Column("sale_of_investment", sa.Numeric(), nullable=True),
        sa.Column("financing_cash_flow", sa.Numeric(), nullable=True),
        sa.Column("net_issuance_payments_of_debt", sa.Numeric(), nullable=True),
        sa.Column("long_term_debt_issuance", sa.Numeric(), nullable=True),
        sa.Column("long_term_debt_payments", sa.Numeric(), nullable=True),
        sa.Column("common_stock_issuance", sa.Numeric(), nullable=True),
        sa.Column("cash_dividends_paid", sa.Numeric(), nullable=True),
        sa.Column("free_cash_flow", sa.Numeric(), nullable=True),
        sa.Column("changes_in_cash", sa.Numeric(), nullable=True),
        sa.Column("end_cash_position", sa.Numeric(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["in_equity_id"],
            ["in_equities.id"],
            name="fk_f_cash_flows_in_equity_id",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "in_equity_id", "statement_type", "period",
            name="uq_cashflow_equity_type_period",
        ),
    )

    op.create_index(
        "ix_cashflow_equity_type_period",
        "f_cash_flows",
        ["in_equity_id", "statement_type", "period"],
    )
    op.execute(
        "CREATE INDEX ix_cashflow_free_cash_flow_annual "
        "ON f_cash_flows (free_cash_flow) "
        "WHERE statement_type = 'annual'"
    )
    op.execute(
        "CREATE INDEX ix_cashflow_operating_cash_flow_annual "
        "ON f_cash_flows (operating_cash_flow) "
        "WHERE statement_type = 'annual'"
    )

    # ── 4. Migrate data from JSONB table ──────────────────────────────────

    # Income statements (statement_type IN ('annual', 'quarterly'))
    op.execute(
        f"""
        INSERT INTO f_income_statements
            (in_equity_id, statement_type, period,
             total_revenue, cost_of_revenue, gross_profit, operating_expense,
             operating_income, ebitda, interest_expense, tax_provision,
             pretax_income, net_income, basic_eps, diluted_eps, total_expenses)
        SELECT
            in_equity_id,
            statement_type,
            period,
            {_coalesce('TotalRevenue',       'Total Revenue')},
            {_coalesce('CostOfRevenue',      'Cost Of Revenue')},
            {_coalesce('GrossProfit',        'Gross Profit')},
            {_coalesce('OperatingExpense',   'Operating Expense')},
            {_coalesce('OperatingIncome',    'Operating Income')},
            {_coalesce('EBITDA',             'Ebitda')},
            {_coalesce('InterestExpense',    'Interest Expense')},
            {_coalesce('TaxProvision',       'Tax Provision')},
            {_coalesce('PretaxIncome',       'Pretax Income')},
            {_coalesce('NetIncome',          'Net Income')},
            {_coalesce('BasicEPS',           'Basic EPS')},
            {_coalesce('DilutedEPS',         'Diluted EPS')},
            {_coalesce('TotalExpenses',      'Total Expenses')}
        FROM f_financial_statements
        WHERE statement_type IN ('annual', 'quarterly')
        ON CONFLICT (in_equity_id, statement_type, period) DO NOTHING
        """
    )

    # Balance sheets (statement_type IN ('annual_balance', 'quarterly_balance'))
    op.execute(
        f"""
        INSERT INTO f_balance_sheets
            (in_equity_id, statement_type, period,
             total_assets, current_assets, cash_and_cash_equivalents,
             accounts_receivable, inventory, net_ppe, total_non_current_assets,
             goodwill, total_liabilities, current_liabilities, current_debt,
             accounts_payable, long_term_debt, total_debt, stockholders_equity,
             common_stock_equity, retained_earnings, working_capital, net_debt)
        SELECT
            in_equity_id,
            CASE statement_type
                WHEN 'annual_balance'    THEN 'annual'
                WHEN 'quarterly_balance' THEN 'quarterly'
            END,
            period,
            {_coalesce('TotalAssets',                          'Total Assets')},
            {_coalesce('CurrentAssets',                        'Current Assets')},
            {_coalesce('CashAndCashEquivalents',               'Cash And Cash Equivalents')},
            {_coalesce('AccountsReceivable',                   'Accounts Receivable')},
            {_coalesce('Inventory',                            'Inventory')},
            {_coalesce('NetPPE',                               'Net PPE')},
            {_coalesce('TotalNonCurrentAssets',                'Total Non Current Assets')},
            {_coalesce('Goodwill',                             'Goodwill')},
            {_coalesce('TotalLiabilitiesNetMinorityInterest',  'Total Liabilities Net Minority Interest')},
            {_coalesce('CurrentLiabilities',                   'Current Liabilities')},
            {_coalesce('CurrentDebt',                          'Current Debt')},
            {_coalesce('AccountsPayable',                      'Accounts Payable')},
            {_coalesce('LongTermDebt',                         'Long Term Debt')},
            {_coalesce('TotalDebt',                            'Total Debt')},
            {_coalesce('StockholdersEquity',                   'Stockholders Equity')},
            {_coalesce('CommonStockEquity',                    'Common Stock Equity')},
            {_coalesce('RetainedEarnings',                     'Retained Earnings')},
            {_coalesce('WorkingCapital',                       'Working Capital')},
            {_coalesce('NetDebt',                              'Net Debt')}
        FROM f_financial_statements
        WHERE statement_type IN ('annual_balance', 'quarterly_balance')
        ON CONFLICT (in_equity_id, statement_type, period) DO NOTHING
        """
    )

    # Cash flows (statement_type IN ('annual_cashflow', 'quarterly_cashflow'))
    op.execute(
        f"""
        INSERT INTO f_cash_flows
            (in_equity_id, statement_type, period,
             operating_cash_flow, net_income_from_continuing_ops,
             depreciation_and_amortization, change_in_working_capital,
             change_in_receivables, change_in_inventory, change_in_payable,
             investing_cash_flow, capital_expenditure, capital_expenditure_reported,
             purchase_of_ppe, sale_of_ppe, purchase_of_investment, sale_of_investment,
             financing_cash_flow, net_issuance_payments_of_debt,
             long_term_debt_issuance, long_term_debt_payments,
             common_stock_issuance, cash_dividends_paid,
             free_cash_flow, changes_in_cash, end_cash_position)
        SELECT
            in_equity_id,
            CASE statement_type
                WHEN 'annual_cashflow'    THEN 'annual'
                WHEN 'quarterly_cashflow' THEN 'quarterly'
            END,
            period,
            {_coalesce('OperatingCashFlow',              'Operating Cash Flow')},
            {_coalesce('NetIncomeFromContinuingOperations', 'Net Income From Continuing Operations')},
            {_coalesce('DepreciationAndAmortization',    'Depreciation And Amortization')},
            {_coalesce('ChangeInWorkingCapital',         'Change In Working Capital')},
            {_coalesce('ChangeInReceivables',            'Change In Receivables')},
            {_coalesce('ChangeInInventory',              'Change In Inventory')},
            {_coalesce('ChangeInPayable',                'Change In Payable')},
            {_coalesce('InvestingCashFlow',              'Investing Cash Flow')},
            {_coalesce('CapitalExpenditure',             'Capital Expenditure')},
            {_coalesce('CapitalExpenditureReported',     'Capital Expenditure Reported')},
            {_coalesce('PurchaseOfPPE',                  'Purchase Of PPE')},
            {_coalesce('SaleOfPPE',                      'Sale Of PPE')},
            {_coalesce('PurchaseOfInvestment',           'Purchase Of Investment')},
            {_coalesce('SaleOfInvestment',               'Sale Of Investment')},
            {_coalesce('FinancingCashFlow',              'Financing Cash Flow')},
            {_coalesce('NetIssuancePaymentsOfDebt',      'Net Issuance Payments Of Debt')},
            {_coalesce('LongTermDebtIssuance',           'Long Term Debt Issuance')},
            {_coalesce('LongTermDebtPayments',           'Long Term Debt Payments')},
            {_coalesce('CommonStockIssuance',            'Common Stock Issuance')},
            {_coalesce('CashDividendsPaid',              'Cash Dividends Paid')},
            {_coalesce('FreeCashFlow',                   'Free Cash Flow')},
            {_coalesce('ChangesInCash',                  'Changes In Cash')},
            {_coalesce('EndCashPosition',                'End Cash Position')}
        FROM f_financial_statements
        WHERE statement_type IN ('annual_cashflow', 'quarterly_cashflow')
        ON CONFLICT (in_equity_id, statement_type, period) DO NOTHING
        """
    )

    # ── 5. Drop the old JSONB table ───────────────────────────────────────
    op.execute("DROP INDEX IF EXISTS ix_fin_data_gin")
    op.execute("DROP INDEX IF EXISTS ix_fin_equity_type_period")
    op.drop_constraint(
        "uq_fin_equity_type_period",
        "f_financial_statements",
        type_="unique",
    )
    op.drop_constraint(
        "fk_f_financial_statements_in_equity_id_in_equities",
        "f_financial_statements",
        type_="foreignkey",
    )
    op.drop_table("f_financial_statements")


# ---------------------------------------------------------------------------
# downgrade
# ---------------------------------------------------------------------------

def downgrade() -> None:
    # Drop new typed tables (data loss — reload from CSV if needed)
    op.execute("DROP INDEX IF EXISTS ix_cashflow_operating_cash_flow_annual")
    op.execute("DROP INDEX IF EXISTS ix_cashflow_free_cash_flow_annual")
    op.drop_index("ix_cashflow_equity_type_period", table_name="f_cash_flows")
    op.drop_table("f_cash_flows")

    op.execute("DROP INDEX IF EXISTS ix_balance_stockholders_equity_annual")
    op.execute("DROP INDEX IF EXISTS ix_balance_net_debt_annual")
    op.execute("DROP INDEX IF EXISTS ix_balance_total_debt_annual")
    op.execute("DROP INDEX IF EXISTS ix_balance_total_assets_annual")
    op.drop_index("ix_balance_equity_type_period", table_name="f_balance_sheets")
    op.drop_table("f_balance_sheets")

    op.execute("DROP INDEX IF EXISTS ix_income_basic_eps_annual")
    op.execute("DROP INDEX IF EXISTS ix_income_ebitda_annual")
    op.execute("DROP INDEX IF EXISTS ix_income_total_revenue_annual")
    op.execute("DROP INDEX IF EXISTS ix_income_net_income_annual")
    op.drop_index("ix_income_equity_type_period", table_name="f_income_statements")
    op.drop_table("f_income_statements")

    # Recreate the original JSONB table (empty — reload data from CSV)
    op.create_table(
        "f_financial_statements",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("in_equity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("statement_type", sa.Text(), nullable=False),
        sa.Column("period", sa.Date(), nullable=False),
        sa.Column("data", postgresql.JSONB(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["in_equity_id"],
            ["in_equities.id"],
            name="fk_f_financial_statements_in_equity_id_in_equities",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "in_equity_id", "statement_type", "period",
            name="uq_fin_equity_type_period",
        ),
    )
    op.create_index(
        "ix_fin_equity_type_period",
        "f_financial_statements",
        ["in_equity_id", "statement_type", "period"],
    )
    op.execute(
        "CREATE INDEX ix_fin_data_gin ON f_financial_statements USING gin(data)"
    )
