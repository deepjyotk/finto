"""
Valuation metrics — deterministic formulas for stock valuation analysis.

Functions:
  pe_ratio, forward_pe, pb_ratio, ps_ratio, peg_ratio, ev_to_ebitda,
  earnings_yield, price_to_fcf
"""


def pe_ratio(market_price: float, earnings_per_share: float) -> float:
    """
    Calculate Price-to-Earnings (P/E) Ratio.

    Measures how much investors pay per dollar of earnings.
    Lower values may indicate undervaluation; higher values may indicate growth expectations.
    Benchmark: 15-25 is typical; varies by sector.

    Args:
        market_price: Current stock price per share
        earnings_per_share: Earnings per share (trailing twelve months)

    Returns:
        P/E ratio (e.g., 18.5)
    """
    if earnings_per_share == 0:
        return float("inf") if market_price > 0 else 0.0
    return market_price / earnings_per_share


def forward_pe(market_price: float, estimated_eps: float) -> float:
    """
    Calculate Forward Price-to-Earnings Ratio.

    Uses estimated future EPS instead of trailing. Useful for growth companies.

    Args:
        market_price: Current stock price per share
        estimated_eps: Estimated earnings per share for next fiscal year

    Returns:
        Forward P/E ratio
    """
    if estimated_eps == 0:
        return float("inf") if market_price > 0 else 0.0
    return market_price / estimated_eps


def pb_ratio(market_price: float, book_value_per_share: float) -> float:
    """
    Calculate Price-to-Book (P/B) Ratio.

    Compares market value to book value. Values below 1.0 may indicate undervaluation.
    Benchmark: < 1.5 is value territory; > 3.0 is growth territory.

    Args:
        market_price: Current stock price per share
        book_value_per_share: Book value per share (total equity / shares outstanding)

    Returns:
        P/B ratio
    """
    if book_value_per_share <= 0:
        return float("inf") if market_price > 0 else 0.0
    return market_price / book_value_per_share


def ps_ratio(market_cap: float, total_revenue: float) -> float:
    """
    Calculate Price-to-Sales (P/S) Ratio.

    Useful for valuing companies with no earnings. Lower is generally better.
    Benchmark: < 2.0 is considered cheap; > 10 is expensive.

    Args:
        market_cap: Total market capitalization
        total_revenue: Total annual revenue

    Returns:
        P/S ratio
    """
    if total_revenue <= 0:
        return float("inf") if market_cap > 0 else 0.0
    return market_cap / total_revenue


def peg_ratio(pe: float, earnings_growth_rate: float) -> float:
    """
    Calculate PEG (Price/Earnings-to-Growth) Ratio.

    Adjusts P/E for growth. PEG < 1.0 may indicate undervaluation relative to growth.

    Args:
        pe: Price-to-Earnings ratio
        earnings_growth_rate: Expected annual earnings growth rate (percentage, e.g., 15.0 for 15%)

    Returns:
        PEG ratio (e.g., 0.85)
    """
    if earnings_growth_rate <= 0:
        return float("inf") if pe > 0 else 0.0
    return pe / earnings_growth_rate


def ev_to_ebitda(
    market_cap: float,
    total_debt: float,
    cash: float,
    ebitda: float,
) -> float:
    """
    Calculate Enterprise Value to EBITDA ratio.

    EV/EBITDA is a capital-structure-neutral valuation metric.
    Benchmark: < 10 is generally attractive; varies by industry.

    Args:
        market_cap: Total market capitalization
        total_debt: Total debt (short-term + long-term)
        cash: Cash and cash equivalents
        ebitda: Earnings Before Interest, Taxes, Depreciation, and Amortization

    Returns:
        EV/EBITDA ratio
    """
    ev = market_cap + total_debt - cash
    if ebitda <= 0:
        return float("inf") if ev > 0 else 0.0
    return ev / ebitda


def earnings_yield(earnings_per_share: float, market_price: float) -> float:
    """
    Calculate Earnings Yield (inverse of P/E, expressed as percentage).

    Higher earnings yield = cheaper stock. Can be compared to bond yields.

    Args:
        earnings_per_share: Earnings per share (TTM)
        market_price: Current stock price

    Returns:
        Earnings yield percentage (e.g., 5.5 for 5.5%)
    """
    if market_price <= 0:
        return 0.0
    return (earnings_per_share / market_price) * 100


def price_to_fcf(market_cap: float, free_cash_flow: float) -> float:
    """
    Calculate Price-to-Free-Cash-Flow ratio.

    Measures price relative to actual cash generation. Lower is better.
    Benchmark: < 15 is attractive; > 30 is expensive.

    Args:
        market_cap: Total market capitalization
        free_cash_flow: Free cash flow (operating cash flow - capex)

    Returns:
        Price/FCF ratio
    """
    if free_cash_flow <= 0:
        return float("inf") if market_cap > 0 else 0.0
    return market_cap / free_cash_flow
