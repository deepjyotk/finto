"""Deterministic stock screen using only BOTH_FUNCTIONS ∪ SCREENER_FUNCTIONS from yfinance_wrappers."""

from __future__ import annotations

import asyncio
import math
from typing import Annotated, Any

from langchain_core.tools import tool
from langgraph.runtime import get_runtime

from src.schemas.agent_state import AgentContext
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

_MEDIUM_DEFAULTS: dict[str, Any] = {
    "pe_min": 12.0,
    "pe_max": 25.0,
    "peg_min": 0.8,
    "peg_max": 1.5,
    "pb_max": 5.0,
    "ps_max": 8.0,
    "ev_ebitda_max": 18.0,
    "roe_min_pct": 12.0,
    "roic_min_pct": 10.0,
    "operating_margin_min_pct": None,
    "revenue_growth_yoy_min_pct": 8.0,
    "eps_growth_yoy_min_pct": 8.0,
    "debt_to_equity_max": 1.0,
    "interest_coverage_min": 4.0,
    "current_ratio_min": 1.2,
    "market_cap_min_usd": 1_000_000_000.0,
    "beta_min": 0.9,
    "beta_max": 1.2,
    "dividend_yield_min_pct": 0.0,
    "payout_ratio_max_pct": 70.0,
    "max_results": 25,
}


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


