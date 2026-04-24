"""Pydantic schemas for the ticker / stock profile page."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel


class StockSearchResult(BaseModel):
    symbol: str          # e.g. "RELIANCE"
    symbol_ns: str       # e.g. "RELIANCE.NS"
    company_name: str    # e.g. "Reliance Industries Limited"


class PricePoint(BaseModel):
    date: str
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: Optional[float] = None
    volume: Optional[int] = None


class StatementRow(BaseModel):
    """One metric row across all periods — wide format for the UI table."""
    metric: str
    values: dict[str, Optional[float]]   # period ISO string → value


class FinancialStatements(BaseModel):
    """Annual or quarterly P&L table ready for direct rendering."""
    statement_type: str          # 'annual' | 'quarterly'
    periods: list[str]           # ordered period ISO strings (newest last)
    rows: list[StatementRow]


class KeyRatio(BaseModel):
    label: str
    value: Optional[str] = None
    unit: Optional[str] = None   # '₹', '%', 'Cr.', etc.


class CompanyInfo(BaseModel):
    symbol: str
    symbol_ns: str
    company_name: str
    isin: Optional[str] = None
    sector: Optional[str] = None
    website: Optional[str] = None
    current_price: Optional[float] = None
    currency: str = "INR"
    exchange: str = "NSE"


class TickerResponse(BaseModel):
    company: CompanyInfo
    key_ratios: list[KeyRatio]
    price_history: list[PricePoint]              # for chart (default 1Y daily OHLCV)
    annual_pnl: FinancialStatements
    quarterly_pnl: FinancialStatements
    annual_balance_sheet: FinancialStatements
    quarterly_balance_sheet: FinancialStatements
    annual_cash_flow: FinancialStatements
    quarterly_cash_flow: FinancialStatements
    ticker_info: Optional[dict] = None           # raw Yahoo Finance info dict from f_ticker_info
