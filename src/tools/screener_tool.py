"""Deterministic stock screen using only BOTH_FUNCTIONS ∪ SCREENER_FUNCTIONS from yfinance_wrappers."""

from __future__ import annotations

import asyncio
import math
from typing import Any

from langchain_core.tools import tool
from sqlalchemy import text

from src.core.db import SessionLocal
from src.schemas.screener_tool_schemas import (
    MediumScreenerParamConfig,
    ScreenOneResult,
    ScreenerCriteria,
    ScreenerRunRequest,
    ScreenerToolInput,
)
from src.tools.yfinance_wrappers import BOTH_FUNCTIONS, SCREENER_FUNCTIONS
from src.tools.yfinance_wrappers import (
    get_balance_sheet,
    get_earnings_estimate,
    get_income_statement,
    get_revenue_estimate,
    get_ticker_info,
)

# Allowed API surface for this tool: wrappers in BOTH_FUNCTIONS | SCREENER_FUNCTIONS only.
_ALLOWED_WRAPPERS = BOTH_FUNCTIONS | SCREENER_FUNCTIONS
assert {
    "get_ticker_info",
    "get_balance_sheet",
    "get_income_statement",
    "get_earnings_estimate",
    "get_revenue_estimate",
} <= _ALLOWED_WRAPPERS

_MEDIUM_PARAM_CONFIG = MediumScreenerParamConfig()
_MEDIUM_DEFAULTS: dict[str, Any] = _MEDIUM_PARAM_CONFIG.default_values()


def enabled_medium_hitl_param_names() -> tuple[str, ...]:
    """Screener params that should be rendered in the HITL form."""
    return _MEDIUM_PARAM_CONFIG.enabled_fields()


def _build_screener_request_from_values(values: dict[str, Any]) -> ScreenerRunRequest:
    enabled_fields = set(enabled_medium_hitl_param_names())
    return ScreenerRunRequest.from_values(
        values,
        enabled_fields=enabled_fields,
    )


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


def _latest_period_row(statement: dict[str, Any]) -> dict[str, Any]:
    if not statement:
        return {}
    for key in sorted(statement.keys(), reverse=True):
        row = statement[key]
        if isinstance(row, dict) and row:
            return row
    return {}


def _dict_only(x: Any) -> dict[str, Any]:
    """Avoid ``x or {}`` when *x* may be a pandas DataFrame (ambiguous truth value)."""
    return x if isinstance(x, dict) else {}


def _estimate_growth_pct(estimate_blob: dict[str, Any]) -> float | None:
    if not estimate_blob:
        return None
    # yfinance as_dict shape: top-level "growth" -> { "0y": 0.11, "+1y": ... }
    g_top = estimate_blob.get("growth")
    if isinstance(g_top, dict):
        for v in g_top.values():
            if v is not None:
                return _growth_to_pct(v)
        return None
    for _k, v in estimate_blob.items():
        if isinstance(v, dict):
            g = v.get("growth")
            if g is not None:
                return _growth_to_pct(g)
    return None


async def _load_all_equity_symbols() -> list[str]:
    """Load all equities from `in_equities` and map to Yahoo `.NS` symbols."""
    async with SessionLocal() as session:
        result = await session.execute(text("SELECT symbol FROM in_equities ORDER BY symbol"))
        symbols: list[str] = []
        for row in result:
            raw = row[0]
            if not raw or not isinstance(raw, str):
                continue
            sym = raw.strip().upper()
            if not sym:
                continue
            symbols.append(sym if sym.endswith(".NS") else f"{sym}.NS")
    return list(dict.fromkeys(symbols))


def _apply_growth_filters(
    symbol: str,
    info: dict[str, Any],
    criteria: ScreenerCriteria,
    snap: dict[str, Any],
    reasons: list[str],
) -> tuple[float | None, float | None]:
    """Populate growth metrics and apply growth thresholds."""
    rev_g = _growth_to_pct(info.get("revenueGrowth"))
    eps_g_info = _growth_to_pct(info.get("earningsGrowth"))
    snap["revenue_growth_pct"] = rev_g
    snap["eps_growth_pct"] = eps_g_info

    if rev_g is None:
        rev_est = _dict_only(get_revenue_estimate(symbol).get("revenue_estimate"))
        rev_g = _estimate_growth_pct(rev_est)
        snap["revenue_growth_pct"] = rev_g

    if eps_g_info is None:
        earn_est = _dict_only(get_earnings_estimate(symbol).get("earnings_estimate"))
        eps_g_info = _estimate_growth_pct(earn_est)
        snap["eps_growth_pct"] = eps_g_info

    if criteria.revenue_growth_yoy_min_pct is not None:
        if rev_g is None:
            reasons.append("revenue_growth_missing")
        elif rev_g < criteria.revenue_growth_yoy_min_pct:
            reasons.append(f"revenue_growth<{criteria.revenue_growth_yoy_min_pct}")

    if criteria.eps_growth_yoy_min_pct is not None:
        if eps_g_info is None:
            reasons.append("eps_growth_missing")
        elif eps_g_info < criteria.eps_growth_yoy_min_pct:
            reasons.append(f"eps_growth<{criteria.eps_growth_yoy_min_pct}")

    return rev_g, eps_g_info


