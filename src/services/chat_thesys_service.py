"""Thesys chat service wired to the LangGraph flow (mirrors ChatService)."""

from typing import Any, List, Optional
from uuid import UUID

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig

from src.api.schemas.thesys_chat import (
    C1ChatRequest,
    ChatSessionSchema,
    MessageItem,
    SessionMessageConfig,
)
from src.core.enums import LLMModel
from src.core.json_logging import logger_for
from src.core.schema import AgentMessage
from src.core.settings import LLMSettings
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

    async def get_user_sessions(
        self, user_id: UUID, *, page: int = 1, page_limit: int = 10
    ) -> tuple[list[ChatSessionSchema], int]:
        """
        Get paginated chat sessions for a user, sorted by most recent first.

        Args:
            user_id: The user ID
            page: Page number to fetch (1-indexed)
            page_limit: Maximum number of sessions per page

        Returns:
            Tuple containing list of ChatSessionSchema objects and total session count
        """
        offset = (page - 1) * page_limit
        sessions, total_sessions = await self.chat_repo.get_sessions_by_user_id_paginated(
            user_id, limit=page_limit, offset=offset
        )
        session_schemas = [
            ChatSessionSchema(
                session_id=str(session.chat_session_id),
                started_at=session.started_at.isoformat(),
            )
            for session in sessions
        ]
        return session_schemas, total_sessions

    async def get_session_messages(self, session_id: UUID, user_id: UUID) -> SessionMessageConfig:
        """
        Get all messages for a session, verifying the session belongs to the user.

        Args:
            session_id: The session ID
            user_id: The user ID (for verification)

        Returns:
            SessionMessageConfig with session_id and messages list

        Raises:
            ValueError: If session not found or doesn't belong to user
        """
        # Verify session exists and belongs to user
        session = await self.chat_repo.get_session_by_id(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")
        if session.user_id != user_id:
            raise ValueError(f"Session {session_id} does not belong to user {user_id}")

        # Get messages for the session
        messages = await self.chat_repo.get_messages_by_session_id(session_id)

        return SessionMessageConfig(
            session_id=str(session_id),
            messages=[
                MessageItem(
                    id=str(msg.id),
                    seq_no=msg.seq_no,
                    message_payload=msg.content,
                    message_type=msg.message_type,
                )
                for msg in messages
            ],
        )

    async def delete_session(self, session_id: UUID, user_id: UUID) -> None:
        """
        Delete a session and all its associated messages, verifying the session belongs to the user.

        Args:
            session_id: The session ID to delete
            user_id: The user ID (for verification)

        Raises:
            ValueError: If session not found or doesn't belong to user
        """
        # Verify session exists and belongs to user
        session = await self.chat_repo.get_session_by_id(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")
        if session.user_id != user_id:
            raise ValueError(f"Session {session_id} does not belong to user {user_id}")

        # Delete the session and its messages
        deleted = await self.chat_repo.delete_session(session_id)
        if not deleted:
            raise ValueError(f"Session {session_id} could not be deleted")

        # Commit the transaction
        await self.chat_repo.session.commit()

    def _resolve_context_llm_models(
        self, chat_model: LLMModel
    ) -> tuple[LLMModel, LLMModel, LLMModel]:
        """Orchestrator / portfolio / web-search models for :class:`AgentContext`.

        :attr:`LLMModel.Auto` uses per-role defaults from settings; any other
        choice applies the resolved OpenAI member to all three roles.
        """
        settings = LLMSettings()
        if chat_model is LLMModel.Auto:
            return (
                LLMModel.from_model_name(settings.orchestrator_model),
                LLMModel.from_model_name(settings.portfolio_model),
                LLMModel.from_model_name(settings.web_search_model),
            )
        resolved = chat_model.resolve_to_openai_member()
        return (resolved, resolved, resolved)

    async def _build_graph_invocation(
        self,
        *,
        graph_runner: Any,
        thread_id: str,
        question: str,
        user_id: UUID,
        broker_id: UUID | None,
        callbacks: Optional[List[BaseCallbackHandler]],
        chat_model: LLMModel,
    ) -> tuple[RunnableConfig, dict[str, Any], dict[str, Any]]:
        """Build the config, initial state, and agent context for a graph invocation.

        history_message_length captures how many messages existed in the thread
        before this turn (used by nodes to prune old iteration messages).
        We read the existing checkpoint via aget_state so the count reflects the
        real persisted history rather than a hard-coded zero.
        """
        config: RunnableConfig = {
            "configurable": {"thread_id": str(thread_id)},
            "callbacks": callbacks or [],
        }

        snapshot = await graph_runner.aget_state(config)
        history_message_length = len(snapshot.values.get("messages", [])) if snapshot else 0
        logger.info(f"History message length for thread {thread_id}: {history_message_length}")

        initial_state: dict[str, Any] = {
            "messages": [HumanMessage(content=question)],
            "symbol_names": [],
            "user_request": question,
            "attempts": 0,
            "last_code_success": True,
            "last_code": None,
            "last_output": None,
            "done": False,
            "final_rendered_ui_answer": None,
        }

        orch, port, web = self._resolve_context_llm_models(chat_model)

        logger.info(f"Orchestrator model: {orch.model_name}")
        logger.info(f"Portfolio model: {port.model_name}")
        logger.info(f"Web search model: {web.model_name}")

        context: dict[str, Any] = {
            "user_id": user_id,
            "orchestrator_model": orch,
            "portfolio_model": port,
            "web_search_model": web,
            "broker_id": broker_id,
            "history_message_length": history_message_length,
        }

        return config, initial_state, context

    async def query(
        self,
        request: C1ChatRequest,
        user_id: UUID,
        callbacks: Optional[List[BaseCallbackHandler]] = None,
    ) -> AgentMessage:
        """
        Run the LangGraph agent for a Thesys C1 chat request.

        Args:
            request: Thesys chat request
            user_id: User UUID
            callbacks: Optional list of LangChain callbacks for tracking (e.g., credit tracking)

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
        raw_broker = request.broker_id
        broker_id: UUID | None = UUID(raw_broker) if raw_broker else None

        # Persist the User message to the chat_messages table
        await self.chat_repo.create_user_message(
            session_id=session_id,
            user_id=user_id,
            content=question,
        )

        graph_runner = await self.graph.get_graph()
        try:
            logger.info(f"Starting Thesys chat session with session_id: {thread_id}")

            config, initial_state, context = await self._build_graph_invocation(
                graph_runner=graph_runner,
                thread_id=thread_id,
                question=question,
                user_id=user_id,
                broker_id=broker_id,
                callbacks=callbacks,
                chat_model=request.model_payload,
            )

            out = await graph_runner.ainvoke(initial_state, config=config, context=context)

            content = out.get("final_rendered_ui_answer") or ""

            await self.chat_repo.create_ai_message(session_id=session_id, content=content)
            await self.chat_repo.session.commit()

            return AgentMessage(role="assistant", content=content)
        except Exception as e:
            logger.error("Thesys agent run failed: %s", str(e), exc_info=True)
            raise RuntimeError(f"Thesys agent run failed: {e}") from e
        finally:
            await self.graph.close_graph(graph_runner)
