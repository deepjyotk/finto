"""Core enums for the application."""

from enum import Enum


class LLMModel(str, Enum):
    """Supported AI models."""

    GPT4oMini = "gpt-4o-mini"
    GPT4p1 = "gpt-4.1"


class Nodes:
    """Node name constants."""

    router = {
        "name": "router_node",
        "description": "Router node for deciding between portfolio and news nodes.",
        "max_ai_messages_allowed": 2,
    }
    news = {
        "name": "news_node",
        "description": "News node for fetching news from the web.",
        "max_ai_messages_allowed": 8,
    }
    portfolio = {
        "name": "portfolio_node",
        "description": "Portfolio node for fetching portfolio information.",
        "max_ai_messages_allowed": 8,
    }
    news_tools = {
        "name": "news_agent_tools",
        "description": "Tools node for news agent - web search and symbol lookup.",
    }
    portfolio_tools = {
        "name": "portfolio_agent_tools",
        "description": "Tools node for portfolio agent - portfolio management and calculations.",
    }
    unknown = {
        "name": "unknown_node",
        "description": "Unknown node for handling unknown queries.",
    }
