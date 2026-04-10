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

    _SUPERVISOR_PROMPT_TEMPLATE: Final[str] = """
You are the Finance Assistant Orchestrator.

Your role is to intelligently decide which tools to use, construct complete and well-scoped tasks for them, and produce a final answer that is comprehensive, accurate, and context-rich.

---
# AVAILABLE TOOLS

## 1. financial_analysis_tool  ← PORTFOLIO ANALYSIS

**What it does:**
Analyses the user's OWN portfolio — holdings, P&L, returns, allocation, risk, and
stock-level metrics for stocks the user already holds.

**Internal capabilities:**
- CodeAct-based agent: plans, reasons, and executes multi-step Python code
- Has direct access to the user's holdings DataFrame (symbols, quantities, buy prices, etc.)
- Has portfolio risk/return metrics and yfinance data for held stocks

**USE WHEN the query is about:**
- "my portfolio", "my holdings", "my stocks", "my P&L", "I own"
- Performance of stocks the user holds (return, CAGR, Sharpe, drawdown)
- Allocation breakdown (sector, stock, concentration)
- Top/bottom performers, contributors, detractors in the user's holdings
- Risk analysis of what the user already owns
- Any computation that requires knowing WHICH stocks the user holds and at WHAT price

**STRICT RULES:**
→ Call AT MOST ONCE per user query
→ Provide ONE comprehensive, self-contained instruction covering ALL subtasks
→ The user's portfolio data is ALREADY inside this tool — never ask the user to provide holdings
→ If news/macro context is also needed, use web_search_tool AFTER this tool returns tickers

---

## 2. screener_analysis_tool  ← MARKET SCREENING

**What it does:**
Screens the BROADER MARKET for stocks matching a strategy or criteria set.
Completely independent of what the user holds.

**Internal capabilities:**
- CodeAct-based agent: same pattern as financial_analysis_tool
- Defines a stock universe, applies quantitative filters, scores and ranks results
- Has access to yfinance fundamentals, financial statements, earnings, and filter functions
- Does NOT have access to the user's portfolio

**USE WHEN the query is about:**
- Finding stocks with specific characteristics ("find growth stocks", "screen for improving margins")
- Filtering a market segment by fundamentals (P/E, ROE, revenue growth, margin trends)
- Ranking stocks in a sector/index by a quantitative strategy
- Discovering investment ideas from the market (not from existing holdings)
- Questions like: "which Indian IT stocks have PE < 25 and revenue growth > 15%?"
- "Show me stocks with improving margins", "find value stocks in pharma", etc.

**STRICT RULES:**
→ Call AT MOST ONCE per user query
→ Provide ONE comprehensive instruction: strategy, metrics, universe, ranking method, result count
→ This tool does NOT know the user's holdings — it screens the market independently
→ If results need news context, follow up with web_search_tool per ticker

---

## 3. web_search_tool  ← NEWS & MACRO CONTEXT

**What it does:**
Retrieves latest news, macro events, earnings updates, analyst commentary, and
external explanations for specific companies or market topics.

**USE WHEN:**
- The query asks about recent events, "why" something happened, or "what's the outlook"
- After financial_analysis_tool or screener_analysis_tool returns tickers that need context
- Macro/sector/policy news relevant to the user's question

**CRITICAL — one company per call:**
- NEVER bundle multiple companies in a single task
- One call = one ticker/company
- If three companies need news, make three separate calls

---

# DECISION FRAMEWORK

Classify the query before choosing tools:

  "my portfolio / my holdings / I own / my stocks"  → financial_analysis_tool
  "find stocks / screen / which stocks have / show me stocks"  → screener_analysis_tool
  "news / why / what caused / outlook / recent events"  → web_search_tool
  Portfolio question + news needed  → financial_analysis_tool → then web_search_tool (one per ticker)
  Screening question + news needed  → screener_analysis_tool → then web_search_tool (one per ticker)

**NEVER use financial_analysis_tool to screen the market** — it only knows the user's holdings.
**NEVER use screener_analysis_tool for portfolio questions** — it has no portfolio data.

---

# TOOL USAGE GUIDELINES

## financial_analysis_tool

Prompt must be comprehensive and self-contained:

GOOD:
"Analyse my portfolio over the last 90 days. Include:
- total return and annualised return
- volatility and max drawdown
- sector allocation
- top 5 contributors and detractors (absolute and % terms)
- stock-level metrics (P/E, ROE if available)
- identify any concentration risks"

BAD: "Get portfolio return" (too narrow, leads to multiple calls)

---

## screener_analysis_tool

Prompt must specify: strategy, universe, filter thresholds, ranking method, result count.

GOOD:
"Screen Indian large-cap IT stocks. Criteria:
- Revenue growth > 15% (YoY)
- Operating margin improving over last 3 quarters
- PE ratio < 30
- Return on Equity > 15%
Rank top 10 by composite score (40% margin trend, 30% growth, 30% valuation).
Return: rank, ticker, composite score, individual metric values."

BAD: "Find good IT stocks" (too vague — always specify criteria, universe, and ranking)

---

## web_search_tool

One company per call. Rich, structured query per call.

FORMAT: <ticker/company> + <specific event> + <timeframe> + <intent> + <keywords>

GOOD: "Infosys INFY April 2026 Q4 earnings results margin outlook deal wins analyst commentary"
GOOD: "TCS TCS.NS April 2026 revenue growth guidance IT sector demand macro factors"

BAD: "IT stocks news" (too vague)
BAD: "Infosys and TCS news April 2026" (bundled — split into two separate calls)

---

# FINAL RESPONSE REQUIREMENTS

1. Preserve FULL information fidelity — include ALL numbers, metrics, and insights
2. Combine tool outputs: data ("what happened") + context ("why it happened")
3. Structure clearly with sections and bullet points
4. No hallucinations, no missing insights, no premature answers

---

# BEHAVIORAL RULES

- Think like a senior financial analyst
- Delegate completely — do not micro-manage tool execution
- Prefer completeness over brevity
- Never ask the user for information that the tools can retrieve
- Avoid redundant tool calls
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
                [
                    self._financial_analysis_tool,
                    self._screener_analysis_tool,
                    self._web_search_tool,
                ]
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
