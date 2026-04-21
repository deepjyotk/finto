"""
Dividend & income metrics — deterministic formulas.

Functions:
  dividend_payout_ratio, dividend_growth_rate, retention_ratio,
  sustainable_growth_rate
"""


def dividend_payout_ratio(dividends_per_share: float, earnings_per_share: float) -> float:
    """
    Calculate Dividend Payout Ratio.

    Percentage of earnings paid out as dividends. Lower = more reinvestment.
    Benchmark: 30-50% is moderate; > 80% may be unsustainable.

    Args:
        dividends_per_share: Annual dividends per share
        earnings_per_share: Earnings per share (TTM)

    Returns:
        Payout ratio percentage (e.g., 35.0 for 35%)
    """
    if earnings_per_share <= 0:
        return 0.0
    return (dividends_per_share / earnings_per_share) * 100


def dividend_growth_rate(
    current_dividend: float, previous_dividend: float, years: float = 1.0
) -> float:
    """
    Calculate Dividend Growth Rate (annualized).

    Measures how fast dividends are growing. Used in Gordon Growth Model.

    Args:
        current_dividend: Most recent annual dividend per share
        previous_dividend: Annual dividend per share N years ago
        years: Number of years between measurements (default 1)

    Returns:
        Annualized dividend growth rate percentage (e.g., 8.0 for 8%)
    """
    if previous_dividend <= 0 or years <= 0:
        return 0.0
    return ((current_dividend / previous_dividend) ** (1 / years) - 1) * 100


def retention_ratio(dividends_per_share: float, earnings_per_share: float) -> float:
    """
    Calculate Retention Ratio (Plowback Ratio).

    Percentage of earnings retained for reinvestment (1 - payout ratio).
    Higher retention = more internal growth funding.

    Args:
        dividends_per_share: Annual dividends per share
        earnings_per_share: Earnings per share

    Returns:
        Retention ratio percentage (e.g., 65.0 for 65%)
    """
    if earnings_per_share <= 0:
        return 0.0
    return (1 - dividends_per_share / earnings_per_share) * 100


def sustainable_growth_rate(roe_pct: float, retention_ratio_pct: float) -> float:
    """
    Calculate Sustainable Growth Rate (SGR).

    Maximum growth rate achievable without external financing.
    SGR = ROE × Retention Ratio.

    Args:
        roe_pct: Return on Equity percentage (e.g., 18.0)
        retention_ratio_pct: Retention ratio percentage (e.g., 65.0)

    Returns:
        Sustainable growth rate percentage (e.g., 11.7 for 11.7%)
    """
    return (roe_pct / 100) * (retention_ratio_pct / 100) * 100
