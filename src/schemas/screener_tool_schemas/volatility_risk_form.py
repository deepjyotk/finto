from __future__ import annotations

from .base import BaseScreenerForm, ScreenerFormField, field


class VolatilityRiskForm(BaseScreenerForm):
    category: str = "volatility_risk"
    description: str = "Filter stocks based on volatility and balance-sheet risk."

    market_cap_min: ScreenerFormField[int] = field(None)
    market_cap_max: ScreenerFormField[int] = field(None)

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
    debt_to_equity_max: ScreenerFormField[float] = field(
        100,
        is_advanced_filter=False,
    )

    interest_coverage_min: ScreenerFormField[float] = field(
        3,
        is_advanced_filter=False,
    )
    interest_coverage_max: ScreenerFormField[float] = field(None)

    current_ratio_min: ScreenerFormField[float] = field(
        1,
        is_advanced_filter=False,
    )
    current_ratio_max: ScreenerFormField[float] = field(None)

    dividend_yield_pct_min: ScreenerFormField[float] = field(None)
    dividend_yield_pct_max: ScreenerFormField[float] = field(None)

    payout_ratio_pct_min: ScreenerFormField[float] = field(None)
    payout_ratio_pct_max: ScreenerFormField[float] = field(None)

    beta_min: ScreenerFormField[float] = field(None)
    beta_max: ScreenerFormField[float] = field(
        1,
        is_advanced_filter=False,
    )

    sectors: ScreenerFormField[list[str]] = field(None)
    industry: ScreenerFormField[str] = field(None)
    country: ScreenerFormField[str] = field(None)
    exchange: ScreenerFormField[str] = field(None)
    market_region: ScreenerFormField[str] = field(None)
    style: ScreenerFormField[str] = field(None)
    sensitivity_type: ScreenerFormField[str] = field(None)
