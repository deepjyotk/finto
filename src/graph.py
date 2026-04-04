# graph.py

import asyncio
from typing import Awaitable, Callable

from langchain_core.messages import AIMessage
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import ToolNode
from psycopg_pool import AsyncConnectionPool

from src.core.enums import Nodes
from src.core.json_logging import logger_for
from src.core.settings import settings
from src.nodes.final_response_generation import FinalResponseGenerationNode
from src.nodes.orchestrator import OrchestratorNode
from src.schemas.agent_state import AgentContext, AgentState

logger = logger_for(__name__)


# Singleton async Postgres saver following LangGraph's recommended pattern
_CHECKPOINTER: AsyncPostgresSaver | None = None
_CHECKPOINTER_POOL: AsyncConnectionPool | None = None
_CHECKPOINTER_LOCK = asyncio.Lock()


async def _reset_checkpointer_pool() -> None:
    """Close and clear the shared checkpointer pool so it can be recreated fresh."""
    global _CHECKPOINTER, _CHECKPOINTER_POOL
    async with _CHECKPOINTER_LOCK:
        if _CHECKPOINTER_POOL and not _CHECKPOINTER_POOL.closed:
            await _CHECKPOINTER_POOL.close()
        _CHECKPOINTER = None
        _CHECKPOINTER_POOL = None


async def _get_checkpointer() -> AsyncPostgresSaver:
    """
    Create (once) and return an AsyncPostgresSaver backed by a shared async pool.

    The checkpointer is used by LangGraph to save state between graph node executions.
    Each graph execution (e.g., a chat request) uses the checkpointer multiple times:
    - After orchestrator node
    - After portfolio/web_search worker tool nodes
    - After final response node

    With concurrent graph executions (multiple users chatting), we need enough
    connections to avoid blocking. With a connection pooler (40 pool, 200 max clients),
    we can use 8 connections to handle 4-8 concurrent graph executions efficiently.
    """
    global _CHECKPOINTER, _CHECKPOINTER_POOL
    async with _CHECKPOINTER_LOCK:
        # If the pool was closed (or never created), rebuild it and the saver
        if _CHECKPOINTER_POOL is None or _CHECKPOINTER_POOL.closed:
            _CHECKPOINTER = None
            _CHECKPOINTER_POOL = None

        if _CHECKPOINTER is None:
            try:
                _CHECKPOINTER_POOL = AsyncConnectionPool(
                    conninfo=settings.database_url,
                    min_size=2,
                    max_size=8,
                )
                await _CHECKPOINTER_POOL.open(wait=True)
                _CHECKPOINTER = AsyncPostgresSaver(_CHECKPOINTER_POOL)

                # Setup checkpoint tables (requires autocommit for CREATE INDEX CONCURRENTLY)
                setup_pool = AsyncConnectionPool(
                    conninfo=settings.database_url,
                    min_size=1,
                    max_size=1,
                    kwargs={"autocommit": True},
                )
                try:
                    await setup_pool.open(wait=True)
                    setup_saver = AsyncPostgresSaver(setup_pool)
                    await setup_saver.setup()
                finally:
                    await setup_pool.close()

            except Exception:
                if _CHECKPOINTER_POOL and not _CHECKPOINTER_POOL.closed:
                    await _CHECKPOINTER_POOL.close()
                _CHECKPOINTER = None
                _CHECKPOINTER_POOL = None
                raise
    return _CHECKPOINTER


async def _create_checkpointer() -> AsyncPostgresSaver:
    """Factory wrapper to align with dependency injection pattern."""
    return await _get_checkpointer()


