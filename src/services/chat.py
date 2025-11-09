"""Chat service - handles chat/agent query operations"""

from typing import Optional

from langchain_core.messages import HumanMessage
from langgraph.graph import StateGraph
from src.api.schemas.chat import ChatRequest
from src.core.json_logging import logger_for
from src.core.schema import AgentMessage
from src.graph import Graph
from src.nodes.web_search import WebSearchNode

logger = logger_for(__name__)


class ChatService:
    """Service layer for chat operations"""

    def __init__(self):
        """Initialize ChatService."""
        pass

    def query(self, request: ChatRequest) -> AgentMessage:
        """
        Run the agent on the provided question and return the AIMessage as AgentMessage.

        Args:
            question: User's question string

        Returns:
            AgentMessage response from the agent

        Raises:
            ValueError: If question is not a non-empty string
            RuntimeError: If OPENAI_API_KEY is not configured or the agent fails
        """
        try:
            question = request.message
            if not isinstance(question, str) or not question.strip():
                raise ValueError("question must be a non-empty string")

            graph = Graph.get_graph(request.model)

            out = graph.invoke(question)
            # MessageGraph.invoke() returns a list of messages directly
            if isinstance(out, list):
                # Get the last message's content
                last_message = out[-1]
                content = (
                    last_message.content if hasattr(last_message, "content") else str(last_message)
                )
            elif isinstance(out, dict):
                # Handle dict case for backward compatibility
                messages = out.get("messages", [])
                content = messages[-1].content if messages else ""
            else:
                content = str(out)

            return AgentMessage(role="assistant", content=content)
            # raw = self.computation_node.get_agent(request.model).invoke(
            #     {"messages": [{"role": "user", "content": question}]}
            # )
            # structured_response = raw.get("structured_response")
            # if structured_response and hasattr(structured_response, "computation"):
            #     content = structured_response.computation
            # else:
            #     content = str(structured_response)
        except Exception as e:
            logger.error("Agent run failed: %s", str(e), exc_info=True)
            raise RuntimeError(f"Agent run failed: {e}") from e
