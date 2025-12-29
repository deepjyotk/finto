"""
Portfolio and financial analysis metrics.

This module provides 10 key metrics for portfolio analysis:
1. ROI - Return on Investment
2. ROE - Return on Equity
3. Sharpe Ratio - Risk-adjusted returns
4. Sortino Ratio - Downside risk-adjusted returns
5. CAGR - Compound Annual Growth Rate
6. Dividend Yield - Income return from dividends
7. Debt-to-Equity Ratio - Financial leverage
8. Current Ratio - Liquidity metric
9. Profit Margin - Profitability percentage
10. Win Rate - Trading success percentage
"""

from typing import Optional


def roi(gain: float, cost: float) -> float:
    """
    Calculate Return on Investment (ROI).

    ROI measures the percentage return on invested capital.
    Higher values indicate better investment returns.

    Args:
        gain: Total gain from investment (selling price - buying price)
        cost: Initial investment cost

    Returns:
        ROI percentage (e.g., 25.5 for 25.5%)
    """
    if cost <= 0:
        return 0.0
    return (gain / cost) * 100


def roe(net_income: float, shareholders_equity: float) -> float:
    """
    Calculate Return on Equity (ROE).

    ROE measures how efficiently a company uses shareholder equity to generate profit.
    Higher values indicate better efficiency.

    Args:
        net_income: Company's net income
        shareholders_equity: Total shareholders' equity

    Returns:
        ROE percentage (e.g., 15.3 for 15.3%)
    """
    if shareholders_equity <= 0:
        return 0.0
    return (net_income / shareholders_equity) * 100


def sharpe_ratio(
    portfolio_return: float, risk_free_rate: float, portfolio_volatility: float
) -> float:
    """
    Calculate Sharpe Ratio.

    Sharpe Ratio measures risk-adjusted returns. It shows excess return per unit of risk.
    Higher values indicate better risk-adjusted performance.
    Benchmark: 1.0+ is good, 2.0+ is very good, 3.0+ is excellent.

    Args:
        portfolio_return: Expected portfolio return (as decimal, e.g., 0.12 for 12%)
        risk_free_rate: Risk-free rate of return (as decimal)
        portfolio_volatility: Portfolio standard deviation (as decimal, e.g., 0.15 for 15%)

    Returns:
        Sharpe Ratio (higher is better)
    """
    if portfolio_volatility <= 0:
        return 0.0
    return (portfolio_return - risk_free_rate) / portfolio_volatility


def sortino_ratio(
    portfolio_return: float, risk_free_rate: float, downside_deviation: float
) -> float:
    """
    Calculate Sortino Ratio.

    Sortino Ratio is like Sharpe Ratio but only penalizes downside volatility (losses).
    Ignores upside volatility, making it more suitable for evaluating downside risk.
    Higher values indicate better risk-adjusted performance.

    Args:
        portfolio_return: Expected portfolio return (as decimal, e.g., 0.12 for 12%)
        risk_free_rate: Risk-free rate of return (as decimal)
        downside_deviation: Downside deviation (volatility of negative returns)

    Returns:
        Sortino Ratio (higher is better)
    """
    if downside_deviation <= 0:
        return 0.0
    return (portfolio_return - risk_free_rate) / downside_deviation


def cagr(beginning_value: float, ending_value: float, years: float) -> float:
    """
    Calculate Compound Annual Growth Rate (CAGR).

    CAGR represents the average annual growth rate over a period.
    Smooths out volatility to show consistent growth rate.

    Args:
        beginning_value: Initial investment value
        ending_value: Final investment value
        years: Number of years (can be fractional, e.g., 2.5)

    Returns:
        CAGR percentage (e.g., 15.7 for 15.7% annual growth)
    """
    if beginning_value <= 0 or years <= 0:
        return 0.0
    return ((ending_value / beginning_value) ** (1 / years) - 1) * 100


def dividend_yield(annual_dividend: float, current_stock_price: float) -> float:
    """
    Calculate Dividend Yield.

    Dividend Yield measures income return from dividends relative to stock price.
    Useful for income-focused investors.

    Args:
        annual_dividend: Total annual dividend per share
        current_stock_price: Current stock price

    Returns:
        Dividend Yield percentage (e.g., 3.5 for 3.5%)
    """
    if current_stock_price <= 0:
        return 0.0
    return (annual_dividend / current_stock_price) * 100


def debt_to_equity_ratio(total_debt: float, total_equity: float) -> float:
    """
    Calculate Debt-to-Equity Ratio.

    Measures financial leverage - how much debt a company uses relative to equity.
    Lower values indicate less financial risk.
    Benchmark: 1.0 or lower is generally considered healthy.

    Args:
        total_debt: Total debt of the company
        total_equity: Total shareholders' equity

    Returns:
        Debt-to-Equity Ratio (e.g., 0.75 means 75% debt for every 100% equity)
    """
    if total_equity <= 0:
        return float("inf") if total_debt > 0 else 0.0
    return total_debt / total_equity


