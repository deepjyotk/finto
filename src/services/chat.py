"""Chat service - handles chat/agent query operations"""

from uuid import UUID

from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig

from src.api.schemas.chat import ChatRequest
from src.core.json_logging import logger_for
from src.core.schema import AgentMessage
from src.graph import Graph

logger = logger_for(__name__)


class ChatService:
    """Service layer for chat operations"""

    def __init__(self):
        """Initialize ChatService."""

    def query(self, request: ChatRequest, thread_id: UUID, user_id: UUID) -> AgentMessage:
        """
        Run the agent on the provided question and return the AIMessage as AgentMessage.

        Args:
            request: Chat request containing message and model
            thread_id: Thread ID for conversation persistence

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

            logger.info(f"Starting chat session with thread_id: {thread_id}")

            # Create config with thread_id for persistence
            config: RunnableConfig = {"configurable": {"thread_id": str(thread_id)}}

            # StateGraph expects an AgentState with a messages key
            initial_state = {"messages": [HumanMessage(content=question)]}
            context = {"user_id": user_id}

            out = graph.invoke(initial_state, config=config, context=context)

            if isinstance(out, list):
                # Get the last message's content
                last_message = out[-1]
                content = (
                    last_message.content if hasattr(last_message, "content") else str(last_message)
                )
            elif isinstance(out, dict):
                # StateGraph returns a state dict with "messages"
                messages = out.get("messages", [])
                content = messages[-1].content if messages else ""
            else:
                content = str(out)

            return AgentMessage(role="assistant", content=content)
        except Exception as e:
            logger.error("Agent run failed: %s", str(e), exc_info=True)
            raise RuntimeError(f"Agent run failed: {e}") from e
