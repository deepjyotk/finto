"""Orchestrator node — supervisor agent that collects context from worker tools."""

from __future__ import annotations

from typing import TYPE_CHECKING

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda
from langgraph.runtime import get_runtime

from src.core.enums import LLMModel, Nodes
from src.core.json_logging import logger_for
from src.core.llm import LLMFactory
from src.nodes.orchestrator_node.orchestrator_prompt import supervisor_prompt_template
from src.schemas.agent_state import AgentContext, AgentState

if TYPE_CHECKING:
    from src.nodes.financial_analysis_tool_node import PortfolioNode
    from src.nodes.screener_analysis_tool_node import ScreenerNode
    from src.nodes.web_search import WebSearchNode

logger = logger_for(__name__)


class OrchestratorNode:
    """Supervisor-style orchestrator that dispatches sub-tasks to worker tools.

    The orchestrator can call ``financial_analysis_tool``, ``screener_analysis_tool``,
    and ``web_search_tool`` one or more times in sequence.  Each worker tool is
    self-contained and returns plain-text results.  The orchestrator accumulates
    those results, then hands off to ``final_response_generation_node``.

    Tool responsibilities (IMPORTANT — keep these distinct):
      financial_analysis_tool  → user's OWN portfolio: holdings, P&L, allocation, risk
      screener_analysis_tool   → MARKET screening: find/filter/rank stocks from the market
      web_search_tool          → news, macro context, "why" explanations (one company per call)
    """

    def __init__(
        self,
        llm_factory: LLMFactory,
        portfolio_node: "PortfolioNode",
        screener_node: "ScreenerNode",
        web_search_node: "WebSearchNode",
    ):
        self._llm_factory = llm_factory
        self._financial_analysis_tool = portfolio_node.create_worker_tool()
        self._screener_analysis_tool = screener_node.create_worker_tool()
        self._web_search_tool = web_search_node.create_worker_tool()

    # ------------------------------------------------------------------
    # Prompt
    # ------------------------------------------------------------------

    def _supervisor_prompt_messages(self) -> ChatPromptTemplate:
        return supervisor_prompt_template()

    # ------------------------------------------------------------------
    # Runnable
    # ------------------------------------------------------------------

    def get_runnable_sequence(self):
        prompt = self._supervisor_prompt_messages()

        def orchestrator_node_fn(state: AgentState) -> AgentState:
            runtime = get_runtime(AgentContext)
            context = runtime.context

            user_id = context.get("user_id", "unknown")
            logger.info("Orchestrator node invoked for user_id=%s", user_id)

            orchestrator_model = context.get("orchestrator_model", LLMModel.GPT4oMini)
            llm = self._llm_factory(orchestrator_model)
            llm_with_tools = llm.bind_tools(
                [
                    self._financial_analysis_tool,
                    self._screener_analysis_tool,
                    self._web_search_tool,
                ],
                parallel_tool_calls=False,
            )

            messages = state.get("messages", [])
            messages_for_llm = list(messages)

            user_request = state.get("user_request", "")
            if not user_request:
                for msg in reversed(messages):
                    if isinstance(msg, HumanMessage):
                        user_request = msg.content
                        break

            chain = prompt | llm_with_tools
            ai_response = chain.invoke({"messages": messages_for_llm})

            new_state: AgentState = {
                **state,
                "messages": messages + [ai_response],
                "user_request": user_request,
            }

            if not getattr(ai_response, "tool_calls", None):
                tool_outputs = [
                    msg.content
                    for msg in messages + [ai_response]
                    if isinstance(msg, ToolMessage) and msg.content
                ]
                if tool_outputs:
                    new_state["last_output"] = "\n\n---\n\n".join(tool_outputs)
                elif ai_response.content:
                    new_state["last_output"] = ai_response.content

            return new_state

        return RunnableLambda(orchestrator_node_fn)

    # ------------------------------------------------------------------
    # Conditional routing
    # ------------------------------------------------------------------

    def orchestrator_decision(self, state: AgentState) -> str:
        """Route to a worker ToolNode, final_response, or unknown based on last AI message."""
        runtime = get_runtime(AgentContext)
        user_id = runtime.context.get("user_id", "unknown")

        messages = state.get("messages", [])
        ai_message_count = sum(isinstance(m, AIMessage) for m in messages)

        if ai_message_count > Nodes.orchestrator.get("max_ai_messages_allowed"):
            logger.warning(
                "Orchestrator max iterations (%d) exceeded for user_id=%s",
                Nodes.orchestrator.get("max_ai_messages_allowed"),
                user_id,
            )
            return Nodes.unknown.get("name")

        last_ai_msg: AIMessage | None = None
        for msg in reversed(messages):
            if isinstance(msg, AIMessage):
                last_ai_msg = msg
                break

        if last_ai_msg and getattr(last_ai_msg, "tool_calls", None):
            tool_name = last_ai_msg.tool_calls[0].get("name", "")
            if tool_name == self._financial_analysis_tool.name:
                logger.info(
                    "Orchestrator routing to financial_analysis_tool_node for user_id=%s",
                    user_id,
                )
                return Nodes.financial_analysis_worker_tools.get("name")
            if tool_name == self._screener_analysis_tool.name:
                logger.info(
                    "Orchestrator routing to screener_analysis_tool_node for user_id=%s",
                    user_id,
                )
                return Nodes.screener_analysis_worker_tools.get("name")
            if tool_name == self._web_search_tool.name:
                logger.info(
                    "Orchestrator routing to web_search_tool_node for user_id=%s",
                    user_id,
                )
                return Nodes.web_search_worker_tools.get("name")

        logger.info("Orchestrator done — routing to final_response for user_id=%s", user_id)
        return Nodes.final_response.get("name")
