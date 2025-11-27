from langgraph.prebuilt import ToolNode

from src.tools.extract_portfolio_data import extract_portfolio_data
from src.tools.get_symbol_name import get_symbol_names
from src.tools.tavily_web_search import tavily_web_search

# News agent tools - focused on web search and basic symbol/price lookup
news_agent_tools = ToolNode([tavily_web_search])

# Portfolio agent tools - focused on portfolio management and calculations
# YFinance and profit calculation functions are now available within extract_portfolio_data generated code
portfolio_agent_tools = ToolNode(
    [
        get_symbol_names,
        extract_portfolio_data,
    ]
)
