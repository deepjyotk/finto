"""Graph definition for the finance assistant agent."""

from typing import List, TypedDict

from langchain_core.messages import BaseMessage, AIMessage
from langgraph.graph import END, START, StateGraph

from src.core.enums import LLMModel, Nodes
from src.core.json_logging import logger_for
from src.nodes.portfolio import PortfolioNode
from src.nodes.router import RouterNode
from src.nodes.web_search import WebSearchNode
from src.tools.execute_tools import news_agent_tools, portfolio_agent_tools
from src.nodes.portfolio_reasoning import PortfolioReasoningNode
from src.nodes.portfolio_context_loader import PortfolioContextLoaderNode
from src.nodes.portfolio_tool_executor import PortfolioToolExecutorNode
from src.nodes.portfolio_computation import PortfolioComputationNode
from src.nodes.portfolio_result_synthesizer import PortfolioResultSynthesizerNode

logger = logger_for(__name__)


class AgentState(TypedDict):
    messages: List[BaseMessage]


class Graph:
    """Main graph builder for the finance assistant."""

    @staticmethod
    def _handle_unknown_node(state: AgentState) -> AgentState:
        logger.warning("Unknown node reached - query could not be routed")
        error_msg = AIMessage(content="I'm sorry, I couldn't determine how to handle your request. Please try rephrasing your question.")
        prev = state.get("messages", []) or []
        return {"messages": prev + [error_msg]}

    @staticmethod
    def get_graph(model: LLMModel):
        logger.info("Building agent graph with model: %s", model.value)
        builder = StateGraph(AgentState)

        # Instantiate runnables
        news_node = WebSearchNode().get_runnable_sequence(model)
        portfolio_node = PortfolioNode().get_runnable_sequence(model)  # legacy (not actively routed)
        router_node = RouterNode().get_runnable_sequence(model)
        reasoning_node = PortfolioReasoningNode().get_runnable_sequence(model)
        context_loader_node = PortfolioContextLoaderNode().get_runnable_sequence(model)
        tool_executor_node = PortfolioToolExecutorNode().get_runnable_sequence(model)
        computation_node = PortfolioComputationNode().get_runnable_sequence(model)
        result_synth_node = PortfolioResultSynthesizerNode().get_runnable_sequence(model)

        def wrap(runnable):
            def _run(state: AgentState) -> AgentState:
                prev = list(state.get("messages", []) or [])
                new = runnable.invoke(prev)
                # Runnables return list[BaseMessage] or single message; normalize and append
                if isinstance(new, list):
                    combined = prev + new
                elif new is None:
                    combined = prev
                else:
                    combined = prev + [new]
                return {"messages": combined}
            return _run

        # Register nodes
        builder.add_node(Nodes.router["name"], wrap(router_node))
        builder.add_node(Nodes.news["name"], wrap(news_node))
        builder.add_node(Nodes.portfolio["name"], wrap(portfolio_node))
        builder.add_node(Nodes.news_tools["name"], news_agent_tools)
        builder.add_node(Nodes.portfolio_tools["name"], portfolio_agent_tools)
        builder.add_node(Nodes.portfolio_reasoning["name"], wrap(reasoning_node))
        builder.add_node(Nodes.context_loader["name"], wrap(context_loader_node))
        builder.add_node(Nodes.tool_executor["name"], wrap(tool_executor_node))
        builder.add_node(Nodes.computation["name"], wrap(computation_node))
        builder.add_node(Nodes.result_synthesizer["name"], wrap(result_synth_node))
        builder.add_node(Nodes.unknown["name"], Graph._handle_unknown_node)

        # Static edges (news & portfolio pipeline)
        builder.add_edge(Nodes.news["name"], Nodes.news_tools["name"])
        builder.add_edge(Nodes.portfolio_reasoning["name"], Nodes.context_loader["name"])
        builder.add_edge(Nodes.context_loader["name"], Nodes.tool_executor["name"])
        builder.add_edge(Nodes.tool_executor["name"], Nodes.portfolio_tools["name"])
        builder.add_edge(Nodes.portfolio_tools["name"], Nodes.computation["name"])
        builder.add_edge(Nodes.computation["name"], Nodes.result_synthesizer["name"])
        builder.add_edge(Nodes.result_synthesizer["name"], END)

        # Conditional routing from router
        def _router_decider(state: AgentState):
            return RouterNode().router_decision(state.get("messages", []))

        builder.add_conditional_edges(
            Nodes.router["name"],
            _router_decider,
            {
                Nodes.portfolio["name"]: Nodes.portfolio_reasoning["name"],
                Nodes.news["name"]: Nodes.news["name"],
            },
        )

        # End edges
        builder.add_edge(Nodes.unknown["name"], END)
        builder.add_edge(Nodes.news_tools["name"], END)

        builder.set_entry_point(Nodes.router["name"])
        logger.info("Agent graph built successfully")
        return builder.compile()
