"""
Profitability & efficiency metrics — deterministic formulas.

Functions:
  roa, gross_margin, operating_margin, ebitda_margin,
  asset_turnover, inventory_turnover, receivable_turnover,
  dupont_roe
"""


def roa(net_income: float, total_assets: float) -> float:
    """
    Calculate Return on Assets (ROA).

    Measures how efficiently a company uses its assets to generate profit.
    Higher is better. Benchmark: 5%+ is good; varies by industry.

    Args:
        net_income: Net income (TTM)
        total_assets: Total assets

    Returns:
        ROA percentage (e.g., 8.5 for 8.5%)
    """
    if total_assets <= 0:
        return 0.0
    return (net_income / total_assets) * 100


def gross_margin(revenue: float, cost_of_goods_sold: float) -> float:
    """
    Calculate Gross Margin percentage.

    Shows what percentage of revenue remains after direct production costs.
    Higher is better. Benchmark: 40%+ for tech, 20-30% for manufacturing.

    Args:
        revenue: Total revenue
        cost_of_goods_sold: Cost of goods sold (COGS)

    Returns:
        Gross margin percentage (e.g., 45.0 for 45%)
    """
    if revenue <= 0:
        return 0.0
    return ((revenue - cost_of_goods_sold) / revenue) * 100


def operating_margin(operating_income: float, revenue: float) -> float:
    """
    Calculate Operating Margin percentage.

    Measures profitability from core operations (before interest and taxes).
    Benchmark: 15%+ is strong; varies by industry.

    Args:
        operating_income: Operating income (EBIT)
        revenue: Total revenue

    Returns:
        Operating margin percentage (e.g., 22.0 for 22%)
    """
    if revenue <= 0:
        return 0.0
    return (operating_income / revenue) * 100


def ebitda_margin(ebitda: float, revenue: float) -> float:
    """
    Calculate EBITDA Margin percentage.

    Measures cash profitability before non-cash charges and financing.
    Benchmark: 20%+ is healthy.

    Args:
        ebitda: Earnings Before Interest, Taxes, Depreciation, and Amortization
        revenue: Total revenue

    Returns:
        EBITDA margin percentage (e.g., 28.0 for 28%)
    """
    if revenue <= 0:
        return 0.0
    return (ebitda / revenue) * 100


def asset_turnover(revenue: float, total_assets: float) -> float:
    """
    Calculate Asset Turnover Ratio.

    Measures how efficiently assets generate revenue. Higher is more efficient.
    Benchmark: 1.0+ for capital-light businesses; 0.3-0.5 for capital-heavy.

    Args:
        revenue: Total annual revenue
        total_assets: Average total assets

    Returns:
        Asset turnover ratio (e.g., 1.5 means $1.50 revenue per $1 of assets)
    """
    if total_assets <= 0:
        return 0.0
    return revenue / total_assets


def inventory_turnover(cost_of_goods_sold: float, average_inventory: float) -> float:
    """
    Calculate Inventory Turnover Ratio.

    Measures how many times inventory is sold and replaced per period.
    Higher is better (faster moving inventory). Benchmark: 5-10 for retail.

    Args:
        cost_of_goods_sold: Cost of goods sold (annual)
        average_inventory: Average inventory value

    Returns:
        Inventory turnover ratio (e.g., 8.0 means inventory turns over 8x/year)
    """
    if average_inventory <= 0:
        return 0.0
    return cost_of_goods_sold / average_inventory


def receivable_turnover(net_credit_sales: float, average_receivables: float) -> float:
    """
    Calculate Receivable Turnover Ratio.

    Measures how efficiently a company collects its receivables.
    Higher is better. Can compute Days Sales Outstanding as 365 / receivable_turnover.

    Args:
        net_credit_sales: Net credit sales (annual)
        average_receivables: Average accounts receivable

    Returns:
        Receivable turnover ratio (e.g., 12.0 means collections 12x/year = ~30 day cycle)
    """
    if average_receivables <= 0:
        return 0.0
    return net_credit_sales / average_receivables


def dupont_roe(
    net_income: float,
    revenue: float,
    total_assets: float,
    shareholders_equity: float,
) -> dict:
    """
    DuPont Analysis — decompose ROE into three components.

    ROE = Profit Margin × Asset Turnover × Equity Multiplier
    Helps identify whether ROE is driven by profitability, efficiency, or leverage.

    Args:
        net_income: Net income
        revenue: Total revenue
        total_assets: Total assets
        shareholders_equity: Total shareholders' equity

    Returns:
        Dict with keys: profit_margin, asset_turnover, equity_multiplier, roe
        All values as percentages except equity_multiplier (ratio).
    """
    pm = (net_income / revenue * 100) if revenue > 0 else 0.0
    at = (revenue / total_assets) if total_assets > 0 else 0.0
    em = (total_assets / shareholders_equity) if shareholders_equity > 0 else 0.0
    roe_val = (pm / 100) * at * em * 100  # back to percentage

    return {
        "profit_margin_pct": round(pm, 4),
        "asset_turnover": round(at, 4),
        "equity_multiplier": round(em, 4),
        "roe_pct": round(roe_val, 4),
    }
