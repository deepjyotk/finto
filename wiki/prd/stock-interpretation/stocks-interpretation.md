# Dev fundamentals distribution (`/dev/query`)

On `http://localhost:3000/dev/query`, expose universe-wide descriptive statistics for fundamentals used by the stock screener.

Because this is dev-only, implementation may live in a single API module ([`src/api/dev.py`](../../../src/api/dev.py)); reuse existing bulk loaders ([`ScreenerRepo`](../../../src/repositories/screener_repo.py)) rather than adding new service/repo layers.

Backend endpoint: **`GET /api/v1/dev/query/fundamentals-stats`** (see implementation).

---

## Statistical summaries required

For each metric below, compute over all equities where the value is defined (finite):

- Minimum, maximum, range (max − min), mean, median (50th percentile)
- Sample standard deviation (`stddev_samp`, ddof = 1)
- Percentiles (continuous / linear interpolation, matching PostgreSQL `percentile_cont`): 25th, 75th, 90th, 95th, 99th
- Count **n** (number of equities contributing)

Metrics:

1. **pe** — Min, max, range, mean, median, standard deviation, p25, p75, p90, p95, p99.
2. **peg** — Same.
3. **pb** — Same.
4. **ps** — Same.
5. **roe_pct** (ROE as %) — Same.
6. **roic_pct** (ROIC as %) — Same.
7. **operating_margin_pct** — Same.
8. **revenue_growth_pct** — Same (including percentiles through p99).
9. **debt_to_equity** — Same.
10. **interest_coverage** — Same.
11. **current_ratio** — Same.
12. **market_cap** — Same (including range, median, standard deviation, and percentiles through p99).

---

## Data sources and definitions

Align with [`documentation/db.md`](../../documentation/db.md) and [`src/tools/screener_tool.py`](../../../src/tools/screener_tool.py).

| Metric | Primary source | Notes |
|--------|----------------|--------|
| pe | `in_equities.company_metadata` | `trailingPE`, else `forwardPE`. JSON keys Yahoo-style. |
| peg | Derived | `pe / eps_growth_pct` only when PE exists and EPS growth > 0 (see earnings growth below). |
| pb | `company_metadata` | `priceToBook`. |
| ps | `company_metadata` | `priceToSalesTrailing12Months`. |
| roe_pct | `company_metadata` | `returnOnEquity`; if `-1 < x < 1`, multiply by 100. |
| roic_pct | Statements | Latest annual `f_income_statements` + `f_balance_sheets`: `(Operating Income / (Total Debt + Stockholders Equity − Cash And Cash Equivalents)) × 100` when invested capital > 0. Display names match screener repo maps. |
| operating_margin_pct | `company_metadata` | `operatingMargins`; fraction normalization same as ROE. |
| revenue_growth_pct | Metadata + income | `_growth_to_pct` on `revenueGrowth`; if missing, YoY % from two latest annual rows on **Total Revenue**. |
| eps growth (for PEG only) | Metadata + income | `_growth_to_pct` on `earningsGrowth`; else YoY from **Basic EPS** on two latest annual rows. |
| debt_to_equity | `company_metadata` | `debtToEquity`. |
| interest_coverage | Statements | `abs(Operating Income / Interest Expense)` when interest expense ≠ 0. |
| current_ratio | `company_metadata` | `currentRatio`. |
| market_cap | `company_metadata` | `marketCap`. |

Exclude NaN and infinite values from aggregates.

---

## Implementation note

Bulk load via `ScreenerRepo.load_equities_with_metadata`, `load_latest_income_rows(..., n_periods=2)`, `load_latest_balance_rows(..., n_periods=1)`. Per-equity metric formulas must stay in sync with `screener_tool._apply_*`.

---

## Captured snapshot (manual run)

**Date:** 2026-05-01  

**How produced:** `uv run python` against the live project DB using the same logic as `GET /api/v1/dev/query/fundamentals-stats` (`query_fundamentals_distribution_stats` in [`src/api/dev.py`](../../../src/api/dev.py)).