def _screen_one(
    symbol: str,
    *,
    pe_min: float | None,
    pe_max: float | None,
    peg_min: float | None,
    peg_max: float | None,
    pb_max: float | None,
    ps_max: float | None,
    ev_ebitda_max: float | None,
    roe_min_pct: float | None,
    roic_min_pct: float | None,
    operating_margin_min_pct: float | None,
    revenue_growth_yoy_min_pct: float | None,
    eps_growth_yoy_min_pct: float | None,
    debt_to_equity_max: float | None,
    interest_coverage_min: float | None,
    current_ratio_min: float | None,
    market_cap_min_usd: float | None,
    beta_min: float | None,
    beta_max: float | None,
    dividend_yield_min_pct: float | None,
    payout_ratio_max_pct: float | None,
) -> tuple[bool, dict[str, Any], list[str]]:
    reasons: list[str] = []
    snap: dict[str, Any] = {"symbol": symbol}

    info = get_ticker_info(symbol)
    if info.get("error"):
        return False, snap, [f"ticker_info_error:{info.get('error')}"]

    pe = _f(info.get("trailingPE"))
    if pe is None:
        pe = _f(info.get("forwardPE"))
    snap["pe"] = pe
    if pe_min is not None and pe is not None and pe < pe_min:
        reasons.append(f"pe<{pe_min}")
    if pe_max is not None and pe is not None and pe > pe_max:
        reasons.append(f"pe>{pe_max}")

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
        eg = _estimate_growth_pct(earn_est)
        eps_g_info = eg
        snap["eps_growth_pct"] = eps_g_info

    if revenue_growth_yoy_min_pct is not None:
        if rev_g is None:
            reasons.append("revenue_growth_missing")
        elif rev_g < revenue_growth_yoy_min_pct:
            reasons.append(f"revenue_growth<{revenue_growth_yoy_min_pct}")

    if eps_growth_yoy_min_pct is not None:
        if eps_g_info is None:
            reasons.append("eps_growth_missing")
        elif eps_g_info < eps_growth_yoy_min_pct:
            reasons.append(f"eps_growth<{eps_growth_yoy_min_pct}")

    peg: float | None = None
    if pe is not None and eps_g_info is not None and eps_g_info > 0:
        peg = pe / eps_g_info
    snap["peg"] = peg
    if peg_min is not None or peg_max is not None:
        if peg is None:
            reasons.append("peg_undef")
        else:
            if peg_min is not None and peg < peg_min:
                reasons.append(f"peg<{peg_min}")
            if peg_max is not None and peg > peg_max:
                reasons.append(f"peg>{peg_max}")

    pb = _f(info.get("priceToBook"))
    snap["pb"] = pb
    if pb_max is not None and pb is not None and pb > pb_max:
        reasons.append(f"pb>{pb_max}")

    ps = _f(info.get("priceToSalesTrailing12Months"))
    snap["ps"] = ps
    if ps_max is not None and ps is not None and ps > ps_max:
        reasons.append(f"ps>{ps_max}")

    ev = _f(info.get("enterpriseValue"))
    inc = _dict_only(get_income_statement(symbol, freq="yearly").get("income_statement"))
    latest_i = _latest_period_row(inc)
    ebitda = _f(latest_i.get("EBITDA"))
    ev_ebitda: float | None = None
    if ev is not None and ebitda is not None and ebitda > 0:
        ev_ebitda = ev / ebitda
    snap["ev_ebitda"] = ev_ebitda
    if ev_ebitda_max is not None:
        if ev_ebitda is None:
            reasons.append("ev_ebitda_missing")
        elif ev_ebitda > ev_ebitda_max:
            reasons.append(f"ev_ebitda>{ev_ebitda_max}")

    roe = _f(info.get("returnOnEquity"))
    if roe is not None and -1 < roe < 1:
        roe *= 100.0
    snap["roe_pct"] = roe
    if roe_min_pct is not None:
        if roe is None:
            reasons.append("roe_missing")
        elif roe < roe_min_pct:
            reasons.append(f"roe<{roe_min_pct}")

    bs = _dict_only(get_balance_sheet(symbol, freq="yearly").get("balance_sheet"))
    latest_b = _latest_period_row(bs)
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
    if roic_min_pct is not None:
        if roic_pct is None:
            reasons.append("roic_missing")
        elif roic_pct < roic_min_pct:
            reasons.append(f"roic<{roic_min_pct}")

    om = _f(info.get("operatingMargins"))
    if om is not None and -1 < om < 1:
        om *= 100.0
    snap["operating_margin_pct"] = om
    if operating_margin_min_pct is not None:
        if om is None:
            reasons.append("operating_margin_missing")
        elif om < operating_margin_min_pct:
            reasons.append(f"operating_margin<{operating_margin_min_pct}")

    dte = _f(info.get("debtToEquity"))
    snap["debt_to_equity"] = dte
    if debt_to_equity_max is not None:
        if dte is None:
            reasons.append("debt_to_equity_missing")
        elif dte > debt_to_equity_max:
            reasons.append(f"debt_to_equity>{debt_to_equity_max}")

    coverage: float | None = None
    if oi is not None and interest is not None and interest != 0:
        coverage = abs(oi / interest)
    snap["interest_coverage"] = coverage
    if interest_coverage_min is not None:
        if coverage is None:
            reasons.append("interest_coverage_missing")
        elif coverage < interest_coverage_min:
            reasons.append(f"interest_coverage<{interest_coverage_min}")

    cr = _f(info.get("currentRatio"))
    snap["current_ratio"] = cr
    if current_ratio_min is not None:
        if cr is None:
            reasons.append("current_ratio_missing")
        elif cr < current_ratio_min:
            reasons.append(f"current_ratio<{current_ratio_min}")

    mcap = _f(info.get("marketCap"))
    snap["market_cap"] = mcap
    if market_cap_min_usd is not None:
        if mcap is None:
            reasons.append("market_cap_missing")
        elif mcap < market_cap_min_usd:
            reasons.append(f"market_cap<{market_cap_min_usd}")

    beta = _f(info.get("beta"))
    snap["beta"] = beta
    if beta_min is not None or beta_max is not None:
        if beta is None:
            reasons.append("beta_missing")
        else:
            if beta_min is not None and beta < beta_min:
                reasons.append(f"beta<{beta_min}")
            if beta_max is not None and beta > beta_max:
                reasons.append(f"beta>{beta_max}")

    dy = _f(info.get("dividendYield"))
    if dy is not None and dy <= 1.0:
        dy *= 100.0
    snap["dividend_yield_pct"] = dy
    if dividend_yield_min_pct is not None and dividend_yield_min_pct > 0:
        if dy is None:
            reasons.append("dividend_yield_missing")
        elif dy < dividend_yield_min_pct:
            reasons.append(f"dividend_yield<{dividend_yield_min_pct}")

    pr = _f(info.get("payoutRatio"))
    if pr is not None and pr <= 1.0:
        pr *= 100.0
    snap["payout_ratio_pct"] = pr
    if payout_ratio_max_pct is not None:
        if pr is None:
            reasons.append("payout_ratio_missing")
        elif pr > payout_ratio_max_pct:
            reasons.append(f"payout_ratio>{payout_ratio_max_pct}")

    return (len(reasons) == 0), snap, reasons


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
    candidate_symbols: list[str],
    *,
    pe_min: float | None = _MEDIUM_DEFAULTS["pe_min"],
    pe_max: float | None = _MEDIUM_DEFAULTS["pe_max"],
    peg_min: float | None = _MEDIUM_DEFAULTS["peg_min"],
    peg_max: float | None = _MEDIUM_DEFAULTS["peg_max"],
    pb_max: float | None = _MEDIUM_DEFAULTS["pb_max"],
    ps_max: float | None = _MEDIUM_DEFAULTS["ps_max"],
    ev_ebitda_max: float | None = _MEDIUM_DEFAULTS["ev_ebitda_max"],
    roe_min_pct: float | None = _MEDIUM_DEFAULTS["roe_min_pct"],
    roic_min_pct: float | None = _MEDIUM_DEFAULTS["roic_min_pct"],
    operating_margin_min_pct: float | None = _MEDIUM_DEFAULTS["operating_margin_min_pct"],
    revenue_growth_yoy_min_pct: float | None = _MEDIUM_DEFAULTS["revenue_growth_yoy_min_pct"],
    eps_growth_yoy_min_pct: float | None = _MEDIUM_DEFAULTS["eps_growth_yoy_min_pct"],
    debt_to_equity_max: float | None = _MEDIUM_DEFAULTS["debt_to_equity_max"],
    interest_coverage_min: float | None = _MEDIUM_DEFAULTS["interest_coverage_min"],
    current_ratio_min: float | None = _MEDIUM_DEFAULTS["current_ratio_min"],
    market_cap_min_usd: float | None = _MEDIUM_DEFAULTS["market_cap_min_usd"],
    beta_min: float | None = _MEDIUM_DEFAULTS["beta_min"],
    beta_max: float | None = _MEDIUM_DEFAULTS["beta_max"],
    dividend_yield_min_pct: float | None = _MEDIUM_DEFAULTS["dividend_yield_min_pct"],
    payout_ratio_max_pct: float | None = _MEDIUM_DEFAULTS["payout_ratio_max_pct"],
    max_results: int = _MEDIUM_DEFAULTS["max_results"],
    universe_hint: str | None = None,
) -> str:
    notes: list[str] = []
    if not candidate_symbols:
        return (
            "ERROR: No candidate symbols to screen. "
            "The screener node must set screener_candidate_symbols on AgentContext before calling get_screened_stocks."
        )

    passed: list[dict[str, Any]] = []
    for sym in candidate_symbols:
        if len(passed) >= max_results:
            break
        ok, snap, reasons = _screen_one(
            sym.strip(),
            pe_min=pe_min,
            pe_max=pe_max,
            peg_min=peg_min,
            peg_max=peg_max,
            pb_max=pb_max,
            ps_max=ps_max,
            ev_ebitda_max=ev_ebitda_max,
            roe_min_pct=roe_min_pct,
            roic_min_pct=roic_min_pct,
            operating_margin_min_pct=operating_margin_min_pct,
            revenue_growth_yoy_min_pct=revenue_growth_yoy_min_pct,
            eps_growth_yoy_min_pct=eps_growth_yoy_min_pct,
            debt_to_equity_max=debt_to_equity_max,
            interest_coverage_min=interest_coverage_min,
            current_ratio_min=current_ratio_min,
            market_cap_min_usd=market_cap_min_usd,
            beta_min=beta_min,
            beta_max=beta_max,
            dividend_yield_min_pct=dividend_yield_min_pct,
            payout_ratio_max_pct=payout_ratio_max_pct,
        )
        if ok:
            passed.append(snap)
        elif reasons and "ticker_info_error" not in reasons[0]:
            notes.append(f"{sym}: {', '.join(reasons[:3])}")

    return _format_result(passed, universe_hint, notes[:50])


