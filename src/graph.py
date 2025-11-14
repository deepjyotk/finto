# graph.py


import psycopg
from langchain_core.messages import AIMessage
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.graph import END, StateGraph
from psycopg.rows import dict_row

from src.core.enums import LLMModel, Nodes
from src.core.json_logging import logger_for
from src.core.settings import settings
from src.nodes.portfolio import PortfolioNode
from src.nodes.router import RouterNode
from src.nodes.web_search import WebSearchNode
from src.schemas.agent_state import AgentState
from src.tools.execute_tools import news_agent_tools, portfolio_agent_tools

logger = logger_for(__name__)

# Create a psycopg connection configured the way PostgresSaver expects
_pg_conn = psycopg.connect(settings.database_url, autocommit=True, row_factory=dict_row)
CHECKPOINTER = PostgresSaver(_pg_conn)
# Safe to call repeatedly; just ensures tables exist
CHECKPOINTER.setup()


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
    def get_graph(model: LLMModel) -> StateGraph:
        logger.info("Building agent graph with model: %s", model.value)

        builder = StateGraph(AgentState)

        news_node_instance = WebSearchNode()
        news_node = news_node_instance.get_runnable_sequence(model)

        portfolio_node_instance = PortfolioNode()
        portfolio_node = portfolio_node_instance.get_runnable_sequence(model)

        router_node_instance = RouterNode()
        router_node = router_node_instance.get_runnable_sequence(model)

        builder.add_node(Nodes.router.get("name"), router_node)
        builder.add_node(Nodes.news.get("name"), news_node)
        builder.add_node(Nodes.portfolio.get("name"), portfolio_node)
        builder.add_node(Nodes.news_tools.get("name"), news_agent_tools)
        builder.add_node(Nodes.portfolio_tools.get("name"), portfolio_agent_tools)
        builder.add_node(Nodes.unknown.get("name"), Graph._handle_unknown_node)

        builder.add_edge(Nodes.news.get("name"), Nodes.news_tools.get("name"))
        builder.add_edge(Nodes.portfolio_tools.get("name"), Nodes.portfolio.get("name"))

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
            Nodes.portfolio.get("name"),
            portfolio_node_instance.portfolio_agent_decision,
            {
                END: END,
                Nodes.portfolio_tools.get("name"): Nodes.portfolio_tools.get("name"),
            },
        )

        builder.add_edge(Nodes.unknown.get("name"), END)
        builder.add_edge(Nodes.news_tools.get("name"), END)

        builder.set_entry_point(Nodes.router.get("name"))

        # ✅ Now CHECKPOINTER is a real PostgresSaver, not a context manager
        graph = builder.compile(checkpointer=CHECKPOINTER)

        logger.info("Agent graph built successfully with Postgres-backed memory.")
        return graph
