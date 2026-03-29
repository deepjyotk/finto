"""Orchestrator node — supervisor agent that collects context from worker tools."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, List

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnableLambda
from langgraph.runtime import get_runtime

from src.core.enums import LLMModel, Nodes
from src.core.json_logging import logger_for
from src.core.llm import LLMFactory
from src.schemas.agent_state import AgentContext, AgentState

if TYPE_CHECKING:
    from src.nodes.portfolio_worker_tool_node import PortfolioNode
    from src.nodes.web_search import WebSearchNode

logger = logger_for(__name__)


class OrchestratorNode:
    """Supervisor-style orchestrator that dispatches sub-tasks to worker tools.

    Instead of routing to a single downstream node the orchestrator can call
    ``portfolio_worker_tool`` and ``web_search_tool`` one or more times in
    sequence.  Each worker tool is self-contained (symbol extraction, code
    generation/execution, or web search + synthesis) and returns plain-text
    results.  The orchestrator accumulates those results, then hands off to
    ``final_response_generation_node`` once it has gathered all needed context.
    """

    _SUPERVISOR_PROMPT_TEMPLATE: Final[
        str
    ] = """
You are the finance assistant orchestrator. Your role is to intelligently \
collect context from specialised worker tools and prepare a comprehensive answer \
to the user's financial query.

Available tools
- portfolio_worker_tool  – Analyses the user's portfolio (holdings, P&L, \
returns, allocation, risk metrics, individual stock analysis).  Use for \
portfolio or stock/fund data questions.
- web_search_tool  – Searches the web for live financial news, market headlines, \
NSE/SEBI/BSE circulars, earnings announcements, macro/policy updates, and recent \
events.  Use whenever the user needs current information, breaking news, or \
time-sensitive market context.

Strategy
1. Read the user's query carefully and decide which tools to call.
2. Craft a focused, specific sub-task for each tool call — do NOT just forward \
the raw user query.
3. Recent news or events: whenever the user asks about recent news, current \
events, or what is happening in the markets, you are free to call \
web_search_tool with a focused query—you do not need to call \
portfolio_worker_tool first unless the question clearly depends on their \
holdings or positions.
4. For multi-part queries (e.g. "top 5 stocks and their news"):
   • Step A: call portfolio_worker_tool with task "Identify top 5 stocks by …"
   • Step B: once you have the stock names from Step A's result, call \
web_search_tool with task "Latest news for <stock1>, <stock2>, …"
5. Call only the tools that are necessary.
6. After all context is collected, stop calling tools — the final-response \
node will format the answer for the user.

Sub-task rules
- Make each sub-task specific and actionable.
- When calling web_search_tool after a portfolio call, embed the concrete \
stock/entity names from the portfolio result into the search task.
- Never repeat a tool call for information you already have.
"""

    def __init__(
        self,
        llm_factory: LLMFactory,
        portfolio_node: "PortfolioNode",
        web_search_node: "WebSearchNode",
    ):
        self._llm_factory = llm_factory
        # Build worker tools once; reused across every graph invocation
        self._portfolio_worker_tool = portfolio_node.create_worker_tool()
        self._web_search_tool = web_search_node.create_worker_tool()

    # ------------------------------------------------------------------
    # Prompt
    # ------------------------------------------------------------------

    def _supervisor_prompt_template(self) -> ChatPromptTemplate:
        return ChatPromptTemplate.from_messages(
            [
                ("system", self._SUPERVISOR_PROMPT_TEMPLATE),
                MessagesPlaceholder(variable_name="messages"),
            ]
        )

    # ------------------------------------------------------------------
    # Runnable
    # ------------------------------------------------------------------

    def get_runnable_sequence(self):
        prompt = self._supervisor_prompt_template()

        def orchestrator_node_fn(state: AgentState) -> AgentState:
            runtime = get_runtime(AgentContext)
            context = runtime.context

            user_id = context.get("user_id", "unknown")
            logger.info("Orchestrator node invoked for user_id=%s", user_id)

            orchestrator_model = context.get("orchestrator_model", LLMModel.GPT4oMini)
            llm = self._llm_factory(orchestrator_model)
            llm_with_tools = llm.bind_tools([self._portfolio_worker_tool, self._web_search_tool])

            messages = state.get("messages", [])

            # Repair orphan tool_calls so OpenAI accepts the request (see _ensure_tool_call_responses)
            # messages_for_llm = _ensure_tool_call_responses(list(messages))
            messages_for_llm = list(messages)

            # Persist the original human request for final_response_generation_node
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

            # When the LLM stops calling tools, collect all ToolMessage outputs
            # and store them as last_output for final_response_generation_node.
            if not getattr(ai_response, "tool_calls", None):
                tool_outputs = [
                    msg.content
                    for msg in messages + [ai_response]
                    if isinstance(msg, ToolMessage) and msg.content
                ]
                if tool_outputs:
                    new_state["last_output"] = "\n\n---\n\n".join(tool_outputs)
                elif ai_response.content:
                    # Fallback: use the orchestrator's own summary as the result
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

        # Find the most recent AIMessage
        last_ai_msg: AIMessage | None = None
        for msg in reversed(messages):
            if isinstance(msg, AIMessage):
                last_ai_msg = msg
                break

        if last_ai_msg and getattr(last_ai_msg, "tool_calls", None):
            tool_name = last_ai_msg.tool_calls[0].get("name", "")
            if tool_name == self._portfolio_worker_tool.name:
                logger.info(
                    "Orchestrator routing to portfolio_worker_tool_node for user_id=%s",
                    user_id,
                )
                return Nodes.portfolio_worker_tools.get("name")
            if tool_name == self._web_search_tool.name:
                logger.info(
                    "Orchestrator routing to web_search_tool_node for user_id=%s",
                    user_id,
                )
                return Nodes.web_search_worker_tools.get("name")

        logger.info("Orchestrator done — routing to final_response for user_id=%s", user_id)
        return Nodes.final_response.get("name")
