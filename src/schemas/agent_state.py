from typing import Annotated, List, TypedDict
from uuid import UUID

from langchain_core.messages import BaseMessage
from langgraph.graph import add_messages

from src.core.enums import LLMModel


class AgentState(TypedDict):
    """State for the StateGraph, holding the message history."""

    messages: Annotated[List[BaseMessage], add_messages]


class AgentContext(TypedDict, total=False):
    """Context for the StateGraph, holding the user_id and model configurations."""

    user_id: UUID
    router_model: LLMModel
    portfolio_model: LLMModel
    news_model: LLMModel