def _apply_valuation_filters(
    info: dict[str, Any],
    criteria: ScreenerCriteria,
    snap: dict[str, Any],
    reasons: list[str],
    eps_g_info: float | None,
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
    if pe is not None and eps_g_info is not None and eps_g_info > 0:
        peg = pe / eps_g_info
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


def _load_statement_context(symbol: str) -> tuple[dict[str, Any], dict[str, Any]]:
    """Load latest income/balance-sheet rows for statement-derived metrics."""
    inc = _dict_only(get_income_statement(symbol, freq="yearly").get("income_statement"))
    bs = _dict_only(get_balance_sheet(symbol, freq="yearly").get("balance_sheet"))
    return _latest_period_row(inc), _latest_period_row(bs)


def _apply_profitability_filters(
    info: dict[str, Any],
    criteria: ScreenerCriteria,
    snap: dict[str, Any],
    reasons: list[str],
    latest_i: dict[str, Any],
    latest_b: dict[str, Any],
) -> tuple[float | None, float | None]:
    """Apply EV/EBITDA, ROE, ROIC and operating-margin filters."""
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

    td = _f(latest_b.get("TotalDebt"))
    eq = _f(latest_b.get("StockholdersEquity"))
    cash = _f(latest_b.get("CashAndCashEquivalents"))
    oi = _f(latest_i.get("OperatingIncome"))
    interest = _f(latest_i.get("InterestExpense"))

    invested = None
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


def _screen_one(symbol: str, criteria: ScreenerCriteria) -> ScreenOneResult:
    """Screen one symbol and return a typed screening result."""
    reasons: list[str] = []
    snap: dict[str, Any] = {"symbol": symbol}

    info = get_ticker_info(symbol)
    if info.get("error"):
        return ScreenOneResult(
            passed=False,
            snapshot=snap,
            reasons=[f"ticker_info_error:{info.get('error')}"],
        )

    _, eps_g_info = _apply_growth_filters(symbol, info, criteria, snap, reasons)
    _apply_valuation_filters(info, criteria, snap, reasons, eps_g_info)
    latest_i, latest_b = _load_statement_context(symbol)
    oi, interest = _apply_profitability_filters(info, criteria, snap, reasons, latest_i, latest_b)
    _apply_balance_sheet_filters(info, criteria, snap, reasons, oi, interest)
    _apply_market_filters(info, criteria, snap, reasons)

    return ScreenOneResult(passed=(len(reasons) == 0), snapshot=snap, reasons=reasons)


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


def run_get_screened_stocks_sync(
    symbols: list[str],
    request: ScreenerRunRequest,
) -> str:
    notes: list[str] = []
    if not symbols:
        return "ERROR: No symbols available to screen."

    passed: list[dict[str, Any]] = []
    for sym in symbols:
        if len(passed) >= request.max_results:
            break
        result = _screen_one(sym.strip(), request.criteria)
        if result.passed:
            passed.append(result.snapshot)
        elif result.reasons and "ticker_info_error" not in result.reasons[0]:
            notes.append(f"{sym}: {', '.join(result.reasons[:3])}")

    return _format_result(passed, request.universe_hint, notes[:50])


@tool("get_screened_stocks", args_schema=ScreenerToolInput)
async def get_screened_stocks(**kwargs: Any) -> str:
    """Return stocks passing quantitative filters.

    Threshold defaults match a **medium profit / medium risk** (balanced quality + growth)
    style screen. There is **no** risk-profile parameter — adjust any numeric arg to tune.
    Symbols are loaded from `in_equities` and screened against current thresholds.

    Uses only yfinance wrapper functions in ``BOTH_FUNCTIONS | SCREENER_FUNCTIONS``.
    """
    symbols = await _load_all_equity_symbols()
    if not symbols:
        return "ERROR: No equities found in in_equities table."
    request = _build_screener_request_from_values(kwargs)
    return await asyncio.to_thread(
        run_get_screened_stocks_sync,
        symbols,
        request,
    )
