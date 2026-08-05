"""
Register ALL tool functions (existing + new) into the global ToolRegistry.

Import this module once at startup (e.g., in financial_analysis_utils.py)
to populate ``registry`` before prompt building.
"""

# ── Existing: portfolio_metrics.py ──────────────────────────────────────────
from src.tools.portfolio_metrics import (
    cagr,
    calculate_all_metrics,
    current_ratio,
    debt_to_equity_ratio,
    dividend_yield,
    downside_deviation,
    portfolio_return,
    profit_margin,
    roe,
    roi,
    sharpe_ratio,
    sortino_ratio,
    win_rate,
)
from src.tools.registry import (
    DIVIDEND,
    EARNINGS_EST,
    EFFICIENCY,
    FINANCIAL_STMT,
    GROWTH,
    LEVERAGE,
    LIQUIDITY,
    OWNERSHIP,
    PORTFOLIO_CALC,
    PRICE_DATA,
    PROFITABILITY,
    RISK,
    SCREENING,
    TRADING,
    VALUATION,
    registry,
)

registry.register(roi, {PROFITABILITY, PORTFOLIO_CALC})
registry.register(roe, {PROFITABILITY})
registry.register(sharpe_ratio, {RISK})
registry.register(sortino_ratio, {RISK})
registry.register(cagr, {GROWTH})
registry.register(dividend_yield, {DIVIDEND})
registry.register(debt_to_equity_ratio, {LEVERAGE})
registry.register(current_ratio, {LIQUIDITY})
registry.register(profit_margin, {PROFITABILITY})
registry.register(win_rate, {TRADING})
registry.register(portfolio_return, {PORTFOLIO_CALC})
registry.register(downside_deviation, {RISK})
registry.register(calculate_all_metrics, {PORTFOLIO_CALC})

# ── Existing: portfolio_risk.py ─────────────────────────────────────────────
from src.tools.portfolio_risk import (
    download_prices,
    max_drawdown,
    max_drawdown_asset,
    portfolio_volatility,
)

registry.register(download_prices, {PRICE_DATA, RISK})
registry.register(portfolio_volatility, {RISK})
registry.register(max_drawdown, {RISK})
registry.register(max_drawdown_asset, {RISK})

# ── Existing: calculate_profit_tool.py ──────────────────────────────────────
from src.tools.calculate_profit_tool import calculate_profit_or_loss

registry.register(calculate_profit_or_loss, {PORTFOLIO_CALC})

# ── Existing: filters.py ────────────────────────────────────────────────────
from src.tools.filters import growth_filter, value_filter

registry.register(growth_filter, {SCREENING, GROWTH})
registry.register(value_filter, {SCREENING, VALUATION})

# ── Existing: yfinance wrappers (register individually by category) ─────────
from src.tools import yfinance_wrappers

registry.register(yfinance_wrappers.get_balance_sheet, {FINANCIAL_STMT})
registry.register(yfinance_wrappers.get_income_statement, {FINANCIAL_STMT})
registry.register(yfinance_wrappers.get_cash_flow, {FINANCIAL_STMT})
registry.register(yfinance_wrappers.get_ticker_price, {PRICE_DATA})
registry.register(yfinance_wrappers.get_last_close_price, {PRICE_DATA})
registry.register(yfinance_wrappers.get_ticker_info, {PRICE_DATA, VALUATION})
registry.register(yfinance_wrappers.get_dividends, {DIVIDEND, PORTFOLIO_CALC})
registry.register(yfinance_wrappers.get_capital_gains, {PORTFOLIO_CALC})
registry.register(yfinance_wrappers.get_earnings_estimate, {EARNINGS_EST})
registry.register(yfinance_wrappers.get_revenue_estimate, {EARNINGS_EST})
registry.register(yfinance_wrappers.get_earnings_history, {EARNINGS_EST})
registry.register(yfinance_wrappers.get_eps_trend, {EARNINGS_EST})
registry.register(yfinance_wrappers.get_eps_revisions, {EARNINGS_EST})
registry.register(yfinance_wrappers.get_growth_estimates, {EARNINGS_EST, GROWTH})
registry.register(yfinance_wrappers.get_major_holders, {OWNERSHIP})
registry.register(yfinance_wrappers.get_institutional_holders, {OWNERSHIP})
registry.register(yfinance_wrappers.get_mutualfund_holders, {OWNERSHIP})
registry.register(yfinance_wrappers.get_insider_purchases, {OWNERSHIP})
registry.register(yfinance_wrappers.get_insider_transactions, {OWNERSHIP})

# Check for batch price function
if hasattr(yfinance_wrappers, "get_last_close_prices_batch"):
    registry.register(yfinance_wrappers.get_last_close_prices_batch, {PRICE_DATA})

# ── NEW: valuation_metrics.py ───────────────────────────────────────────────
from src.tools.valuation_metrics import (
    earnings_yield,
    ev_to_ebitda,
    forward_pe,
    pb_ratio,
    pe_ratio,
    peg_ratio,
    price_to_fcf,
    ps_ratio,
)

registry.register_many(
    [
        pe_ratio,
        forward_pe,
        pb_ratio,
        ps_ratio,
        peg_ratio,
        ev_to_ebitda,
        earnings_yield,
        price_to_fcf,
    ],
    {VALUATION},
)

# ── NEW: profitability_efficiency_metrics.py ────────────────────────────────
from src.tools.profitability_efficiency_metrics import (
    asset_turnover,
    dupont_roe,
    ebitda_margin,
    gross_margin,
    inventory_turnover,
    operating_margin,
    receivable_turnover,
    roa,
)

registry.register_many([roa, gross_margin, operating_margin, ebitda_margin], {PROFITABILITY})
registry.register_many([asset_turnover, inventory_turnover, receivable_turnover], {EFFICIENCY})
registry.register(dupont_roe, {PROFITABILITY, EFFICIENCY})

# ── NEW: risk_metrics.py ────────────────────────────────────────────────────
from src.tools.risk_metrics import (
    alpha,
    beta,
    calmar_ratio,
    information_ratio,
    interest_coverage_ratio,
    omega_ratio,
    quick_ratio,
    treynor_ratio,
    value_at_risk_historical,
)

registry.register_many(
    [
        beta,
        alpha,
        treynor_ratio,
        information_ratio,
        value_at_risk_historical,
        calmar_ratio,
        omega_ratio,
    ],
    {RISK},
)
registry.register(quick_ratio, {LIQUIDITY})
registry.register(interest_coverage_ratio, {LEVERAGE})

# ── NEW: dividend_metrics.py ────────────────────────────────────────────────
from src.tools.dividend_metrics import (
    dividend_growth_rate,
    dividend_payout_ratio,
    retention_ratio,
    sustainable_growth_rate,
)

registry.register_many(
    [dividend_payout_ratio, dividend_growth_rate, retention_ratio, sustainable_growth_rate],
    {DIVIDEND, GROWTH},
)
