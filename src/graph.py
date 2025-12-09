# graph.py

import asyncio
from typing import Awaitable, Callable

from langchain_core.messages import AIMessage
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.graph import END, StateGraph
from psycopg_pool import AsyncConnectionPool

from src.core.enums import Nodes
from src.core.json_logging import logger_for
from src.core.settings import settings
from src.nodes.code_generation import CodeGenerationNode
from src.nodes.execute_code import ExecuteCodeNode
from src.nodes.final_response_generation import FinalResponseGenerationNode
from src.nodes.portfolio import PortfolioNode
from src.nodes.router import RouterNode
from src.nodes.web_search import WebSearchNode
from src.schemas.agent_state import AgentContext, AgentState
from src.tools.execute_tools import news_agent_tools

logger = logger_for(__name__)


# Singleton async Postgres saver following LangGraph’s recommended pattern
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
    We keep the pool small to stay under PgBouncer/session-mode limits and
    initialize checkpoint tables on first use.
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
                    min_size=1,
                    max_size=5,
                )
                # Ensure pool is ready before passing to saver
                await _CHECKPOINTER_POOL.open(wait=True)
                _CHECKPOINTER = AsyncPostgresSaver(_CHECKPOINTER_POOL)
                await _CHECKPOINTER.setup()  # ensure checkpoint tables exist
            except Exception:
                # Tear down partial initialization so the next caller can retry cleanly
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
    """Main graph builder for the finance assistant."""

    def __init__(
        self,
        news_node_instance: WebSearchNode,
        portfolio_node: PortfolioNode,
        code_generation_node: CodeGenerationNode,
        final_response_node: FinalResponseGenerationNode,
        execute_code_node: ExecuteCodeNode,
        router_node: RouterNode,
        checkpointer_factory: Callable[[], Awaitable[AsyncPostgresSaver]] = _create_checkpointer,
    ):
        self.news_node_instance = news_node_instance
        self.portfolio_node = portfolio_node
        self.code_generation_node = code_generation_node
        self.final_response_node = final_response_node
        self.execute_code_node = execute_code_node
        self.router_node = router_node
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

        news_node = self.news_node_instance.get_runnable_sequence()

        portfolio_node = self.portfolio_node.get_runnable_sequence()

        code_generation_node = self.code_generation_node.get_runnable_sequence()

        final_response_node = self.final_response_node.get_runnable_sequence()

        execute_code_node = self.execute_code_node.get_runnable_sequence()

        router_node = self.router_node.get_runnable_sequence()

        builder.add_node(Nodes.router.get("name"), router_node)
        builder.add_node(Nodes.news.get("name"), news_node)
        builder.add_node(Nodes.portfolio.get("name"), portfolio_node)
        builder.add_node(Nodes.news_tools.get("name"), news_agent_tools)
        builder.add_node(Nodes.code_generation.get("name"), code_generation_node)
        builder.add_node(Nodes.final_response.get("name"), final_response_node)
        builder.add_node(Nodes.execute_code.get("name"), execute_code_node)
        builder.add_node(Nodes.unknown.get("name"), Graph._handle_unknown_node)

        builder.add_edge(Nodes.news.get("name"), Nodes.news_tools.get("name"))
        builder.add_edge(Nodes.portfolio.get("name"), Nodes.code_generation.get("name"))
        builder.add_edge(Nodes.code_generation.get("name"), Nodes.execute_code.get("name"))

        builder.add_conditional_edges(
            Nodes.router.get("name"),
            self.router_node.router_decision,
            {
                Nodes.portfolio.get("name"): Nodes.portfolio.get("name"),
                Nodes.news.get("name"): Nodes.news.get("name"),
                Nodes.unknown.get("name"): Nodes.unknown.get("name"),
            },
        )

        builder.add_conditional_edges(
            Nodes.execute_code.get("name"),
            self.code_generation_node.code_generation_agent_decision,
            {
                Nodes.code_generation.get("name"): Nodes.code_generation.get("name"),
                Nodes.final_response.get("name"): Nodes.final_response.get("name"),
                END: END,
            },
        )

        builder.add_edge(Nodes.unknown.get("name"), END)
        builder.add_edge(Nodes.final_response.get("name"), END)
        builder.add_edge(Nodes.news_tools.get("name"), END)

        builder.set_entry_point(Nodes.router.get("name"))

        # Create a fresh checkpointer for this graph build to avoid stale DB connections
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
