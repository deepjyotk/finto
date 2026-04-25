"""
Risk metrics — deterministic formulas beyond Sharpe/Sortino.

Functions:
  beta, alpha, treynor_ratio, information_ratio, value_at_risk_historical,
  calmar_ratio, omega_ratio, quick_ratio, interest_coverage_ratio
"""

from typing import List


def beta(asset_returns: List[float], market_returns: List[float]) -> float:
    """
    Calculate Beta — sensitivity of asset returns to market returns.

    Beta > 1: more volatile than market. Beta < 1: less volatile.
    Beta = 1: moves with market. Beta < 0: inversely correlated.

    Args:
        asset_returns: List of periodic asset returns (decimals, e.g., [0.02, -0.01])
        market_returns: List of periodic market returns (same length & period)

    Returns:
        Beta coefficient (e.g., 1.2 means 20% more volatile than market)
    """
    n = len(asset_returns)
    if n < 2 or n != len(market_returns):
        return 0.0

    mean_a = sum(asset_returns) / n
    mean_m = sum(market_returns) / n

    covar = sum((a - mean_a) * (m - mean_m) for a, m in zip(asset_returns, market_returns)) / (
        n - 1
    )
    var_m = sum((m - mean_m) ** 2 for m in market_returns) / (n - 1)

    if var_m == 0:
        return 0.0
    return covar / var_m


def alpha(
    portfolio_return: float,
    risk_free_rate: float,
    beta_value: float,
    market_return: float,
) -> float:
    """
    Calculate Jensen's Alpha — excess return over CAPM-predicted return.

    Positive alpha = outperformance. Negative = underperformance.

    Args:
        portfolio_return: Actual portfolio return (decimal, e.g., 0.15 for 15%)
        risk_free_rate: Risk-free rate (decimal)
        beta_value: Portfolio beta
        market_return: Market return (decimal)

    Returns:
        Alpha as decimal (e.g., 0.03 for 3% outperformance)
    """
    expected = risk_free_rate + beta_value * (market_return - risk_free_rate)
    return portfolio_return - expected


def treynor_ratio(portfolio_return: float, risk_free_rate: float, beta_value: float) -> float:
    """
    Calculate Treynor Ratio — return per unit of systematic risk (beta).

    Like Sharpe but uses beta instead of total volatility. Higher is better.
    Best for well-diversified portfolios where unsystematic risk is eliminated.

    Args:
        portfolio_return: Portfolio return (decimal)
        risk_free_rate: Risk-free rate (decimal)
        beta_value: Portfolio beta

    Returns:
        Treynor ratio (higher is better)
    """
    if beta_value == 0:
        return 0.0
    return (portfolio_return - risk_free_rate) / beta_value


def information_ratio(
    portfolio_return: float, benchmark_return: float, tracking_error: float
) -> float:
    """
    Calculate Information Ratio — active return per unit of active risk.

    Measures a manager's ability to generate excess returns relative to a benchmark.
    Benchmark: 0.5+ is good, 1.0+ is excellent.

    Args:
        portfolio_return: Portfolio return (decimal)
        benchmark_return: Benchmark return (decimal)
        tracking_error: Standard deviation of active returns (decimal)

    Returns:
        Information ratio
    """
    if tracking_error <= 0:
        return 0.0
    return (portfolio_return - benchmark_return) / tracking_error


def value_at_risk_historical(returns: List[float], confidence_level: float = 0.95) -> float:
    """
    Calculate Historical Value at Risk (VaR).

    Estimates the maximum expected loss at a given confidence level over one period.
    E.g., 95% VaR of 0.03 means there's a 5% chance of losing more than 3%.

    Args:
        returns: List of periodic returns (decimals)
        confidence_level: Confidence level (default 0.95 for 95%)

    Returns:
        VaR as a positive decimal (e.g., 0.03 for 3% loss threshold)
    """
    if not returns or len(returns) < 2:
        return 0.0
    sorted_returns = sorted(returns)
    index = int((1 - confidence_level) * len(sorted_returns))
    index = max(0, min(index, len(sorted_returns) - 1))
    return abs(sorted_returns[index])


def calmar_ratio(annualized_return: float, max_drawdown_value: float) -> float:
    """
    Calculate Calmar Ratio — annualized return divided by max drawdown.

    Measures return relative to worst peak-to-trough decline. Higher is better.
    Benchmark: 3.0+ is excellent.

    Args:
        annualized_return: Annualized return (decimal, e.g., 0.15 for 15%)
        max_drawdown_value: Maximum drawdown as positive decimal (e.g., 0.20 for 20%)

    Returns:
        Calmar ratio
    """
    if max_drawdown_value <= 0:
        return 0.0
    return annualized_return / max_drawdown_value


def omega_ratio(returns: List[float], threshold: float = 0.0) -> float:
    """
    Calculate Omega Ratio — probability-weighted gains over losses.

    Sum of returns above threshold / sum of returns below threshold.
    Omega > 1 indicates more upside than downside. Higher is better.

    Args:
        returns: List of periodic returns (decimals)
        threshold: Minimum acceptable return (decimal, default 0.0)

    Returns:
        Omega ratio (e.g., 1.5 means 50% more upside than downside)
    """
    if not returns:
        return 0.0
    gains = sum(max(0, r - threshold) for r in returns)
    losses = sum(max(0, threshold - r) for r in returns)
    if losses == 0:
        return float("inf") if gains > 0 else 0.0
    return gains / losses


def quick_ratio(current_assets: float, inventory: float, current_liabilities: float) -> float:
    """
    Calculate Quick Ratio (Acid-Test Ratio).

    Like current ratio but excludes inventory (less liquid asset).
    Benchmark: 1.0+ is healthy.

    Args:
        current_assets: Total current assets
        inventory: Inventory value
        current_liabilities: Total current liabilities

    Returns:
        Quick ratio (e.g., 1.3 means 1.3x coverage excluding inventory)
    """
    if current_liabilities <= 0:
        return float("inf") if (current_assets - inventory) > 0 else 0.0
    return (current_assets - inventory) / current_liabilities


def interest_coverage_ratio(ebit: float, interest_expense: float) -> float:
    """
    Calculate Interest Coverage Ratio.

    Measures ability to pay interest on debt. Higher is safer.
    Benchmark: 3.0+ is healthy; < 1.5 is risky.

    Args:
        ebit: Earnings Before Interest and Taxes
        interest_expense: Total interest expense (positive number)

    Returns:
        Interest coverage ratio (e.g., 5.0 means can cover interest 5x)
    """
    if interest_expense <= 0:
        return float("inf") if ebit > 0 else 0.0
    return ebit / interest_expense
