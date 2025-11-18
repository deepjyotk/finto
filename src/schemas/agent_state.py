from typing import Annotated, List, TypedDict
from uuid import UUID

from langchain_core.messages import BaseMessage
from langgraph.graph import add_messages


class AgentState(TypedDict):
    """State for the StateGraph, holding the message history."""

    messages: Annotated[List[BaseMessage], add_messages]


class AgentContext(TypedDict):
    """Context for the StateGraph, holding the user_id."""

    user_id: UUID
