# graph.py

import asyncio
from typing import Callable

import psycopg
from langchain_core.messages import AIMessage
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.graph import END, StateGraph
from psycopg.rows import dict_row

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


class AsyncPostgresSaver(PostgresSaver):
    """
    Thin async wrapper around PostgresSaver so LangGraph's async runner
    can use the checkpoint store without hitting NotImplementedError.
    """

    async def aget_tuple(self, config):
        return await asyncio.to_thread(self.get_tuple, config)

    async def aget(self, config):
        return await asyncio.to_thread(self.get, config)

    async def alist(self, config, *, filter=None, before=None, limit=None):
        return await asyncio.to_thread(
            lambda: list(self.list(config, filter=filter, before=before, limit=limit))
        )

    async def aput(self, config, checkpoint, metadata, new_versions):
        return await asyncio.to_thread(self.put, config, checkpoint, metadata, new_versions)

    async def aput_writes(self, config, writes, task_id, task_path=""):
        return await asyncio.to_thread(self.put_writes, config, writes, task_id, task_path)

    async def adelete_thread(self, thread_id):
        return await asyncio.to_thread(self.delete_thread, thread_id)


def _create_checkpointer() -> PostgresSaver:
    """
    Create a new PostgresSaver with a fresh psycopg connection.
    This avoids using a long-lived connection that may become closed by the server.
    """
    conn = psycopg.connect(settings.database_url, autocommit=True, row_factory=dict_row)
    saver = AsyncPostgresSaver(conn)
    # Ensure required tables exist
    try:
        saver.setup()
    except Exception:
        # If setup fails, close the connection and re-raise
        try:
            conn.close()
        except Exception:
            pass
        raise
    return saver


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
        checkpointer_factory: Callable[[], PostgresSaver] = _create_checkpointer,
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
        checkpointer = self._checkpointer_factory()
        graph = builder.compile(checkpointer=checkpointer)

        logger.info("Agent graph built successfully with Postgres-backed memory.")
        return graph
