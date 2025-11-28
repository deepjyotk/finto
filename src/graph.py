# graph.py


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


def _create_checkpointer() -> PostgresSaver:
    """
    Create a new PostgresSaver with a fresh psycopg connection.
    This avoids using a long-lived connection that may become closed by the server.
    """
    conn = psycopg.connect(settings.database_url, autocommit=True, row_factory=dict_row)
    saver = PostgresSaver(conn)
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

    @staticmethod
    def get_graph() -> StateGraph:
        logger.info("Building agent graph")

        builder = StateGraph(state_schema=AgentState, context_schema=AgentContext)

        news_node_instance = WebSearchNode()
        news_node = news_node_instance.get_runnable_sequence()

        portfolio_node_instance = PortfolioNode()
        portfolio_node = portfolio_node_instance.get_runnable_sequence()

        code_generation_node_instance = CodeGenerationNode()
        code_generation_node = code_generation_node_instance.get_runnable_sequence()

        final_response_node_instance = FinalResponseGenerationNode()
        final_response_node = final_response_node_instance.get_runnable_sequence()

        execute_code_node_instance = ExecuteCodeNode()
        execute_code_node = execute_code_node_instance.get_runnable_sequence()

        router_node_instance = RouterNode()
        router_node = router_node_instance.get_runnable_sequence()

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
            router_node_instance.router_decision,
            {
                Nodes.portfolio.get("name"): Nodes.portfolio.get("name"),
                Nodes.news.get("name"): Nodes.news.get("name"),
                Nodes.unknown.get("name"): Nodes.unknown.get("name"),
            },
        )

        builder.add_conditional_edges(
            Nodes.execute_code.get("name"),
            code_generation_node_instance.code_generation_agent_decision,
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
        checkpointer = _create_checkpointer()
        graph = builder.compile(checkpointer=checkpointer)

        logger.info("Agent graph built successfully with Postgres-backed memory.")
        return graph