def current_ratio(current_assets: float, current_liabilities: float) -> float:
    """
    Calculate Current Ratio.

    Measures short-term liquidity - ability to pay short-term obligations.
    Shows how many times a company can cover current liabilities with current assets.
    Benchmark: 1.5-3.0 is generally considered healthy.

    Args:
        current_assets: Total current assets
        current_liabilities: Total current liabilities

    Returns:
        Current Ratio (e.g., 2.1 means 2.1x coverage of liabilities)
    """
    if current_liabilities <= 0:
        return float("inf") if current_assets > 0 else 0.0
    return current_assets / current_liabilities


def profit_margin(net_income: float, revenue: float) -> float:
    """
    Calculate Profit Margin.

    Measures profitability - what percentage of revenue becomes profit.
    Higher values indicate better profitability.
    Varies by industry (tech typically 20%+, retail typically 5-10%).

    Args:
        net_income: Net income (bottom line profit)
        revenue: Total revenue

    Returns:
        Profit Margin percentage (e.g., 12.5 for 12.5%)
    """
    if revenue <= 0:
        return 0.0
    return (net_income / revenue) * 100


def win_rate(winning_trades: int, total_trades: int) -> float:
    """
    Calculate Win Rate.

    Measures trading success percentage - what fraction of trades are profitable.
    Used to evaluate trading strategy effectiveness.
    Benchmark: 50%+ is generally acceptable; 60%+ is very good.

    Args:
        winning_trades: Number of profitable trades
        total_trades: Total number of trades executed

    Returns:
        Win Rate percentage (e.g., 62.5 for 62.5% win rate)
    """
    if total_trades <= 0:
        return 0.0
    return (winning_trades / total_trades) * 100


def portfolio_return(beginning_value: float, ending_value: float) -> float:
    """
    Calculate portfolio return as a decimal.

    Simple return calculation showing percentage gain/loss on investment.
    Used as input for risk-adjusted metrics like Sharpe and Sortino ratios.

    Args:
        beginning_value: Initial portfolio value
        ending_value: Final portfolio value

    Returns:
        Return as decimal (e.g., 0.15 for 15% return, -0.05 for -5% loss)
    """
    if beginning_value <= 0:
        return 0.0
    return (ending_value - beginning_value) / beginning_value


def downside_deviation(returns_series: list, risk_free_rate: float = 0.0) -> float:
    """
    Calculate downside deviation (semi-standard deviation).

    Measures volatility of negative returns below a threshold (typically risk-free rate).
    Used in Sortino Ratio to focus only on downside risk.
    Only considers returns below the threshold, ignoring upside volatility.

    Args:
        returns_series: List or array of periodic returns (as decimals, e.g., [0.02, -0.01, 0.03])
        risk_free_rate: Minimum acceptable return threshold (as decimal, default 0.0)

    Returns:
        Downside deviation as decimal (e.g., 0.08 for 8%)
    """
    if not returns_series or len(returns_series) == 0:
        return 0.0

    # Calculate downside returns (only negative deviations from risk_free_rate)
    downside_returns = [min(0, r - risk_free_rate) for r in returns_series]

    # Calculate sum of squared downside returns
    sum_squared = sum(r**2 for r in downside_returns)

    # Calculate downside deviation (using n-1 for sample)
    n = len(returns_series)
    if n <= 1:
        return 0.0

    downside_var = sum_squared / (n - 1)
    return downside_var**0.5


# Additional helper functions for batch calculations


def calculate_all_metrics(
    symbol_name: str,
    beginning_value: float,
    ending_value: float,
    years: float,
    net_income: Optional[float] = None,
    equity: Optional[float] = None,
    debt: Optional[float] = None,
    revenue: Optional[float] = None,
    dividend: Optional[float] = None,
    stock_price: Optional[float] = None,
    volatility: float = 0.15,
    risk_free_rate: float = 0.05,
) -> dict:
    """
    Calculate all available metrics for a stock in one call.

    Args:
        symbol_name: Stock symbol name
        beginning_value: Initial investment value
        ending_value: Final investment value
        years: Investment period in years
        net_income: Net income (optional)
        equity: Shareholders' equity (optional)
        debt: Total debt (optional)
        revenue: Total revenue (optional)
        dividend: Annual dividend per share (optional)
        stock_price: Current stock price (optional)
        volatility: Portfolio volatility (default 0.15 for 15%)
        risk_free_rate: Risk-free rate (default 0.05 for 5%)

    Returns:
        Dictionary with all calculated metrics
    """
    metrics = {
        "symbol": symbol_name,
        "roi": roi(ending_value - beginning_value, beginning_value),
        "cagr": cagr(beginning_value, ending_value, years),
        "sharpe_ratio": sharpe_ratio(
            cagr(beginning_value, ending_value, years) / 100, risk_free_rate, volatility
        ),
    }

    if net_income is not None and equity is not None:
        metrics["roe"] = roe(net_income, equity)

    if debt is not None and equity is not None:
        metrics["debt_to_equity"] = debt_to_equity_ratio(debt, equity)

    if revenue is not None and net_income is not None:
        metrics["profit_margin"] = profit_margin(net_income, revenue)

    if dividend is not None and stock_price is not None:
        metrics["dividend_yield"] = dividend_yield(dividend, stock_price)

    return metrics
