"""Pydantic schemas for screener tool configuration and run payloads."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ScreenerParamConfig(BaseModel):
    """UI/runtime config for a single screener parameter."""

    value: float | int | None
    dirty: bool = False
    is_advanced_filter: bool = False
    enabled: bool


class MediumScreenerParamConfig(BaseModel):
    """Single source of truth for medium profile defaults and HITL visibility."""

    pe_min: ScreenerParamConfig = ScreenerParamConfig(value=12.0, enabled=True)
    pe_max: ScreenerParamConfig = ScreenerParamConfig(value=25.0, enabled=True)
    peg_min: ScreenerParamConfig = ScreenerParamConfig(value=0.8, enabled=True)
    peg_max: ScreenerParamConfig = ScreenerParamConfig(value=1.5, enabled=True)
    pb_max: ScreenerParamConfig = ScreenerParamConfig(value=5.0, enabled=True)
    ps_max: ScreenerParamConfig = ScreenerParamConfig(value=8.0, enabled=True)
    ev_ebitda_max: ScreenerParamConfig = ScreenerParamConfig(value=18.0, enabled=True)
    roe_min_pct: ScreenerParamConfig = ScreenerParamConfig(value=12.0, enabled=True)
    roic_min_pct: ScreenerParamConfig = ScreenerParamConfig(value=10.0, enabled=True)
    operating_margin_min_pct: ScreenerParamConfig = ScreenerParamConfig(value=None, enabled=True)
    revenue_growth_yoy_min_pct: ScreenerParamConfig = ScreenerParamConfig(value=8.0, enabled=True)
    eps_growth_yoy_min_pct: ScreenerParamConfig = ScreenerParamConfig(value=8.0, enabled=True)
    debt_to_equity_max: ScreenerParamConfig = ScreenerParamConfig(value=1.0, enabled=True)
    interest_coverage_min: ScreenerParamConfig = ScreenerParamConfig(value=4.0, enabled=False)
    current_ratio_min: ScreenerParamConfig = ScreenerParamConfig(value=1.2, enabled=False)
    market_cap_min_usd: ScreenerParamConfig = ScreenerParamConfig(
        value=1_000_000_000.0, enabled=False
    )
    beta_min: ScreenerParamConfig = ScreenerParamConfig(value=0.9, enabled=False)
    beta_max: ScreenerParamConfig = ScreenerParamConfig(value=1.2, enabled=False)
    dividend_yield_min_pct: ScreenerParamConfig = ScreenerParamConfig(value=0.0, enabled=False)
    payout_ratio_max_pct: ScreenerParamConfig = ScreenerParamConfig(value=70.0, enabled=False)
    max_results: ScreenerParamConfig = ScreenerParamConfig(value=25, enabled=False)

    def default_values(self) -> dict[str, Any]:
        return {name: getattr(self, name).value for name in self.__class__.model_fields}

    def enabled_fields(self) -> tuple[str, ...]:
        return tuple(name for name in self.__class__.model_fields if getattr(self, name).enabled)


class ScreenerCriteria(BaseModel):
    """Normalized quantitative thresholds used by the screener engine."""

    pe_min: float | None
    pe_max: float | None
    peg_min: float | None
    peg_max: float | None
    pb_max: float | None
    ps_max: float | None
    ev_ebitda_max: float | None
    roe_min_pct: float | None
    roic_min_pct: float | None
    operating_margin_min_pct: float | None
    revenue_growth_yoy_min_pct: float | None
    eps_growth_yoy_min_pct: float | None
    debt_to_equity_max: float | None
    interest_coverage_min: float | None
    current_ratio_min: float | None
    market_cap_min_usd: float | None
    beta_min: float | None
    beta_max: float | None
    dividend_yield_min_pct: float | None
    payout_ratio_max_pct: float | None

    @classmethod
    def from_values(
        cls, values: dict[str, Any], *, enabled_fields: set[str] | None = None
    ) -> "ScreenerCriteria":
        def _get(field_name: str) -> Any:
            if enabled_fields is not None and field_name not in enabled_fields:
                return None
            return values.get(field_name)

        return cls(
            pe_min=_get("pe_min"),
            pe_max=_get("pe_max"),
            peg_min=_get("peg_min"),
            peg_max=_get("peg_max"),
            pb_max=_get("pb_max"),
            ps_max=_get("ps_max"),
            ev_ebitda_max=_get("ev_ebitda_max"),
            roe_min_pct=_get("roe_min_pct"),
            roic_min_pct=_get("roic_min_pct"),
            operating_margin_min_pct=_get("operating_margin_min_pct"),
            revenue_growth_yoy_min_pct=_get("revenue_growth_yoy_min_pct"),
            eps_growth_yoy_min_pct=_get("eps_growth_yoy_min_pct"),
            debt_to_equity_max=_get("debt_to_equity_max"),
            interest_coverage_min=_get("interest_coverage_min"),
            current_ratio_min=_get("current_ratio_min"),
            market_cap_min_usd=_get("market_cap_min_usd"),
            beta_min=_get("beta_min"),
            beta_max=_get("beta_max"),
            dividend_yield_min_pct=_get("dividend_yield_min_pct"),
            payout_ratio_max_pct=_get("payout_ratio_max_pct"),
        )


class ScreenerRunRequest(BaseModel):
    """Full screener run payload with criteria + execution controls."""

    criteria: ScreenerCriteria
    max_results: int = 25
    universe_hint: str | None = None

    @classmethod
    def from_values(
        cls, values: dict[str, Any], *, enabled_fields: set[str] | None = None
    ) -> "ScreenerRunRequest":
        return cls(
            criteria=ScreenerCriteria.from_values(values, enabled_fields=enabled_fields),
            max_results=int(values.get("max_results", 25)),
            universe_hint=values.get("universe_hint"),
        )


class ScreenOneResult(BaseModel):
    """Result of screening one symbol against configured criteria."""

    passed: bool
    snapshot: dict[str, Any]
    reasons: list[str]


class ScreenerToolInput(BaseModel):
    """Input schema for the public `get_screened_stocks` tool."""

    pe_min: float | None = Field(default=12.0, description="Trailing or forward P/E lower bound.")
    pe_max: float | None = Field(default=25.0, description="Trailing or forward P/E upper bound.")
    peg_min: float | None = Field(
        default=0.8,
        description="PEG lower bound (earnings growth must be positive/stable to use).",
    )
    peg_max: float | None = Field(default=1.5, description="PEG upper bound.")
    pb_max: float | None = Field(default=5.0, description="Price/book ceiling (sector-sensitive).")
    ps_max: float | None = Field(default=8.0, description="Price/sales ceiling (sector-sensitive).")
    ev_ebitda_max: float | None = Field(default=18.0, description="EV/EBITDA ceiling.")
    roe_min_pct: float | None = Field(default=12.0, description="Minimum ROE (%).")
    roic_min_pct: float | None = Field(default=10.0, description="Minimum ROIC (%).")
    operating_margin_min_pct: float | None = Field(
        default=None,
        description="Optional minimum operating margin (%).",
    )
    revenue_growth_yoy_min_pct: float | None = Field(
        default=8.0,
        description="Minimum revenue YoY growth (%).",
    )
    eps_growth_yoy_min_pct: float | None = Field(
        default=8.0, description="Minimum EPS YoY growth (%)."
    )
    debt_to_equity_max: float | None = Field(default=1.0, description="Maximum debt/equity.")
    interest_coverage_min: float | None = Field(
        default=4.0,
        description="Minimum interest coverage (times).",
    )
    current_ratio_min: float | None = Field(default=1.2, description="Minimum current ratio.")
    market_cap_min_usd: float | None = Field(
        default=1_000_000_000.0, description="Minimum market cap (USD)."
    )
    beta_min: float | None = Field(default=0.9, description="Minimum 1y beta vs benchmark.")
    beta_max: float | None = Field(default=1.2, description="Maximum 1y beta vs benchmark.")
    dividend_yield_min_pct: float | None = Field(
        default=0.0,
        description="Minimum dividend yield (%); 0 = no dividend floor.",
    )
    payout_ratio_max_pct: float | None = Field(
        default=70.0, description="Maximum payout ratio (%)."
    )
    max_results: int = Field(default=25, description="Cap on returned tickers.")
    universe_hint: str | None = Field(
        default=None,
        description="Optional exchange/region/sector hint, e.g. 'US large-cap tech'.",
    )
