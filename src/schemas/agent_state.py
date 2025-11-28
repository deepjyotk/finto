from typing import Annotated, List, Optional, TypedDict
from uuid import UUID

from langchain_core.messages import BaseMessage
from langgraph.graph import add_messages

from src.core.enums import LLMModel


class AgentState(TypedDict):
    """State for the StateGraph, holding the message history."""

    messages: Annotated[List[BaseMessage], add_messages]
    symbol_names: List[str]
    user_request: str
    attempts: int
    last_code_success: bool
    last_code: Optional[str]
    last_output: Optional[str]
    done: bool
    final_answer: Optional[str]


class AgentContext(TypedDict, total=False):
    """Context for the StateGraph, holding the user_id and model configurations."""

    user_id: UUID
    router_model: LLMModel
    portfolio_model: LLMModel
    news_model: LLMModel
