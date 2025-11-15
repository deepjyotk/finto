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
    # New portfolio pipeline nodes
    portfolio_reasoning = {
        "name": "portfolio_reasoning_node",
        "description": "Interprets query and outputs plan + required tools.",
        "max_ai_messages_allowed": 2,
    }
    context_loader = {
        "name": "context_loader_node",
        "description": "Loads user portfolio context (e.g., from Excel/DB).",
        "max_ai_messages_allowed": 1,
    }
    tool_executor = {
        "name": "tool_executor_node",
        "description": "LLM step that issues tool calls based on plan + context.",
        "max_ai_messages_allowed": 2,
    }
    computation = {
        "name": "computation_node",
        "description": "LLM-generated Python REPL to compute metrics.",
        "max_ai_messages_allowed": 1,
    }
    result_synthesizer = {
        "name": "result_synthesizer_node",
        "description": "Turns structured results into final user-friendly answer.",
        "max_ai_messages_allowed": 1,
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
