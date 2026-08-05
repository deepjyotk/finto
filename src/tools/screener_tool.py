"""Deterministic stock screen using data from the database.

All financial data (ticker info, income statements, balance sheets) is loaded
in bulk from the database rather than fetched per-symbol via yfinance.

Data sources
------------
  in_equities.company_metadata  — yfinance-style info snapshot (PE, beta, etc.)
  f_income_statements            — typed annual rows (revenue, EBITDA, EPS, …)
  f_balance_sheets               — typed annual rows (debt, equity, cash, …)
"""

from __future__ import annotations

import asyncio
import math
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from langchain_core.tools import tool

from src.core.db import SessionLocal
from src.repositories.screener_repo import ScreenerRepo
from src.schemas.screener_tool_schemas.base import BaseScreenerForm, ScreenerFormField
from src.schemas.screener_tool_schemas.screener_tool_schema_medium import (
    ScreenerCriteria,
    ScreenerRunRequest,
    ScreenerToolInput,
    ScreenOneResult,
)

# ---------------------------------------------------------------------------
# Category form → normalized criteria mapping
# ---------------------------------------------------------------------------

_CATEGORY_TO_CRITERIA: dict[str, str] = {
    "roe_pct_min": "roe_min_pct",
    "roic_pct_min": "roic_min_pct",
    "operating_margin_pct_min": "operating_margin_min_pct",
    "revenue_growth_pct_min": "revenue_growth_yoy_min_pct",
    "market_cap_min": "market_cap_min_usd",
    "min_inr": "market_cap_min_inr",
    "max_inr": "market_cap_max_inr",
    "dividend_yield_pct_min": "dividend_yield_min_pct",
    "payout_ratio_pct_max": "payout_ratio_max_pct",
}

_CRITERIA_SKIP_FIELDS = frozenset(
    {
        "roe_pct_max",
        "roic_pct_max",
        "operating_margin_pct_max",
        "revenue_growth_pct_max",
        "debt_to_equity_min",
        "interest_coverage_max",
        "current_ratio_max",
        "dividend_yield_pct_max",
        "payout_ratio_pct_min",
        "market_cap_max",
        "pb_min",
        "ps_min",
        "sectors",
        "industry",
        "country",
        "exchange",
        "market_region",
        "style",
        "sensitivity_type",
        "market_category",
        "_intent",
    }
)

_SCREEN_CONCURRENCY = 32

StatementRowsByEquity = dict[UUID, list[dict[str, Any]]]


def _build_screener_request_from_values(values: dict[str, Any]) -> ScreenerRunRequest:
    return ScreenerRunRequest.from_values(values)


def build_screener_request_from_form(form: BaseScreenerForm) -> ScreenerRunRequest:
    """Convert a typed HITL category form into the normalized screener request."""
    values: dict[str, Any] = {}

    for field_name in form.__class__.model_fields:
        if field_name in _CRITERIA_SKIP_FIELDS:
            continue

        field_model = getattr(form, field_name, None)
        if not isinstance(field_model, ScreenerFormField):
            continue
        if field_model.value is None:
            continue

        criteria_key = _CATEGORY_TO_CRITERIA.get(field_name, field_name)
        values[criteria_key] = field_model.value

    return ScreenerRunRequest.from_values(values)


# ---------------------------------------------------------------------------
# Per-symbol data bundle (pre-loaded from DB before screening loop)
# ---------------------------------------------------------------------------


@dataclass
class EquityScreenData:
    """All data needed to screen one equity, loaded from DB in bulk."""

    symbol_ns: str
    info: dict[str, Any] = field(default_factory=dict)
    income_rows: list[dict[str, Any]] = field(default_factory=list)
    """Latest 2 annual income rows, newest first. Each row: {"data": {display_name: float}}."""
    balance_rows: list[dict[str, Any]] = field(default_factory=list)
    """Latest 1 annual balance row. Each row: {"data": {display_name: float}}."""


# ---------------------------------------------------------------------------
# Scalar helpers
# ---------------------------------------------------------------------------


def _f(x: Any) -> float | None:
    if x is None:
        return None
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        return None
    return v


def _growth_to_pct(raw: Any) -> float | None:
    """Yahoo often returns fractional growth (0.15) or percent-like values."""
    g = _f(raw)
    if g is None:
        return None
    if -1.0 < g < 1.0:
        return g * 100.0
    return g