@tool("get_screened_stocks")
async def get_screened_stocks(
    pe_min: Annotated[float | None, "Trailing or forward P/E lower bound."] = _MEDIUM_DEFAULTS["pe_min"],
    pe_max: Annotated[float | None, "Trailing or forward P/E upper bound."] = _MEDIUM_DEFAULTS["pe_max"],
    peg_min: Annotated[float | None, "PEG lower bound (earnings growth must be positive/stable to use)."] = _MEDIUM_DEFAULTS["peg_min"],
    peg_max: Annotated[float | None, "PEG upper bound."] = _MEDIUM_DEFAULTS["peg_max"],
    pb_max: Annotated[float | None, "Price/book ceiling (sector-sensitive)."] = _MEDIUM_DEFAULTS["pb_max"],
    ps_max: Annotated[float | None, "Price/sales ceiling (sector-sensitive)."] = _MEDIUM_DEFAULTS["ps_max"],
    ev_ebitda_max: Annotated[float | None, "EV/EBITDA ceiling."] = _MEDIUM_DEFAULTS["ev_ebitda_max"],
    roe_min_pct: Annotated[float | None, "Minimum ROE (%)."] = _MEDIUM_DEFAULTS["roe_min_pct"],
    roic_min_pct: Annotated[float | None, "Minimum ROIC (%)."] = _MEDIUM_DEFAULTS["roic_min_pct"],
    operating_margin_min_pct: Annotated[float | None, "Optional minimum operating margin (%)."] = _MEDIUM_DEFAULTS["operating_margin_min_pct"],
    revenue_growth_yoy_min_pct: Annotated[float | None, "Minimum revenue YoY growth (%)."] = _MEDIUM_DEFAULTS["revenue_growth_yoy_min_pct"],
    eps_growth_yoy_min_pct: Annotated[float | None, "Minimum EPS YoY growth (%)."] = _MEDIUM_DEFAULTS["eps_growth_yoy_min_pct"],
    debt_to_equity_max: Annotated[float | None, "Maximum debt/equity."] = _MEDIUM_DEFAULTS["debt_to_equity_max"],
    interest_coverage_min: Annotated[float | None, "Minimum interest coverage (times)."] = _MEDIUM_DEFAULTS["interest_coverage_min"],
    current_ratio_min: Annotated[float | None, "Minimum current ratio."] = _MEDIUM_DEFAULTS["current_ratio_min"],
    market_cap_min_usd: Annotated[float | None, "Minimum market cap (USD)."] = _MEDIUM_DEFAULTS["market_cap_min_usd"],
    beta_min: Annotated[float | None, "Minimum 1y beta vs benchmark."] = _MEDIUM_DEFAULTS["beta_min"],
    beta_max: Annotated[float | None, "Maximum 1y beta vs benchmark."] = _MEDIUM_DEFAULTS["beta_max"],
    dividend_yield_min_pct: Annotated[float | None, "Minimum dividend yield (%); 0 = no dividend floor."] = _MEDIUM_DEFAULTS["dividend_yield_min_pct"],
    payout_ratio_max_pct: Annotated[float | None, "Maximum payout ratio (%)."] = _MEDIUM_DEFAULTS["payout_ratio_max_pct"],
    max_results: Annotated[int, "Cap on returned tickers."] = _MEDIUM_DEFAULTS["max_results"],
    universe_hint: Annotated[str | None, "Optional exchange/region/sector hint, e.g. 'US large-cap tech'."] = None,
) -> str:
    """Return stocks passing quantitative filters.

    Threshold defaults match a **medium profit / medium risk** (balanced quality + growth)
    style screen. There is **no** risk-profile parameter — adjust any numeric arg to tune.

    Candidate tickers are **not** a tool argument: the screener node sets
    ``screener_candidate_symbols`` on ``AgentContext``
    (e.g. from orchestration / universe resolution) before this tool runs.

    Uses only yfinance wrapper functions in ``BOTH_FUNCTIONS | SCREENER_FUNCTIONS``.
    """
    runtime = get_runtime(AgentContext)
    candidate_symbols: list[str] = list(runtime.context.get("screener_candidate_symbols") or [])
    return await asyncio.to_thread(
        run_get_screened_stocks_sync,
        candidate_symbols,
        pe_min=pe_min,
        pe_max=pe_max,
        peg_min=peg_min,
        peg_max=peg_max,
        pb_max=pb_max,
        ps_max=ps_max,
        ev_ebitda_max=ev_ebitda_max,
        roe_min_pct=roe_min_pct,
        roic_min_pct=roic_min_pct,
        operating_margin_min_pct=operating_margin_min_pct,
        revenue_growth_yoy_min_pct=revenue_growth_yoy_min_pct,
        eps_growth_yoy_min_pct=eps_growth_yoy_min_pct,
        debt_to_equity_max=debt_to_equity_max,
        interest_coverage_min=interest_coverage_min,
        current_ratio_min=current_ratio_min,
        market_cap_min_usd=market_cap_min_usd,
        beta_min=beta_min,
        beta_max=beta_max,
        dividend_yield_min_pct=dividend_yield_min_pct,
        payout_ratio_max_pct=payout_ratio_max_pct,
        max_results=max_results,
        universe_hint=universe_hint,
    )