**Caveats:** Values depend entirely on the current `in_equities.company_metadata` payloads and annual statement rows in the database at query time. In this snapshot, **`ps` had no finite values (`n`: 0)**—stored metadata did not include usable `priceToSalesTrailing12Months` for any equity after filtering.

```json
{
  "pe": {
    "n": 1929,
    "min": -143.24509,
    "max": 4925.0,
    "range": 5068.24509,
    "mean": 57.539866849334366,
    "median": 25.686274,
    "stddev": 222.70297801919511,
    "p25": 14.841288,
    "p75": 44.484737,
    "p90": 80.59967200000001,
    "p95": 125.79928399999987,
    "p99": 627.8400000000038
  },
  "peg": {
    "n": 1105,
    "min": -37.971702685714135,
    "max": 2445.3335,
    "range": 2483.3052026857144,
    "mean": 11.320569464762453,
    "median": 1.468815681818182,
    "stddev": 80.20791083088712,
    "p25": 0.5429549342891279,
    "p75": 5.267990254237288,
    "p90": 17.69208003418804,
    "p95": 35.456533210526274,
    "p99": 179.8314285714289
  },
  "pb": {
    "n": 2197,
    "min": -362.36194,
    "max": 176.30435,
    "range": 538.66629,
    "mean": 3.969074963834729,
    "median": 2.2891138,
    "stddev": 12.078216014187568,
    "p25": 1.0404738,
    "p75": 4.6767697,
    "p90": 9.333840600000002,
    "p95": 14.220634799999987,
    "p99": 36.593257759999986
  },
  "ps": {
    "n": 0,
    "min": null,
    "max": null,
    "range": null,
    "mean": null,
    "median": null,
    "stddev": null,
    "p25": null,
    "p75": null,
    "p90": null,
    "p95": null,
    "p99": null
  },
  "roe_pct": {
    "n": 157,
    "min": -91.438,
    "max": 92.33100400000001,
    "range": 183.769004,
    "mean": 12.669846138866244,
    "median": 12.7,
    "stddev": 19.940538888028378,
    "p25": 3.47,
    "p75": 19.736,
    "p90": 31.2542,
    "p95": 43.048398199999994,
    "p99": 74.51955779999999
  },
  "roic_pct": {
    "n": 2016,
    "min": -1366.4876690533015,
    "max": 874.4117647058823,
    "range": 2240.899433759184,
    "mean": 9.320688226339035,
    "median": 9.724705375202419,
    "stddev": 50.732004633704506,
    "p25": 3.5476185036987276,
    "p75": 16.721517564109945,
    "p90": 25.53474323352151,
    "p95": 33.758841794701524,
    "p99": 71.17008804410263
  },
  "operating_margin_pct": {
    "n": 2208,
    "min": -19479.0,
    "max": 1306.5,
    "range": 20785.5,
    "mean": 2.4730913785819757,
    "median": 8.7185,
    "stddev": 416.3615524689964,
    "p25": 3.19575,
    "p75": 17.1705,
    "p90": 32.7011994,
    "p95": 49.003698050000004,
    "p99": 84.12116720999995
  },
  "revenue_growth_pct": {
    "n": 2187,
    "min": -100.0,
    "max": 770.9858865530571,
    "range": 870.9858865530571,
    "mean": 8.834147970503443,
    "median": 8.5,
    "stddev": 37.14200944056895,
    "p25": -2.3,
    "p75": 21.55,
    "p90": 41.04000000000005,
    "p95": 57.00999999999994,
    "p99": 93.82799999999997
  },
  "debt_to_equity": {
    "n": 1910,
    "min": 0.0,
    "max": 19197.627,
    "range": 19197.627,
    "mean": 93.97181361256544,
    "median": 29.83,
    "stddev": 592.3434682009862,
    "p25": 7.980250000000001,
    "p75": 69.9255,
    "p90": 152.0474,
    "p95": 276.56749999999994,
    "p99": 743.6923700000008
  },
  "interest_coverage": {
    "n": 2034,
    "min": 0.001153874785974838,
    "max": 104889.4,
    "range": 104889.3988461252,
    "mean": 295.0554038143618,
    "median": 5.510754907788,
    "stddev": 4091.755542063223,
    "p25": 2.186489418020872,
    "p75": 20.444468687373167,
    "p90": 100.44860462432776,
    "p95": 273.0354571136528,
    "p99": 2456.197996693591
  },
  "current_ratio": {
    "n": 164,
    "min": 0.01,
    "max": 778.713,
    "range": 778.703,
    "mean": 12.994542682926832,
    "median": 1.7000000000000002,
    "stddev": 69.69863336429867,
    "p25": 0.95775,
    "p75": 2.6755,
    "p90": 5.3678000000000035,
    "p95": 11.345049999999993,
    "p99": 268.68300000000045
  },
  "market_cap": {
    "n": 2204,
    "min": 13416137.0,
    "max": 17968417210368.0,
    "range": 17968403794231.0,
    "mean": 203574412015.31262,
    "median": 18134140928.0,
    "stddev": 802726145080.241,
    "p25": 3837917504.0,
    "p75": 96904267776.0,
    "p90": 393482734796.8002,
    "p95": 970267525119.9985,
    "p99": 3521227120967.625
  }
}
```