def _yoy_growth_pct(new_val: float | None, old_val: float | None) -> float | None:
    """Compute year-over-year growth % from two consecutive period values."""
    if new_val is None or old_val is None or old_val == 0:
        return None
    return ((new_val - old_val) / abs(old_val)) * 100.0


# ---------------------------------------------------------------------------
# Statement context extraction (from pre-loaded DB rows)
# ---------------------------------------------------------------------------


def _extract_statement_context(data: EquityScreenData) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return the latest income and balance-sheet data dicts from pre-loaded DB rows.

    The dicts use display names matching _INCOME_DISPLAY / _BALANCE_DISPLAY
    (e.g. "Operating Income", "Total Debt") — NOT yfinance camelCase.
    """
    latest_i = data.income_rows[0]["data"] if data.income_rows else {}
    latest_b = data.balance_rows[0]["data"] if data.balance_rows else {}
    return latest_i, latest_b


# ---------------------------------------------------------------------------
# Filter helpers — each mutates `snap` and appends to `reasons`
# ---------------------------------------------------------------------------


def _apply_growth_filters(
    data: EquityScreenData,
    criteria: ScreenerCriteria,
    snap: dict[str, Any],
    reasons: list[str],
) -> tuple[float | None, float | None]:
    """Populate growth metrics and apply growth thresholds.

    Priority:
    1. company_metadata.revenueGrowth / earningsGrowth (pre-computed by yfinance)
    2. Fallback: compute YoY from the latest 2 annual DB income rows
    """
    info = data.info
    income_rows = data.income_rows

    rev_g = _growth_to_pct(info.get("revenueGrowth"))
    eps_g = _growth_to_pct(info.get("earningsGrowth"))

    # Fallback: compute YoY from DB income rows when metadata lacks the value
    if rev_g is None and len(income_rows) >= 2:
        r1 = _f(income_rows[0]["data"].get("Total Revenue"))
        r0 = _f(income_rows[1]["data"].get("Total Revenue"))
        rev_g = _yoy_growth_pct(r1, r0)

    if eps_g is None and len(income_rows) >= 2:
        e1 = _f(income_rows[0]["data"].get("Basic EPS"))
        e0 = _f(income_rows[1]["data"].get("Basic EPS"))
        eps_g = _yoy_growth_pct(e1, e0)

    snap["revenue_growth_pct"] = rev_g
    snap["eps_growth_pct"] = eps_g

    if criteria.revenue_growth_yoy_min_pct is not None:
        if rev_g is None:
            reasons.append("revenue_growth_missing")
        elif rev_g < criteria.revenue_growth_yoy_min_pct:
            reasons.append(f"revenue_growth<{criteria.revenue_growth_yoy_min_pct}")

    if criteria.eps_growth_yoy_min_pct is not None:
        if eps_g is None:
            reasons.append("eps_growth_missing")
        elif eps_g < criteria.eps_growth_yoy_min_pct:
            reasons.append(f"eps_growth<{criteria.eps_growth_yoy_min_pct}")

    return rev_g, eps_g


def _apply_valuation_filters(
    info: dict[str, Any],
    criteria: ScreenerCriteria,
    snap: dict[str, Any],
    reasons: list[str],
    eps_g: float | None,
) -> None:
    """Populate valuation metrics and apply valuation thresholds."""
    pe = _f(info.get("trailingPE"))
    if pe is None:
        pe = _f(info.get("forwardPE"))
    snap["pe"] = pe
    if criteria.pe_min is not None and pe is not None and pe < criteria.pe_min:
        reasons.append(f"pe<{criteria.pe_min}")
    if criteria.pe_max is not None and pe is not None and pe > criteria.pe_max:
        reasons.append(f"pe>{criteria.pe_max}")

    peg: float | None = None
    if pe is not None and eps_g is not None and eps_g > 0:
        peg = pe / eps_g
    snap["peg"] = peg
    if criteria.peg_min is not None or criteria.peg_max is not None:
        if peg is None:
            reasons.append("peg_undef")
        else:
            if criteria.peg_min is not None and peg < criteria.peg_min:
                reasons.append(f"peg<{criteria.peg_min}")
            if criteria.peg_max is not None and peg > criteria.peg_max:
                reasons.append(f"peg>{criteria.peg_max}")

    pb = _f(info.get("priceToBook"))
    snap["pb"] = pb
    if criteria.pb_max is not None and pb is not None and pb > criteria.pb_max:
        reasons.append(f"pb>{criteria.pb_max}")

    ps = _f(info.get("priceToSalesTrailing12Months"))
    snap["ps"] = ps
    if criteria.ps_max is not None and ps is not None and ps > criteria.ps_max:
        reasons.append(f"ps>{criteria.ps_max}")


def _apply_profitability_filters(
    info: dict[str, Any],
    criteria: ScreenerCriteria,
    snap: dict[str, Any],
    reasons: list[str],
    latest_i: dict[str, Any],
    latest_b: dict[str, Any],
) -> tuple[float | None, float | None]:
    """Apply EV/EBITDA, ROE, ROIC and operating-margin filters.

    Statement keys use display names (e.g. "Operating Income", not "OperatingIncome").
    """
    ev = _f(info.get("enterpriseValue"))
    ebitda = _f(latest_i.get("EBITDA"))
    ev_ebitda: float | None = None
    if ev is not None and ebitda is not None and ebitda > 0:
        ev_ebitda = ev / ebitda
    snap["ev_ebitda"] = ev_ebitda
    if criteria.ev_ebitda_max is not None:
        if ev_ebitda is None:
            reasons.append("ev_ebitda_missing")
        elif ev_ebitda > criteria.ev_ebitda_max:
            reasons.append(f"ev_ebitda>{criteria.ev_ebitda_max}")

    roe = _f(info.get("returnOnEquity"))
    if roe is not None and -1 < roe < 1:
        roe *= 100.0
    snap["roe_pct"] = roe
    if criteria.roe_min_pct is not None:
        if roe is None:
            reasons.append("roe_missing")
        elif roe < criteria.roe_min_pct:
            reasons.append(f"roe<{criteria.roe_min_pct}")

    # ROIC: operating_income / (total_debt + stockholders_equity - cash)
    td = _f(latest_b.get("Total Debt"))
    eq = _f(latest_b.get("Stockholders Equity"))
    cash = _f(latest_b.get("Cash And Cash Equivalents"))
    oi = _f(latest_i.get("Operating Income"))
    interest = _f(latest_i.get("Interest Expense"))

    invested: float | None = None
    if td is not None and eq is not None:
        invested = td + eq - (cash or 0.0)
    roic_pct: float | None = None
    if oi is not None and invested is not None and invested > 0:
        roic_pct = (oi / invested) * 100.0
    snap["roic_pct"] = roic_pct
    if criteria.roic_min_pct is not None:
        if roic_pct is None:
            reasons.append("roic_missing")
        elif roic_pct < criteria.roic_min_pct:
            reasons.append(f"roic<{criteria.roic_min_pct}")

    om = _f(info.get("operatingMargins"))
    if om is not None and -1 < om < 1:
        om *= 100.0
    snap["operating_margin_pct"] = om
    if criteria.operating_margin_min_pct is not None:
        if om is None:
            reasons.append("operating_margin_missing")
        elif om < criteria.operating_margin_min_pct:
            reasons.append(f"operating_margin<{criteria.operating_margin_min_pct}")

    return oi, interest


def _apply_balance_sheet_filters(
    info: dict[str, Any],
    criteria: ScreenerCriteria,
    snap: dict[str, Any],
    reasons: list[str],
    oi: float | None,
    interest: float | None,
) -> None:
    """Apply debt, coverage, and current-ratio thresholds."""
    dte = _f(info.get("debtToEquity"))
    snap["debt_to_equity"] = dte
    if criteria.debt_to_equity_max is not None:
        if dte is None:
            reasons.append("debt_to_equity_missing")
        elif dte > criteria.debt_to_equity_max:
            reasons.append(f"debt_to_equity>{criteria.debt_to_equity_max}")

    coverage: float | None = None
    if oi is not None and interest is not None and interest != 0:
        coverage = abs(oi / interest)
    snap["interest_coverage"] = coverage
    if criteria.interest_coverage_min is not None:
        if coverage is None:
            reasons.append("interest_coverage_missing")
        elif coverage < criteria.interest_coverage_min:
            reasons.append(f"interest_coverage<{criteria.interest_coverage_min}")

    cr = _f(info.get("currentRatio"))
    snap["current_ratio"] = cr
    if criteria.current_ratio_min is not None:
        if cr is None:
            reasons.append("current_ratio_missing")
        elif cr < criteria.current_ratio_min:
            reasons.append(f"current_ratio<{criteria.current_ratio_min}")


def _apply_market_filters(
    info: dict[str, Any],
    criteria: ScreenerCriteria,
    snap: dict[str, Any],
    reasons: list[str],
) -> None:
    """Apply market-cap, beta, dividend, and payout filters."""
    mcap = _f(info.get("marketCap"))
    snap["market_cap"] = mcap
    if criteria.market_cap_min_usd is not None:
        if mcap is None:
            reasons.append("market_cap_missing")
        elif mcap < criteria.market_cap_min_usd:
            reasons.append(f"market_cap<{criteria.market_cap_min_usd}")
    if criteria.market_cap_min_inr is not None:
        if mcap is None:
            reasons.append("market_cap_missing")
        elif mcap < criteria.market_cap_min_inr:
            reasons.append(f"market_cap_inr<{criteria.market_cap_min_inr}")
    if criteria.market_cap_max_inr is not None:
        if mcap is None:
            reasons.append("market_cap_missing")
        elif mcap > criteria.market_cap_max_inr:
            reasons.append(f"market_cap_inr>{criteria.market_cap_max_inr}")

    beta = _f(info.get("beta"))
    snap["beta"] = beta
    if criteria.beta_min is not None or criteria.beta_max is not None:
        if beta is None:
            reasons.append("beta_missing")
        else:
            if criteria.beta_min is not None and beta < criteria.beta_min:
                reasons.append(f"beta<{criteria.beta_min}")
            if criteria.beta_max is not None and beta > criteria.beta_max:
                reasons.append(f"beta>{criteria.beta_max}")

    dy = _f(info.get("dividendYield"))
    if dy is not None and dy <= 1.0:
        dy *= 100.0
    snap["dividend_yield_pct"] = dy
    if criteria.dividend_yield_min_pct is not None and criteria.dividend_yield_min_pct > 0:
        if dy is None:
            reasons.append("dividend_yield_missing")
        elif dy < criteria.dividend_yield_min_pct:
            reasons.append(f"dividend_yield<{criteria.dividend_yield_min_pct}")

    pr = _f(info.get("payoutRatio"))
    if pr is not None and pr <= 1.0:
        pr *= 100.0
    snap["payout_ratio_pct"] = pr
    if criteria.payout_ratio_max_pct is not None:
        if pr is None:
            reasons.append("payout_ratio_missing")
        elif pr > criteria.payout_ratio_max_pct:
            reasons.append(f"payout_ratio>{criteria.payout_ratio_max_pct}")


# ---------------------------------------------------------------------------
# Per-symbol screening
# ---------------------------------------------------------------------------


def _screen_one(data: EquityScreenData, criteria: ScreenerCriteria) -> ScreenOneResult:
    """Screen one equity using pre-loaded DB data and return a typed result."""
    reasons: list[str] = []
    snap: dict[str, Any] = {"symbol": data.symbol_ns}
    info = data.info

    if not info:
        return ScreenOneResult(
            passed=False,
            snapshot=snap,
            reasons=["no_company_metadata"],
        )

    _, eps_g = _apply_growth_filters(data, criteria, snap, reasons)
    _apply_valuation_filters(info, criteria, snap, reasons, eps_g)
    latest_i, latest_b = _extract_statement_context(data)
    oi, interest = _apply_profitability_filters(info, criteria, snap, reasons, latest_i, latest_b)
    _apply_balance_sheet_filters(info, criteria, snap, reasons, oi, interest)
    _apply_market_filters(info, criteria, snap, reasons)

    return ScreenOneResult(passed=(len(reasons) == 0), snapshot=snap, reasons=reasons)


# ---------------------------------------------------------------------------
# Result formatting
# ---------------------------------------------------------------------------


def _format_result(
    passed: list[dict[str, Any]],
    universe_hint: str | None,
    notes: list[str],
) -> str:
    lines = [
        "=== GET_SCREENED_STOCKS ===",
        f"universe_hint: {universe_hint or '(none)'}",
        f"pass_count: {len(passed)}",
    ]
    if notes:
        lines.append("notes:")
        for n in notes:
            lines.append(f"  - {n}")
    lines.append("=== PASSED ===")
    for row in passed:
        lines.append(str(row))
    return "\n".join(lines)


def _needs_income_rows(criteria: ScreenerCriteria) -> bool:
    return any(
        value is not None
        for value in (
            criteria.revenue_growth_yoy_min_pct,
            criteria.eps_growth_yoy_min_pct,
            criteria.ev_ebitda_max,
            criteria.roic_min_pct,
            criteria.interest_coverage_min,
        )
    )


def _needs_balance_rows(criteria: ScreenerCriteria) -> bool:
    return criteria.roic_min_pct is not None


async def _load_income_rows(equity_ids: list[UUID]) -> StatementRowsByEquity:
    async with SessionLocal() as session:
        return await ScreenerRepo(session).load_latest_income_rows(equity_ids, n_periods=2)


async def _load_balance_rows(equity_ids: list[UUID]) -> StatementRowsByEquity:
    async with SessionLocal() as session:
        return await ScreenerRepo(session).load_latest_balance_rows(equity_ids, n_periods=1)


async def _load_required_statement_rows(
    equity_ids: list[UUID],
    criteria: ScreenerCriteria,
) -> tuple[StatementRowsByEquity, StatementRowsByEquity]:
    load_income = _needs_income_rows(criteria)
    load_balance = _needs_balance_rows(criteria)

    if load_income and load_balance:
        income_map, balance_map = await asyncio.gather(
            _load_income_rows(equity_ids),
            _load_balance_rows(equity_ids),
        )
        return income_map, balance_map

    income_map = await _load_income_rows(equity_ids) if load_income else {}
    balance_map = await _load_balance_rows(equity_ids) if load_balance else {}
    return income_map, balance_map


async def _screen_equity_async(
    equity: dict[str, Any],
    request: ScreenerRunRequest,
    income_map: StatementRowsByEquity,
    balance_map: StatementRowsByEquity,
    semaphore: asyncio.Semaphore,
) -> ScreenOneResult:
    async with semaphore:
        eid: UUID = equity["id"]
        screen_data = EquityScreenData(
            symbol_ns=f"{equity['symbol']}.NS",
            info=equity["info"],
            income_rows=income_map.get(eid, []),
            balance_rows=balance_map.get(eid, []),
        )
        return await asyncio.to_thread(_screen_one, screen_data, request.criteria)


# ---------------------------------------------------------------------------
# Main async screener entry point
# ---------------------------------------------------------------------------


async def _run_get_screened_stocks_request_async(request: ScreenerRunRequest) -> str:
    """Run the deterministic screen against the DB universe.

    Loads equity metadata first, then fetches only statement tables required by
    the active criteria. Independent statement queries and per-equity screening
    are run concurrently with bounded fan-out.
    """
    async with SessionLocal() as session:
        repo = ScreenerRepo(session)

        equities = await repo.load_equities_with_metadata()
        if not equities:
            return "ERROR: No equities found in in_equities table."

    equity_ids: list[UUID] = [e["id"] for e in equities]
    income_map, balance_map = await _load_required_statement_rows(equity_ids, request.criteria)

    notes: list[str] = []
    passed: list[dict[str, Any]] = []
    semaphore = asyncio.Semaphore(_SCREEN_CONCURRENCY)
    results = await asyncio.gather(
        *(
            _screen_equity_async(equity, request, income_map, balance_map, semaphore)
            for equity in equities
        )
    )

    for result in results:
        if len(passed) >= request.max_results:
            break

        if result.passed:
            passed.append(result.snapshot)
        elif result.reasons and result.reasons[0] != "no_company_metadata":
            symbol_ns = result.snapshot.get("symbol", "(unknown)")
            notes.append(f"{symbol_ns}: {', '.join(result.reasons[:3])}")

    return _format_result(passed, request.universe_hint, notes[:50])


async def run_get_screened_stocks_async(form: BaseScreenerForm) -> str:
    """Run the deterministic screen from a typed HITL category form."""
    request = build_screener_request_from_form(form)
    return await _run_get_screened_stocks_request_async(request)


# ---------------------------------------------------------------------------
# LangChain tool definition
# ---------------------------------------------------------------------------


@tool("get_screened_stocks", args_schema=ScreenerToolInput)
async def get_screened_stocks(**kwargs: Any) -> str:
    """Return stocks passing quantitative filters.

    Threshold defaults match a **medium profit / medium risk** (balanced quality + growth)
    style screen. There is **no** risk-profile parameter — adjust any numeric arg to tune.
    Symbols are loaded from `in_equities` and screened against current thresholds.

    Uses financial data stored in the database (company_metadata, f_income_statements,
    f_balance_sheets) — no live yfinance calls during screening.
    """
    request = _build_screener_request_from_values(kwargs)
    return await _run_get_screened_stocks_request_async(request)
