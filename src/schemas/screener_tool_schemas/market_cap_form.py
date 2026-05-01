"""Market-cap tier form: one category with configurable large / mid / small USD breakpoints.

Tier semantics match the PRD (size buckets):
  large-cap: market cap >= large_cap_min_usd
  mid-cap:    mid_cap_min_usd <= market cap <= mid_cap_max_usd (typically below large floor)
  small-cap: market cap <= small_cap_max_usd (typically aligned with mid floor)

Defaults align with ``stocks-interpretation.md``: large >$10B, mid $2B–$10B, small <$2B.
Adjust module-level constants or form field values to change breakpoints globally or per-user.
"""

from __future__ import annotations

from typing import Literal

from .base import BaseScreenerForm, ScreenerFormField, field

MarketCapSegment = Literal["large_cap", "mid_cap", "small_cap"]

# Single source of truth for tier boundaries (USD). Import these without instantiating the form.
DEFAULT_LARGE_CAP_MIN_USD: int = 10_000_000_000
DEFAULT_MID_CAP_MIN_USD: int = 2_000_000_000
DEFAULT_MID_CAP_MAX_USD: int = 10_000_000_000
DEFAULT_SMALL_CAP_MAX_USD: int = 2_000_000_000


def resolved_market_cap_bounds(
    segment: MarketCapSegment | str | None,
    *,
    large_cap_min_usd: int | None,
    mid_cap_min_usd: int | None,
    mid_cap_max_usd: int | None,
    small_cap_max_usd: int | None,
) -> tuple[int | None, int | None]:
    """Map segment + tier boundaries to ``(market_cap_min, market_cap_max)`` for screening."""
    if segment == "large_cap":
        return large_cap_min_usd, None
    if segment == "mid_cap":
        return mid_cap_min_usd, mid_cap_max_usd
    if segment == "small_cap":
        return None, small_cap_max_usd
    return None, None


class MarketCapForm(BaseScreenerForm):
    category: str = "market_cap"
    description: str = (
        "Screen by market-cap tier (large / mid / small). Tier USD boundaries are configurable."
    )

    segment: ScreenerFormField[MarketCapSegment | None] = field(
        "large_cap",
        is_advanced_filter=False,
    )

    large_cap_min_usd: ScreenerFormField[int] = field(
        DEFAULT_LARGE_CAP_MIN_USD,
        is_advanced_filter=True,
    )
    mid_cap_min_usd: ScreenerFormField[int] = field(
        DEFAULT_MID_CAP_MIN_USD,
        is_advanced_filter=True,
    )
    mid_cap_max_usd: ScreenerFormField[int] = field(
        DEFAULT_MID_CAP_MAX_USD,
        is_advanced_filter=True,
    )
    small_cap_max_usd: ScreenerFormField[int] = field(
        DEFAULT_SMALL_CAP_MAX_USD,
        is_advanced_filter=True,
    )

    market_cap_min: ScreenerFormField[int] = field(None)
    market_cap_max: ScreenerFormField[int] = field(None)

    pe_min: ScreenerFormField[float] = field(None)
    pe_max: ScreenerFormField[float] = field(40)

    peg_min: ScreenerFormField[float] = field(None)
    peg_max: ScreenerFormField[float] = field(2)

    pb_min: ScreenerFormField[float] = field(None)
    pb_max: ScreenerFormField[float] = field(5)

    ps_min: ScreenerFormField[float] = field(None)
    ps_max: ScreenerFormField[float] = field(None)

    roe_pct_min: ScreenerFormField[float] = field(8)
    roe_pct_max: ScreenerFormField[float] = field(None)

    roic_pct_min: ScreenerFormField[float] = field(8)
    roic_pct_max: ScreenerFormField[float] = field(None)

    operating_margin_pct_min: ScreenerFormField[float] = field(5)
    operating_margin_pct_max: ScreenerFormField[float] = field(None)

    revenue_growth_pct_min: ScreenerFormField[float] = field(5)
    revenue_growth_pct_max: ScreenerFormField[float] = field(None)

    debt_to_equity_min: ScreenerFormField[float] = field(None)
    debt_to_equity_max: ScreenerFormField[float] = field(150)

    interest_coverage_min: ScreenerFormField[float] = field(3)
    interest_coverage_max: ScreenerFormField[float] = field(None)

    current_ratio_min: ScreenerFormField[float] = field(1)
    current_ratio_max: ScreenerFormField[float] = field(None)

    dividend_yield_pct_min: ScreenerFormField[float] = field(None)
    dividend_yield_pct_max: ScreenerFormField[float] = field(None)

    payout_ratio_pct_min: ScreenerFormField[float] = field(None)
    payout_ratio_pct_max: ScreenerFormField[float] = field(None)

    beta_min: ScreenerFormField[float] = field(None)
    beta_max: ScreenerFormField[float] = field(None)

    sectors: ScreenerFormField[list[str]] = field([])
    industry: ScreenerFormField[str] = field(None)
    country: ScreenerFormField[str] = field(None)
    exchange: ScreenerFormField[str] = field(None)
    market_region: ScreenerFormField[str] = field(None)
    style: ScreenerFormField[str] = field(None)
    sensitivity_type: ScreenerFormField[str] = field(None)
