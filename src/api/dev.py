from __future__ import annotations

import math
from collections import defaultdict
from datetime import date
from decimal import Decimal
from typing import Annotated

import numpy as np
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.db import get_session
from src.repositories.screener_repo import ScreenerRepo
from src.tools.screener_tool import (
    EquityScreenData,
    _f,
    _growth_to_pct,
    _yoy_growth_pct,
)

router = APIRouter(prefix="/dev", tags=["dev"])


class DevPriceBarQueryResponse(BaseModel):
    symbol: str
    company_name: str
    open: Decimal | None
    high: Decimal | None
    low: Decimal | None
    close: Decimal | None
    volume: int | None


class MetricDistribution(BaseModel):
    """Descriptive stats for one fundamental; JSON uses \"range\" for max − min."""

    model_config = ConfigDict(populate_by_name=True)

    n: int
    min: float | None = None
    max: float | None = None
    rng: float | None = Field(None, serialization_alias="range")
    mean: float | None = None
    median: float | None = None
    stddev: float | None = None
    p25: float | None = None
    p75: float | None = None
    p90: float | None = None
    p95: float | None = None
    p99: float | None = None


class FundamentalsStatsResponse(BaseModel):
    pe: MetricDistribution
    peg: MetricDistribution
    pb: MetricDistribution
    ps: MetricDistribution
    roe_pct: MetricDistribution
    roic_pct: MetricDistribution
    operating_margin_pct: MetricDistribution
    revenue_growth_pct: MetricDistribution
    debt_to_equity: MetricDistribution
    interest_coverage: MetricDistribution
    current_ratio: MetricDistribution
    market_cap: MetricDistribution


def _metrics_snapshot_for_distribution(data: EquityScreenData) -> dict[str, float | None]:
    """Per-equity metrics; keep aligned with screener_tool._apply_* snap fields."""

    info = data.info
    income_rows = data.income_rows

    rev_g = _growth_to_pct(info.get("revenueGrowth"))
    eps_g = _growth_to_pct(info.get("earningsGrowth"))

    if rev_g is None and len(income_rows) >= 2:
        r1 = _f(income_rows[0]["data"].get("Total Revenue"))
        r0 = _f(income_rows[1]["data"].get("Total Revenue"))
        rev_g = _yoy_growth_pct(r1, r0)

    if eps_g is None and len(income_rows) >= 2:
        e1 = _f(income_rows[0]["data"].get("Basic EPS"))
        e0 = _f(income_rows[1]["data"].get("Basic EPS"))
        eps_g = _yoy_growth_pct(e1, e0)

    pe = _f(info.get("trailingPE"))
    if pe is None:
        pe = _f(info.get("forwardPE"))

    peg: float | None = None
    if pe is not None and eps_g is not None and eps_g > 0:
        peg = pe / eps_g

    pb = _f(info.get("priceToBook"))
    ps = _f(info.get("priceToSalesTrailing12Months"))

    latest_i = data.income_rows[0]["data"] if data.income_rows else {}
    latest_b = data.balance_rows[0]["data"] if data.balance_rows else {}

    roe = _f(info.get("returnOnEquity"))
    if roe is not None and -1 < roe < 1:
        roe *= 100.0

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

    om = _f(info.get("operatingMargins"))
    if om is not None and -1 < om < 1:
        om *= 100.0

    dte = _f(info.get("debtToEquity"))

    coverage: float | None = None
    if oi is not None and interest is not None and interest != 0:
        coverage = abs(oi / interest)

    cr = _f(info.get("currentRatio"))
    mcap = _f(info.get("marketCap"))

    return {
        "pe": pe,
        "peg": peg,
        "pb": pb,
        "ps": ps,
        "roe_pct": roe,
        "roic_pct": roic_pct,
        "operating_margin_pct": om,
        "revenue_growth_pct": rev_g,
        "debt_to_equity": dte,
        "interest_coverage": coverage,
        "current_ratio": cr,
        "market_cap": mcap,
    }


