"""Chat service - handles chat/agent query operations"""

from src.api.schemas.chat import ChatRequest
from src.core.schema import AgentMessage
from src.nodes.computation import ComputationNode


class ChatService:
    """Service layer for chat operations"""

    def __init__(self, computation_node: ComputationNode):
        """Initialize ChatService."""
        self.computation_node = computation_node

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
        question = request.message
        if not isinstance(question, str) or not question.strip():
            raise ValueError("question must be a non-empty string")

        try:
            raw = self.computation_node.get_agent(request.model).invoke(
                {"messages": [{"role": "user", "content": question}]}
            )
            output = raw["structured_response"]
            return output
        except Exception as e:
            raise RuntimeError(f"Agent run failed: {e}") from e
