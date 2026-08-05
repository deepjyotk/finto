"""Market-cap category form.

Important fields for cap-based screening
----------------------------------------
- ``market_category``: qualitative bucket — ``large_cap``, ``medium_cap``, or ``small_cap``.
- ``min_inr`` / ``max_inr``: optional explicit floors/ceilings in INR against
  ``company_metadata.marketCap`` from the Yahoo snapshot (typically INR for NSE ``.NS``).

Additional rows filter on valuation and fundamentals (P/E, ROE, margins, …).
"""

from __future__ import annotations

from typing import Literal

from .base import BaseScreenerForm, ScreenerFormField, field

MarketCapCategory = Literal["large_cap", "medium_cap", "small_cap"]


class MarketCapForm(BaseScreenerForm):
    category: str = "market_cap"
    description: str = "Screen by market-cap tier and/or INR range, aligned with NSE listings."

    market_category: ScreenerFormField[MarketCapCategory] = field(
        "large_cap",
        is_advanced_filter=False,
    )

    min_inr: ScreenerFormField[int | None] = field(None, is_advanced_filter=False)
    max_inr: ScreenerFormField[int | None] = field(None, is_advanced_filter=False)

    pe_min: ScreenerFormField[float] = field(None)
    pe_max: ScreenerFormField[float] = field(None)

    peg_min: ScreenerFormField[float] = field(None)
    peg_max: ScreenerFormField[float] = field(None)

    pb_min: ScreenerFormField[float] = field(None)
    pb_max: ScreenerFormField[float] = field(None)

    ps_min: ScreenerFormField[float] = field(None)
    ps_max: ScreenerFormField[float] = field(None)

    roe_pct_min: ScreenerFormField[float] = field(None)
    roe_pct_max: ScreenerFormField[float] = field(None)

    roic_pct_min: ScreenerFormField[float] = field(None)
    roic_pct_max: ScreenerFormField[float] = field(None)

    operating_margin_pct_min: ScreenerFormField[float] = field(None)
    operating_margin_pct_max: ScreenerFormField[float] = field(None)

    revenue_growth_pct_min: ScreenerFormField[float] = field(None)
    revenue_growth_pct_max: ScreenerFormField[float] = field(None)

    debt_to_equity_min: ScreenerFormField[float] = field(None)
    debt_to_equity_max: ScreenerFormField[float] = field(None)

    interest_coverage_min: ScreenerFormField[float] = field(None)
    interest_coverage_max: ScreenerFormField[float] = field(None)

    current_ratio_min: ScreenerFormField[float] = field(None)
    current_ratio_max: ScreenerFormField[float] = field(None)

    dividend_yield_pct_min: ScreenerFormField[float] = field(None)
    dividend_yield_pct_max: ScreenerFormField[float] = field(None)

    payout_ratio_pct_min: ScreenerFormField[float] = field(None)
    payout_ratio_pct_max: ScreenerFormField[float] = field(None)

    beta_min: ScreenerFormField[float] = field(None)
    beta_max: ScreenerFormField[float] = field(None)

    sectors: ScreenerFormField[list[str]] = field(None)
    industry: ScreenerFormField[str] = field(None)
    country: ScreenerFormField[str] = field(None)
    exchange: ScreenerFormField[str] = field(None)
    market_region: ScreenerFormField[str] = field(None)
    style: ScreenerFormField[str] = field(None)
    sensitivity_type: ScreenerFormField[str] = field(None)
