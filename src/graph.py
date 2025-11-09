"""Graph definition for the finance assistant agent."""

from typing import Annotated, Final, List, TypedDict

from langchain_core.messages import BaseMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnableSequence
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, MessageGraph, StateGraph
from langgraph.graph.message import add_messages

from src.core.enums import LLMModel, Nodes
from src.core.json_logging import logger_for
from src.nodes.portfolio import PortfolioNode
from src.nodes.router import RouterNode
from src.nodes.web_search import WebSearchNode
from src.tools.execute_tools import news_agent_tools, portfolio_agent_tools

logger = logger_for(__name__)


class Graph:
    """Main graph builder for the finance assistant."""


    # @staticmethod
    # def router_decision_wrapper(model: LLMModel):
    #     """
    #     Create a router decision function bound to a specific model.

    #     Args:
    #         model: The LLM model to use for routing decisions

    #     Returns:
    #         A function that takes state and returns routing decision
    #     """
    #     router_node = RouterNode()

    #     def router_decision(state: AgentState) -> str:

    #         """Make routing decision based on state."""
    #         return router_node.router_decision(state["messages"], model)

    #     return router_decision

    @staticmethod
    def _handle_unknown_node(state: List[BaseMessage]) -> List[BaseMessage]:
        """
        Handle unknown/unsupported queries.

        Args:
            state: Current message state

        Returns:
            Updated message state with error response
        """
        from langchain_core.messages import AIMessage

        logger.warning("Unknown node reached - query could not be routed")
        error_msg = AIMessage(
            content="I'm sorry, I couldn't determine how to handle your request. Please try rephrasing your question."
        )
        return {"messages": [error_msg]}

    @staticmethod
    def get_graph(model: LLMModel) -> MessageGraph:
        """
        Build and return the complete agent graph.

        Args:
            model: The LLM model to use for all nodes

        Returns:
            StateGraph: The compiled graph ready for execution
        """
        logger.info("Building agent graph with model: %s", model.value)

        # Initialize builder with AgentState
        # builder = StateGraph(AgentState)
        builder = MessageGraph()

        # Create node instances
        news_node_instance = WebSearchNode()
        news_node = news_node_instance.get_runnable_sequence(model)
        portfolio_node_instance = PortfolioNode()
        portfolio_node = portfolio_node_instance.get_runnable_sequence(model)
        router_node_instance = RouterNode()
        router_node = router_node_instance.get_runnable_sequence(model)

        # Add nodes
        builder.add_node(Nodes.router.get("name"), router_node)
        builder.add_node(Nodes.news.get("name"), news_node)
        builder.add_node(Nodes.portfolio.get("name"), portfolio_node)
        builder.add_node(Nodes.news_tools.get("name"), news_agent_tools) 
        builder.add_node(Nodes.portfolio_tools.get("name"), portfolio_agent_tools)

        # Add unknown node
        builder.add_node(Nodes.unknown.get("name"), Graph._handle_unknown_node)


        # Add edges
        builder.add_edge(Nodes.news.get("name"), Nodes.news_tools.get("name"))
        # builder.add_edge(Nodes.portfolio.get("name"), Nodes.portfolio_tools.get("name"))
        builder.add_edge(Nodes.portfolio_tools.get("name"), Nodes.portfolio.get("name"))

        # router_decision = Graph.router_decision_wrapper(model)

        # Add conditional edges from START
        builder.add_conditional_edges(
            Nodes.router.get("name"),
            router_node_instance.router_decision,
            {
                Nodes.portfolio.get("name"): Nodes.portfolio.get("name"),
                Nodes.news.get("name"): Nodes.news.get("name"),
            },
        )

        builder.add_conditional_edges(
            Nodes.portfolio.get("name"),
            portfolio_node_instance.portfolio_agent_decision, # --> iske 2 output hoga END or Nodes.portfolio_tools.get("name")
            {
                END: END,
                Nodes.portfolio_tools.get("name"): Nodes.portfolio_tools.get("name")
            },
        )

        # Ending edges
        builder.add_edge(Nodes.unknown.get("name"), END)
        builder.add_edge(Nodes.news_tools.get("name"), END)
        
        

        logger.info("Agent graph built successfully")
        builder.set_entry_point(Nodes.router.get("name"))
        # builder.set_finish_point(END)
        
        compiled_graph = builder.compile()
        return compiled_graph

