"""Thesys chat service wired to the LangGraph flow (mirrors ChatService)."""

from uuid import UUID

import psycopg
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig

from src.api.schemas.thesys_chat import C1ChatRequest, ChatSessionSchema
from src.core.enums import LLMModel
from src.core.json_logging import logger_for
from src.core.schema import AgentMessage
from src.graph import Graph
from src.repositories.chat_repo import ChatRepository

logger = logger_for(__name__)


class ThesysChatService:
    """Service layer for Thesys chat operations using the shared LangGraph."""

    def __init__(self, graph: Graph, chat_repo: ChatRepository):
        self.graph = graph
        self.chat_repo = chat_repo

    async def create_session(self, user_id: UUID) -> ChatSessionSchema:
        """
        Create a new chat session for a user.

        Args:
            user_id: The user ID

        Returns:
            ChatSessionSchema: The newly created session schema
        """
        chat_session = await self.chat_repo.create_session(user_id)
        # Commit the transaction to persist the session
        await self.chat_repo.session.commit()
        return ChatSessionSchema(
            session_id=str(chat_session.chat_session_id),
            started_at=chat_session.started_at.isoformat(),
        )

    async def get_user_sessions(self, user_id: UUID) -> list[ChatSessionSchema]:
        """
        Get all chat sessions for a user, sorted by most recent first.

        Args:
            user_id: The user ID

        Returns:
            List of ChatSessionSchema objects sorted by started_at descending
        """
        sessions = await self.chat_repo.get_sessions_by_user_id(user_id)
        return [
            ChatSessionSchema(
                session_id=str(session.chat_session_id),
                started_at=session.started_at.isoformat(),
            )
            for session in sessions
        ]

    async def query(self, request: C1ChatRequest, user_id: UUID) -> AgentMessage:
        """
        Run the LangGraph agent for a Thesys C1 chat request.

        Returns:
            AgentMessage: Final assistant message produced by the graph.
        """
        # Thesys may wrap content in <content thesys="true"> and HTML-encode it; clean it.
        from src.core.llm import _strip_thesys_wrapping

        question = _strip_thesys_wrapping(request.message_payload.content)

        if not isinstance(question, str) or not question.strip():
            raise ValueError("message_payload.content must be a non-empty string")

        thread_id = request.session_id
        session_id = UUID(thread_id)

        # Persist the User message to the chat_messages table
        await self.chat_repo.create_user_message(
            session_id=session_id,
            user_id=user_id,
            content=question,
        )

        graph_runner = await self.graph.get_graph()

        logger.info(f"Starting Thesys chat session with session_id: {thread_id}")

        config: RunnableConfig = {"configurable": {"thread_id": str(thread_id)}}

        initial_state = {
            "messages": [HumanMessage(content=question)],
            "symbol_names": [],
            "user_request": question,
            "attempts": 0,
            "last_code_success": True,
            "last_code": None,
            "last_output": None,
            "done": False,
            "final_answer": None,
        }
        context = {
            "user_id": user_id,
            "router_model": LLMModel.GPT4oMini,
            "portfolio_model": LLMModel.GPT4p1,
            "news_model": LLMModel.GPT4oMini,
        }

        try:
            try:
                out = await graph_runner.ainvoke(initial_state, config=config, context=context)
            except Exception as e:
                msg = str(e).lower()
                if (
                    "connection is closed" in msg
                    or "server closed the connection" in msg
                    or isinstance(e, psycopg.OperationalError)
                ):
                    logger.warning(
                        "DB connection error detected, rebuilding graph and retrying once"
                    )
                    graph_runner = await self.graph.get_graph()
                    out = await graph_runner.ainvoke(initial_state, config=config, context=context)
                else:
                    raise

            if isinstance(out, list):
                last_message = out[-1]
                content = (
                    last_message.content if hasattr(last_message, "content") else str(last_message)
                )
            elif isinstance(out, dict):
                messages = out.get("messages", [])
                content = messages[-1].content if messages else ""
            else:
                content = str(out)

            # Persist the AI message to the chat_messages table
            await self.chat_repo.create_ai_message(
                session_id=session_id,
                content=content,
            )
            # Commit the transaction to persist both messages
            await self.chat_repo.session.commit()

            return AgentMessage(role="assistant", content=content)
        except Exception as e:
            logger.error("Thesys agent run failed: %s", str(e), exc_info=True)
            raise RuntimeError(f"Thesys agent run failed: {e}") from e
