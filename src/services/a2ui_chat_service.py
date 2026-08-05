"""A2UI chat service.

Mirrors :class:`~src.services.chat_thesys_service.ThesysChatService` but
drives the LangGraph agent with ``astream_events`` instead of ``ainvoke``,
yielding a structured stream of :class:`~src.a2ui.schemas.A2UIEvent` objects.

The service is used exclusively when ``THESYS_ENABLED=false``.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any, AsyncIterator, List, Optional
from uuid import UUID

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.errors import GraphBubbleUp
from langgraph.types import Command

from src.a2ui.catalog import A2UI_HITL_SURFACE_ID
from src.a2ui.event_builder import build_a2ui_event
from src.a2ui.schemas import (
    A2UIEvent,
    make_a2ui_message,
    make_error,
    make_hitl_form,
    make_message_complete,
    make_step_complete,
    make_tool_result,
)
from src.a2ui.v0_9 import parse_llm_surface_document, serialize_stored_document
from src.api.schemas.a2ui_resume import A2UIResumeRequest
from src.api.schemas.thesys_chat import C1ChatRequest
from src.core.enums import ChatMode, LLMModel
from src.core.json_logging import logger_for
from src.core.settings import LLMSettings
from src.graph import Graph
from src.repositories.chat_repo import ChatRepository

logger = logger_for(__name__)

# Matches labels in ``event_builder._NODE_LABELS`` / ToolNode name — synthetic events on HITL interrupt.
_SCREENER_TOOL_NODE = "screener_analysis_tool_node"
_SCREENER_TOOL_TITLE = "Screening stocks"


def _iter_screener_hitl_ui_closure() -> Iterator[A2UIEvent]:
    """Synthetic events: interrupt aborts the tool node before LangChain emits tool_end / chain_end."""
    yield make_tool_result(
        tool_name="screener_analysis_tool",
        step_name=_SCREENER_TOOL_NODE,
        output_summary="Paused — confirm screening parameters in the side panel, then submit.",
        status="success",
    )
    yield make_step_complete(
        step_name=_SCREENER_TOOL_NODE,
        title=_SCREENER_TOOL_TITLE,
        status="done",
    )


class A2UIChatService:
    """Service layer for A2UI streaming chat backed by the shared LangGraph.

    The public method :meth:`stream` is an async generator that yields
    :class:`~src.a2ui.schemas.A2UIEvent` objects.  Callers feed the generator
    into :func:`~src.a2ui.sse_emitter.a2ui_sse_generator` to produce SSE.
    """

    def __init__(self, graph: Graph, chat_repo: ChatRepository) -> None:
        self.graph = graph
        self.chat_repo = chat_repo

    # ------------------------------------------------------------------
    # Helpers (copied from ThesysChatService for symmetry)
    # ------------------------------------------------------------------

    def _resolve_context_llm_models(
        self, chat_model: LLMModel
    ) -> tuple[LLMModel, LLMModel, LLMModel]:
        llm_cfg = LLMSettings()  # type: ignore[call-arg]
        if chat_model is LLMModel.Auto:
            return (
                LLMModel.from_model_name(llm_cfg.orchestrator_model),
                LLMModel.from_model_name(llm_cfg.portfolio_model),
                LLMModel.from_model_name(llm_cfg.web_search_model),
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
        chat_mode: ChatMode = ChatMode.OVERALL,
    ) -> tuple[RunnableConfig, dict[str, Any], dict[str, Any]]:
        config: RunnableConfig = {
            "configurable": {"thread_id": str(thread_id)},
            "callbacks": callbacks or [],
        }

        snapshot = await graph_runner.aget_state(config)
        history_message_length = len(snapshot.values.get("messages", [])) if snapshot else 0
        logger.info(
            f"[A2UI] History message length for thread {thread_id}: {history_message_length}"
        )

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
        context: dict[str, Any] = {
            "user_id": user_id,
            "orchestrator_model": orch,
            "portfolio_model": port,
            "screener_model": port,
            "web_search_model": web,
            "broker_id": broker_id,
            "chat_mode": chat_mode,
            "history_message_length": history_message_length,
        }

        return config, initial_state, context

    async def _build_resume_invocation(
        self,
        *,
        graph_runner: Any,
        thread_id: str,
        user_id: UUID,
        broker_id: UUID | None,
        callbacks: Optional[List[BaseCallbackHandler]],
        chat_model: LLMModel,
    ) -> tuple[RunnableConfig, dict[str, Any]]:
        """Config + context for Command(resume=...) after a HITL interrupt."""
        config: RunnableConfig = {
            "configurable": {"thread_id": str(thread_id)},
            "callbacks": callbacks or [],
        }

        snapshot = await graph_runner.aget_state(config)
        history_message_length = len(snapshot.values.get("messages", [])) if snapshot else 0

        orch, port, web = self._resolve_context_llm_models(chat_model)
        context: dict[str, Any] = {
            "user_id": user_id,
            "orchestrator_model": orch,
            "portfolio_model": port,
            "screener_model": port,
            "web_search_model": web,
            "broker_id": broker_id,
            "history_message_length": history_message_length,
        }

        return config, context

    # ------------------------------------------------------------------
    # Public streaming interface
    # ------------------------------------------------------------------

    async def stream(
        self,
        request: C1ChatRequest,
        user_id: UUID,
        callbacks: Optional[List[BaseCallbackHandler]] = None,
    ) -> AsyncIterator[A2UIEvent]:
        """Stream A2UI events for one chat turn.

        Yields structured events as the LangGraph agent executes.  On
        completion emits a ``message_complete`` event with the final answer
        and persists both messages to the database.

        Yields:
            A2UIEvent subclass instances (never raw CoT or prompt text).
        """

        question = request.message_payload.content
        if not isinstance(question, str) or not question.strip():
            yield make_error("message_payload.content must be a non-empty string")
            return

        thread_id = request.session_id
        session_id = UUID(thread_id)
        raw_broker = request.broker_id
        broker_id: UUID | None = UUID(raw_broker) if raw_broker else None

        await self.chat_repo.create_user_message(
            session_id=session_id,
            user_id=user_id,
            content=question,
        )
        await self.chat_repo.session.commit()

        graph_runner: Any = await self.graph.get_graph()
        final_content_parts: list[str] = []

        try:
            config, initial_state, context = await self._build_graph_invocation(
                graph_runner=graph_runner,
                thread_id=thread_id,
                question=question,
                user_id=user_id,
                broker_id=broker_id,
                callbacks=callbacks,
                chat_model=request.model_payload,
                chat_mode=request.chat_mode or ChatMode.OVERALL,
            )

            logger.info(f"[A2UI] Starting stream for session {thread_id}")

            try:
                async for lg_event in graph_runner.astream_events(
                    initial_state,
                    config=config,
                    context=context,
                    version="v2",
                ):
                    a2ui_evt = build_a2ui_event(lg_event)
                    if a2ui_evt is not None:
                        # Accumulate message chunks for final persistence
                        from src.a2ui.schemas import A2UIEventType

                        if a2ui_evt.event == A2UIEventType.MESSAGE_CHUNK:
                            final_content_parts.append(a2ui_evt.payload.chunk)
                        yield a2ui_evt
            except GraphBubbleUp:
                logger.info("[A2UI] Graph paused for human input (HITL)")

            snapshot = await graph_runner.aget_state(config)
            if snapshot and snapshot.interrupts:
                for evt in _iter_screener_hitl_ui_closure():
                    yield evt
                hitl_messages: list[dict[str, Any]] = []
                for intr in snapshot.interrupts:
                    iv = intr.value if isinstance(intr.value, dict) else {"value": intr.value}
                    for message in iv.get("a2ui_messages", []):
                        if isinstance(message, dict):
                            hitl_messages.append(message)
                            yield make_a2ui_message(message)
                    yield make_hitl_form(
                        thread_id=thread_id,
                        surface_id=A2UI_HITL_SURFACE_ID,
                        task=iv.get("task") if isinstance(iv.get("task"), str) else None,
                    )
                if hitl_messages:
                    persisted_hitl = serialize_stored_document(
                        hitl_messages, main_surface_id=A2UI_HITL_SURFACE_ID
                    )
                    yield make_message_complete(persisted_hitl)
                    await self.chat_repo.create_ai_message(
                        session_id=session_id, content=persisted_hitl
                    )
                    await self.chat_repo.session.commit()
                logger.info(f"[A2UI] HITL interrupt emitted for session {thread_id}")
                return

            raw_final_content = "".join(final_content_parts)
            surface_messages, persisted_content = parse_llm_surface_document(raw_final_content)
            for message in surface_messages:
                yield make_a2ui_message(message)
            yield make_message_complete(persisted_content)

            # Persist the AI message
            await self.chat_repo.create_ai_message(session_id=session_id, content=persisted_content)
            await self.chat_repo.session.commit()

            logger.info(f"[A2UI] Stream complete for session {thread_id}")

        except Exception as exc:
            logger.error("[A2UI] Stream error: %s", str(exc), exc_info=True)
            yield make_error(
                "An error occurred while processing your request. Please try again.",
                code=type(exc).__name__,
            )
        finally:
            await self.graph.close_graph(graph_runner)

    async def resume_stream(
        self,
        request: A2UIResumeRequest,
        user_id: UUID,
        callbacks: Optional[List[BaseCallbackHandler]] = None,
    ) -> AsyncIterator[A2UIEvent]:
        """Resume graph execution after :func:`interrupt` (e.g. screener HITL form submit)."""

        thread_id = request.session_id
        session_id = UUID(thread_id)
        raw_broker = request.broker_id
        broker_id: UUID | None = UUID(raw_broker) if raw_broker else None

        graph_runner: Any = await self.graph.get_graph()
        final_content_parts: list[str] = []

        try:
            config, context = await self._build_resume_invocation(
                graph_runner=graph_runner,
                thread_id=thread_id,
                user_id=user_id,
                broker_id=broker_id,
                callbacks=callbacks,
                chat_model=request.model_payload,
            )

            logger.info("[A2UI] Resume stream for session %s", thread_id)

            try:
                async for lg_event in graph_runner.astream_events(
                    Command(resume=request.form_values),
                    config=config,
                    context=context,
                    version="v2",
                ):
                    a2ui_evt = build_a2ui_event(lg_event)
                    if a2ui_evt is not None:
                        from src.a2ui.schemas import A2UIEventType

                        if a2ui_evt.event == A2UIEventType.MESSAGE_CHUNK:
                            final_content_parts.append(a2ui_evt.payload.chunk)
                        yield a2ui_evt
            except GraphBubbleUp:
                logger.info("[A2UI] Graph paused again during resume (HITL)")

            snapshot = await graph_runner.aget_state(config)
            if snapshot and snapshot.interrupts:
                for evt in _iter_screener_hitl_ui_closure():
                    yield evt
                resume_hitl_messages: list[dict[str, Any]] = []
                for intr in snapshot.interrupts:
                    iv = intr.value if isinstance(intr.value, dict) else {"value": intr.value}
                    for message in iv.get("a2ui_messages", []):
                        if isinstance(message, dict):
                            resume_hitl_messages.append(message)
                            yield make_a2ui_message(message)
                    yield make_hitl_form(
                        thread_id=thread_id,
                        surface_id=A2UI_HITL_SURFACE_ID,
                        task=iv.get("task") if isinstance(iv.get("task"), str) else None,
                    )
                if resume_hitl_messages:
                    persisted_resume_hitl = serialize_stored_document(
                        resume_hitl_messages, main_surface_id=A2UI_HITL_SURFACE_ID
                    )
                    yield make_message_complete(persisted_resume_hitl)
                    await self.chat_repo.create_ai_message(
                        session_id=session_id, content=persisted_resume_hitl
                    )
                    await self.chat_repo.session.commit()
                return

            yield make_a2ui_message(
                {
                    "version": "v0.9",
                    "deleteSurface": {
                        "surfaceId": A2UI_HITL_SURFACE_ID,
                    },
                }
            )

            raw_final_content = "".join(final_content_parts)
            surface_messages, persisted_content = parse_llm_surface_document(raw_final_content)
            for message in surface_messages:
                yield make_a2ui_message(message)
            yield make_message_complete(persisted_content)

            await self.chat_repo.create_ai_message(session_id=session_id, content=persisted_content)
            await self.chat_repo.session.commit()

            logger.info("[A2UI] Resume stream complete for session %s", thread_id)

        except Exception as exc:
            logger.error("[A2UI] Resume stream error: %s", str(exc), exc_info=True)
            yield make_error(
                "An error occurred while resuming your request. Please try again.",
                code=type(exc).__name__,
            )
        finally:
            await self.graph.close_graph(graph_runner)
