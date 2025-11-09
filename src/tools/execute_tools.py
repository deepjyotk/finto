from langgraph.prebuilt import ToolNode

from src.tools.get_symbol_name import get_symbol_name
from src.tools.get_ticker_price import get_ticker_price
from src.tools.calculate_profit_tool import calculate_profit
from src.tools.get_row_tool import get_holding_by_symbol
from src.tools.tavily_web_search import tavily_web_search
from src.tools.yf_tools import (
    get_major_holders,
    get_institutional_holders,
    get_mutualfund_holders,
    get_insider_purchases,
    get_insider_transactions,
    get_dividends,
    get_capital_gains,
    get_balance_sheet,
    get_cash_flow,
    get_income_statement,
    get_earnings_estimate,
    get_revenue_estimate,
    get_earnings_history,
    get_eps_trend,
    get_eps_revisions,
    get_growth_estimates,
    get_earnings,
)


# News agent tools - focused on web search and basic symbol/price lookup
news_agent_tools = ToolNode([tavily_web_search])

# Portfolio agent tools - focused on portfolio management and calculations
portfolio_agent_tools = ToolNode(
    [
        get_symbol_name,
        get_ticker_price,
        get_holding_by_symbol,
        calculate_profit,
        get_major_holders,
        get_institutional_holders,
        get_mutualfund_holders,
        get_insider_purchases,
        get_insider_transactions,
        get_dividends,
        get_capital_gains,
        get_balance_sheet,
        get_cash_flow,
        get_income_statement,
        get_earnings_estimate,
        get_revenue_estimate,
        get_earnings_history,
        get_eps_trend,
        get_eps_revisions,
        get_growth_estimates,
        get_earnings,
    ]
)
