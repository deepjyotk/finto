from langgraph.prebuilt import ToolNode

from src.tools.tavily_web_search import tavily_web_search

# News agent tools - focused on web search and basic symbol/price lookup
news_agent_tools = ToolNode([tavily_web_search])
