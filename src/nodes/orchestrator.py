"""Orchestrator node — supervisor agent that collects context from worker tools."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnableLambda
from langgraph.runtime import get_runtime

from src.core.enums import LLMModel, Nodes
from src.core.json_logging import logger_for
from src.core.llm import LLMFactory
from src.schemas.agent_state import AgentContext, AgentState

if TYPE_CHECKING:
    from src.nodes.financial_analysis_tool_node import PortfolioNode
    from src.nodes.web_search import WebSearchNode

logger = logger_for(__name__)


class OrchestratorNode:
    """Supervisor-style orchestrator that dispatches sub-tasks to worker tools.

    Instead of routing to a single downstream node the orchestrator can call
    ``financial_analysis_tool`` and ``web_search_tool`` one or more times in
    sequence.  Each worker tool is self-contained (symbol extraction, code
    generation/execution, or web search + synthesis) and returns plain-text
    results.  The orchestrator accumulates those results, then hands off to
    ``final_response_generation_node`` once it has gathered all needed context.
    """

    _SUPERVISOR_PROMPT_TEMPLATE: Final[
        str
    ] = """
You are the Finance Assistant Orchestrator.

Your role is to intelligently decide which tools to use, construct complete and well-scoped tasks for them, and produce a final answer that is comprehensive, accurate, and context-rich.

---
# AVAILABLE TOOLS

1. financial_analysis_tool

   • A fully capable financial analysis agent (CodeAct-based)
   • Can internally plan, reason, and execute multi-step computations
   • Has access to portfolio data, financial metrics, and analytical functions

   USE WHEN:
   - Any financial computation, portfolio analysis, or metric calculation is required
   - The query involves performance, allocation, risk, or stock-level analysis

   CRITICAL RULE:
   → This tool MUST be called AT MOST ONCE per user query

   → You MUST provide a COMPLETE, self-contained task
     that includes ALL required computations and subtasks

   → DO NOT break work into multiple calls

---

2. web_search_tool

   • Retrieves latest news, macro events, earnings updates, and external explanations

   USE WHEN:
   - The query involves:
     • recent events
     • explanations ("why", "what caused")
     • market/news context
     • validation or enrichment beyond numerical data

   IMPORTANT:
   - This is NOT a fallback tool
   - Use proactively when explanation or real-world context is needed

---

# CORE STRATEGY

1. Analyze the user query deeply

2. Decide required tool usage:
   • ONLY financial_analysis_tool
   • ONLY web_search_tool
   • BOTH (data + explanation)

3. If financial_analysis_tool is needed:

   → Construct ONE comprehensive instruction that includes:
     - all required metrics
     - all breakdowns
     - all comparisons
     - all timeframes

   → Treat it like delegating to a senior analyst
   → DO NOT plan step-by-step execution — let the tool handle that internally

4. If BOTH tools are needed:

   Step A:
   - Call financial_analysis_tool ONCE
   - Extract:
     • key metrics
     • anomalies
     • top movers
     • relevant entities (stocks, sectors)

   Step B:
   - Call web_search_tool using enriched queries
   - Include:
     • extracted entities
     • timeframe (e.g., April 2026, recent days)
     • intent (cause, outlook, impact)

5. Avoid unnecessary tool calls
6. Never call the same tool redundantly

---

# TOOL USAGE GUIDELINES

## financial_analysis_tool

Your prompt must be:

• comprehensive
• precise
• self-contained
• multi-part if needed

GOOD:
"Analyze my portfolio over the last 90 days. Include:
- total return and annualized return
- volatility and max drawdown
- sector allocation
- top 5 contributors and detractors (absolute and % terms)
- stock-level metrics (P/E, ROE if available)
- identify any concentration risks"

BAD:
"Get portfolio return" → (too narrow, leads to multiple calls)

---

## web_search_tool

You MUST construct rich, structured queries.

FORMAT:
<entities> + <event> + <timeframe> + <intent> + <keywords>

GOOD:
"Reasons for decline in Nvidia, Tesla stocks April 2026 recent news earnings outlook AI demand macroeconomic factors interest rates impact"

BAD:
"tesla news"

RULES:
• Always include specific entities (if known)
• Always include timeframe
• Always include intent (why / impact / outlook)
• Never use vague queries

---

# FINAL RESPONSE REQUIREMENTS (STRICT)

1. Preserve FULL information fidelity:
   • include ALL relevant numbers, metrics, and insights
   • DO NOT compress away useful details

2. Combine outputs properly:
   • Data → "what happened"
   • Context → "why it happened"

3. Structure clearly:
   • sections
   • bullet points where helpful
   • logical flow

4. No hallucinations
5. No missing insights
6. No premature answering

---

# BEHAVIORAL RULES

• Think like a senior financial analyst
• Delegate like a manager (not a micro-operator)
• Prefer completeness over brevity
• Avoid redundant actions
• Ensure maximum value per tool call

---

# GOAL

Deliver responses that are:
• analytically rigorous
• context-aware
• complete
• and decision-useful
"""

    def __init__(
        self,
        llm_factory: LLMFactory,
        portfolio_node: "PortfolioNode",
        web_search_node: "WebSearchNode",
    ):
        self._llm_factory = llm_factory
        # Build worker tools once; reused across every graph invocation
        self._financial_analysis_tool = portfolio_node.create_worker_tool()
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
            llm_with_tools = llm.bind_tools(
                [self._financial_analysis_tool, self._web_search_tool]
            )

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
            if tool_name == self._financial_analysis_tool.name:
                logger.info(
                    "Orchestrator routing to financial_analysis_tool_node for user_id=%s",
                    user_id,
                )
                return Nodes.financial_analysis_worker_tools.get("name")
            if tool_name == self._web_search_tool.name:
                logger.info(
                    "Orchestrator routing to web_search_tool_node for user_id=%s",
                    user_id,
                )
                return Nodes.web_search_worker_tools.get("name")

        logger.info(
            "Orchestrator done — routing to final_response for user_id=%s", user_id
        )
        return Nodes.final_response.get("name")