class Graph:
    """Main graph builder for the finance assistant.

    Architecture (hub-and-spoke with sequential tool collection):

        orchestrator_node
            ├─► financial_analysis_tool_node ──┐
            ├─► web_search_tool_node ────────┤
            │   (both loop back to ──────────┘
            │    orchestrator_node)
            └─► final_response_generation_node ──► END

    The orchestrator is a supervisor agent that can call the worker tools
    multiple times in sequence (e.g. portfolio first to identify stocks, then
    web_search with those stock names).  Once it has all needed context it routes to
    final_response_generation_node which formats the user-facing answer.
    """

    def __init__(
        self,
        orchestrator_node: OrchestratorNode,
        final_response_node: FinalResponseGenerationNode,
        checkpointer_factory: Callable[[], Awaitable[AsyncPostgresSaver]] = _create_checkpointer,
    ):
        self.orchestrator_node = orchestrator_node
        self.final_response_node = final_response_node
        self._checkpointer_factory = checkpointer_factory

    @staticmethod
    def _handle_unknown_node(state: AgentState) -> AgentState:
        logger.warning("Unknown node reached - query could not be routed")
        messages = state.get("messages", [])
        return {
            **state,
            "messages": messages
            + [
                AIMessage(
                    content=(
                        "I'm sorry, I couldn't determine how to handle your request. "
                        "Please try rephrasing your question."
                    )
                )
            ],
        }

    async def get_graph(self) -> StateGraph:
        logger.info("Building agent graph")

        builder = StateGraph(state_schema=AgentState, context_schema=AgentContext)

        # Worker ToolNodes — each wraps a self-contained tool created by the
        # respective node class.  The orchestrator owns (and binds to) these tools;
        # we reuse the same tool objects for the ToolNodes so names/schemas match.
        financial_analysis_tool_node = ToolNode(
            [self.orchestrator_node._financial_analysis_tool],
            name=Nodes.financial_analysis_worker_tools.get("name"),
        )
        web_search_tool_node = ToolNode(
            [self.orchestrator_node._web_search_tool],
            name=Nodes.web_search_worker_tools.get("name"),
        )

        final_response_node = self.final_response_node.get_runnable_sequence()
        orchestrator_node = self.orchestrator_node.get_runnable_sequence()

        builder.add_node(Nodes.orchestrator.get("name"), orchestrator_node)
        builder.add_node(
            Nodes.financial_analysis_worker_tools.get("name"),
            financial_analysis_tool_node,
        )
        builder.add_node(Nodes.web_search_worker_tools.get("name"), web_search_tool_node)
        builder.add_node(Nodes.final_response.get("name"), final_response_node)
        builder.add_node(Nodes.unknown.get("name"), Graph._handle_unknown_node)

        # Worker tool nodes always return to the orchestrator for the next decision
        builder.add_edge(
            Nodes.financial_analysis_worker_tools.get("name"),
            Nodes.orchestrator.get("name"),
        )
        builder.add_edge(Nodes.web_search_worker_tools.get("name"), Nodes.orchestrator.get("name"))

        # Orchestrator routes to workers (if it still has tool calls to make) or
        # to final_response when context collection is complete
        builder.add_conditional_edges(
            Nodes.orchestrator.get("name"),
            self.orchestrator_node.orchestrator_decision,
            {
                Nodes.financial_analysis_worker_tools.get(
                    "name"
                ): Nodes.financial_analysis_worker_tools.get("name"),
                Nodes.web_search_worker_tools.get("name"): Nodes.web_search_worker_tools.get(
                    "name"
                ),
                Nodes.final_response.get("name"): Nodes.final_response.get("name"),
                Nodes.unknown.get("name"): Nodes.unknown.get("name"),
            },
        )

        builder.add_edge(Nodes.unknown.get("name"), END)
        builder.add_edge(Nodes.final_response.get("name"), END)

        builder.set_entry_point(Nodes.orchestrator.get("name"))

        checkpointer = await self._checkpointer_factory()
        graph = builder.compile(checkpointer=checkpointer)

        logger.info("Agent graph built successfully with Postgres-backed memory.")
        return graph

    async def close_graph(self, _graph_runner: StateGraph) -> None:
        """
        Placeholder for symmetry with callers; nothing to close per run because the
        Postgres saver holds a shared pool for the process lifetime.
        """
        return None

    async def reset_checkpointer(self) -> None:
        """Reset the shared checkpointer/pool after connection errors."""
        await _reset_checkpointer_pool()