def _distribution(values: list[float]) -> MetricDistribution:
    arr = np.asarray(values, dtype=np.float64)
    arr = arr[np.isfinite(arr)]
    n = int(arr.size)
    if n == 0:
        return MetricDistribution(n=0)

    mn = float(np.min(arr))
    mx = float(np.max(arr))
    mean = float(np.mean(arr))
    median = float(np.percentile(arr, 50, method="linear"))
    stddev = float(np.std(arr, ddof=1)) if n > 1 else None

    return MetricDistribution(
        n=n,
        min=mn,
        max=mx,
        rng=mx - mn,
        mean=mean,
        median=median,
        stddev=stddev,
        p25=float(np.percentile(arr, 25, method="linear")),
        p75=float(np.percentile(arr, 75, method="linear")),
        p90=float(np.percentile(arr, 90, method="linear")),
        p95=float(np.percentile(arr, 95, method="linear")),
        p99=float(np.percentile(arr, 99, method="linear")),
    )


_METRIC_KEYS: tuple[str, ...] = (
    "pe",
    "peg",
    "pb",
    "ps",
    "roe_pct",
    "roic_pct",
    "operating_margin_pct",
    "revenue_growth_pct",
    "debt_to_equity",
    "interest_coverage",
    "current_ratio",
    "market_cap",
)


@router.get("/query/fundamentals-stats", response_model=FundamentalsStatsResponse)
async def query_fundamentals_distribution_stats(
    session: Annotated[AsyncSession, Depends(get_session)],
):
    repo = ScreenerRepo(session)
    equities = await repo.load_equities_with_metadata()
    if not equities:
        empty = MetricDistribution(n=0)
        return FundamentalsStatsResponse(
            **{k: empty for k in _METRIC_KEYS},
        )

    equity_ids = [e["id"] for e in equities]
    income_map = await repo.load_latest_income_rows(equity_ids, n_periods=2)
    balance_map = await repo.load_latest_balance_rows(equity_ids, n_periods=1)

    columns: dict[str, list[float]] = defaultdict(list)

    for equity in equities:
        eid = equity["id"]
        data = EquityScreenData(
            symbol_ns=f'{equity["symbol"]}.NS',
            info=equity["info"],
            income_rows=income_map.get(eid, []),
            balance_rows=balance_map.get(eid, []),
        )
        snap = _metrics_snapshot_for_distribution(data)
        for key in _METRIC_KEYS:
            v = snap.get(key)
            if v is not None and math.isfinite(v):
                columns[key].append(float(v))

    return FundamentalsStatsResponse(
        **{k: _distribution(columns[k]) for k in _METRIC_KEYS},
    )


@router.get("/query/price-bar", response_model=DevPriceBarQueryResponse | None)
async def query_price_bar_by_symbol_and_trade_date(
    symbol: Annotated[str, Query(min_length=1, description="NSE symbol, e.g. RELIANCE")],
    trade_date: Annotated[date, Query(description="Trade date in YYYY-MM-DD format")],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    result = await session.execute(
        text(
            """
            SELECT
                ie.symbol,
                ie.company_name,
                pb.open,
                pb.high,
                pb.low,
                pb.close,
                pb.volume
            FROM in_equities AS ie
            JOIN price_bars_1d AS pb
              ON pb.in_equity_id = ie.id
            WHERE ie.symbol = split_part(upper(:symbol), '.', 1)
              AND pb.trade_date = :trade_date
            LIMIT 1
            """
        ),
        {"symbol": symbol.strip(), "trade_date": trade_date},
    )
    row = result.fetchone()
    if row is None:
        return None

    return DevPriceBarQueryResponse(
        symbol=row.symbol,
        company_name=row.company_name,
        open=row.open,
        high=row.high,
        low=row.low,
        close=row.close,
        volume=row.volume,
    )