## Classification of stocks:

Stocks can be categorized in multiple ways depending on **what you’re trying to analyze**—growth, risk, income, sector, etc. There isn’t just one system; investors use several lenses at once.

Here’s a clean breakdown 👇

---

# 1. Based on Market Capitalization (Size)

This is the most common classification.

* **Large-cap** (>$10B)
  Stable, established companies (e.g., Apple, Microsoft)

* **Mid-cap** ($2B–$10B)
  Growth + some stability

* **Small-cap** (<$2B)
  High growth potential, higher risk

---

# 2. Based on Growth vs Value

* **Growth Stocks**

  * High revenue/earnings growth
  * Expensive (high P/E)
  * Reinvest profits
    Example: Tesla

* **Value Stocks**

  * Undervalued relative to fundamentals
  * Lower P/E, often “cheap”
    Example: Coca-Cola

---

# 3. Based on Dividend Behavior

* **Dividend Stocks**

  * Regular payouts
  * Income-focused
    Example: Johnson & Johnson

* **Non-dividend Stocks**

  * Reinvest profits for growth

---

# 4. Based on Sector / Industry

Grouped by business activity:

* Tech (NVIDIA)
* Healthcare
* Finance
* Energy
* Consumer Goods
* Industrials

This is often aligned with classifications like the Global Industry Classification Standard.

---

# 5. Based on Economic Sensitivity

* **Cyclical Stocks**

  * Move with economy (e.g., travel, luxury)
  * Example: Marriott International

* **Defensive Stocks**

  * Stable even in downturns
  * Example: Procter & Gamble

---

# 6. Based on Ownership / Geography

* **Domestic Stocks**
* **International Stocks**
* **Emerging Market Stocks**

---

# 7. Based on Investment Style (Advanced)

* **Blue-chip Stocks**
  Large, reliable leaders
  (e.g., IBM)

* **Penny Stocks**
  Very low-priced, high risk

* **Momentum Stocks**
  Stocks trending strongly upward

* **ESG Stocks**
  Focus on environmental/social/governance criteria

---

# 8. Based on Volatility / Risk

* **High-beta stocks** → more volatile than market
* **Low-beta stocks** → more stable

---

# How to Think About It (Practical Insight)

Most investors **combine categories**, for example:

* “Large-cap + value + dividend” → safe, income portfolio
* “Small-cap + growth” → aggressive, high-return strategy

---

If you want, I can map these categories to **how you should pick stocks using metrics like PE < 15, PEG < 1 (what you asked earlier)**—that’s where this becomes actually useful.

