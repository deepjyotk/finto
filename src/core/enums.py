"""Core enums for the application."""

from enum import Enum
from typing import Any, Dict


class LLMModel(Enum):
    """Supported AI models with associated LLM kwargs.

    Each enum member stores both the model name and its configuration kwargs.
    Access the model name with `.value['model']` or `.model_name`
    Access the kwargs with `.value['kwargs']` or `.llm_kwargs`
    """

    # GPT-3.5 Series
    GPT35Turbo = {"model": "gpt-3.5-turbo", "kwargs": {"temperature": 0}}
    GPT35Turbo16K = {"model": "gpt-3.5-turbo-16k", "kwargs": {"temperature": 0}}

    # GPT-4 Series
    GPT4 = {"model": "gpt-4", "kwargs": {"temperature": 0}}
    GPT4Turbo = {"model": "gpt-4-turbo", "kwargs": {"temperature": 0}}
    GPT4TurboPreview = {"model": "gpt-4-turbo-preview", "kwargs": {"temperature": 0}}
    GPT432K = {"model": "gpt-4-32k", "kwargs": {"temperature": 0}}

    # GPT-4o Series (Omni - multimodal)
    GPT4o = {"model": "gpt-4o", "kwargs": {"temperature": 0.5}}
    GPT4oMini = {"model": "gpt-4o-mini", "kwargs": {"temperature": 0}}
    GPT4o20240806 = {"model": "gpt-4o-2024-08-06", "kwargs": {"temperature": 0}}  # Dated version

    # GPT-4.1 Series
    GPT4p1 = {"model": "gpt-4.1", "kwargs": {"temperature": 0.5}}
    GPT4p1Mini = {"model": "gpt-4.1-mini", "kwargs": {"temperature": 0}}
    GPT4p1Nano = {"model": "gpt-4.1-nano", "kwargs": {"temperature": 0}}

    # GPT-5 Series
    GPT5 = {"model": "gpt-5", "kwargs": {}}  # gpt-5 only supports temperature=1
    GPT5Chat = {"model": "gpt-5-chat", "kwargs": {"temperature": 0}}
    GPT5p1 = {
        "model": "gpt-5.1",
        "kwargs": {"temperature": 1},
    }  # gpt-5.1 only supports temperature=1
    GPT5p1Instant = {"model": "gpt-5.1-instant", "kwargs": {"temperature": 0}}  # !Not available yet
    # GPT5p1Thinking = {"model": "gpt-5.1-thinking", "kwargs": {"temperature": 0}} # !Not available yet

    # O-Series (Reasoning Models - don't support temperature parameter)
    O1 = {"model": "o1", "kwargs": {}}
    O1Preview = {"model": "o1-preview", "kwargs": {}}
    O1Mini = {"model": "o1-mini", "kwargs": {}}
    O3 = {"model": "o3", "kwargs": {}}
    O3Pro = {"model": "o3-pro", "kwargs": {}}
    O4Mini = {"model": "o4-mini", "kwargs": {}}
    O4MiniHigh = {"model": "o4-mini-high", "kwargs": {}}

    @property
    def model_name(self) -> str:
        """Get the model name string."""
        return self.value["model"]

    @property
    def llm_kwargs(self) -> Dict[str, Any]:
        """Get the LLM kwargs dict."""
        return self.value["kwargs"]

    def __str__(self) -> str:
        """Return the model name when converted to string."""
        return self.model_name

    def __repr__(self) -> str:
        """Return a representation of the enum member."""
        return f"<LLMModel.{self.name}: {self.model_name}>"

    @classmethod
    def from_model_name(cls, model_name: str) -> "LLMModel":
        """Get enum member by model name string."""
        for member in cls:
            if member.model_name == model_name:
                return member
        raise ValueError(f"No LLMModel found with model name: {model_name}")


class Nodes:
    """Node name constants."""

    router = {
        "name": "router_node",
        "description": "Router node for deciding between portfolio and news nodes.",
        "max_ai_messages_allowed": 60,
    }
    news = {
        "name": "news_node",
        "description": "News node for fetching news from the web.",
        "max_ai_messages_allowed": 60,
    }
    portfolio = {
        "name": "portfolio_node",
        "description": "Portfolio node for fetching portfolio information.",
        "max_ai_messages_allowed": 60,
    }
    code_generation = {
        "name": "code_generation_node",
        "description": "LLM node that generates Python code for portfolio analysis.",
        "max_ai_messages_allowed": 60,
    }
    execute_code = {
        "name": "execute_code_node",
        "description": "Node that executes generated Python code and captures output.",
    }
    news_tools = {
        "name": "news_agent_tools",
        "description": "Tools node for news agent - web search and symbol lookup.",
    }
    final_response = {
        "name": "final_response_generation_node",
        "description": "Node that crafts the final answer from code execution output and the user request.",
        "max_ai_messages_allowed": 20,
    }
    unknown = {
        "name": "unknown_node",
        "description": "Unknown node for handling unknown queries.",
    }
