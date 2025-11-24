from langgraph.prebuilt import ToolNode

from src.tools.calculate_profit_tool import calculate_profit
from src.tools.extract_portfolio_data import extract_portfolio_data, _extract_portfolio_data_internal
from src.tools.get_symbol_name import get_symbol_names
from src.tools.get_ticker_price import get_ticker_prices
from src.tools.tavily_web_search import tavily_web_search
from src.tools.yf_tools import (
    get_balance_sheet,
    get_capital_gains,
    get_cash_flow,
    get_dividends,
    get_earnings,
    get_earnings_estimate,
    get_earnings_history,
    get_eps_revisions,
    get_eps_trend,
    get_growth_estimates,
    get_income_statement,
    get_insider_purchases,
    get_insider_transactions,
    get_institutional_holders,
    get_major_holders,
    get_mutualfund_holders,
    get_revenue_estimate,
)

# News agent tools - focused on web search and basic symbol/price lookup
news_agent_tools = ToolNode([tavily_web_search])

# Custom wrapper to inject context into extract_portfolio_data
def portfolio_tools_with_context(state):
    """Custom tool node that injects user context into extract_portfolio_data tool."""
    from langchain_core.tools import StructuredTool
    
    # Get user_id directly from state
    user_id = state.get("user_id")
    
    # Create a wrapped version of extract_portfolio_data with context pre-filled
    def extract_with_context(query: str, symbols: list[str] | None = None) -> str:
        context = {"user_id": user_id}
        return _extract_portfolio_data_internal(query, context, symbols)
    
    # Create a new tool with the same metadata but wrapped function
    extract_tool_with_context = StructuredTool.from_function(
        func=extract_with_context,
        name="extract_portfolio_data",
        description=extract_portfolio_data.description,
    )
    
    # Create ToolNode with the wrapped tool
    tools = [
        get_ticker_prices,
        get_symbol_names,
        calculate_profit,
        extract_tool_with_context,  # Use wrapped version
        # YFinance tools
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
    
    tool_node = ToolNode(tools)
    return tool_node.invoke(state)

# Use the custom wrapper instead of plain ToolNode
portfolio_agent_tools = portfolio_tools_with_context
