"""Screener node: market-wide stock screening via CodeAct pattern.

Mirrors the structure of PortfolioNode but operates on the broader market
(no user portfolio df).  The screener generates and executes Python code
that filters, scores, and ranks stocks based on a quantitative strategy.
"""

from typing import List

from langchain_core.messages import BaseMessage, HumanMessage, ToolMessage
from langchain_core.runnables import RunnableLambda
from langchain_core.tools import tool
from langgraph.runtime import get_runtime

from src.core.enums import LLMModel
from src.core.json_logging import logger_for
from src.core.llm import LLMFactory
from src.nodes.code_execution_tool import build_execute_code_tool
from src.nodes.screener_analysis_tool_node.screener_prompt import SCREENER_CODE_GENERATION_PROMPT
from src.nodes.screener_analysis_tool_node.screener_utils import (
    MIN_RANKED_STOCKS_TARGET,
    build_relaxation_user_message,
    build_screener_code_gen_invoke_args,
    build_screener_execution_env,
    parse_screened_count_from_tool_result,
)
from src.schemas.agent_state import AgentContext

logger = logger_for(__name__)


def _invoke_screener_llm(llm_with_tools, invoke_args: dict) -> BaseMessage:
    """Invoke SCREENER_CODE_GENERATION_PROMPT and return the LLM response."""
    prompt_value = SCREENER_CODE_GENERATION_PROMPT.invoke(invoke_args)
    llm_messages = prompt_value.to_messages()
    logger.debug(
        "Screener code generation LLM input (%d messages): %s",
        len(llm_messages),
        llm_messages,
    )
    return llm_with_tools.invoke(prompt_value)


class ScreenerNode:
    """Screener node: generates and executes market-wide stock screening code.

    Uses the same CodeAct pattern as PortfolioNode but:
    - No portfolio df (operates on a user-defined or strategy-derived stock universe)
    - Uses screener-appropriate yfinance functions + filter functions
    - Returns a shortlisted, scored, and ranked stock list
    - After a successful run with fewer than ``MIN_RANKED_STOCKS_TARGET`` names, may loop back
      with a human message so the model relaxes thresholds (up to ``max_relaxation_rounds``).
    """

    def __init__(
        self,
        llm_factory: LLMFactory,
        max_code_executions: int = 12,
        max_relaxation_rounds: int = 3,
    ):
        self._llm_factory = llm_factory
        self.max_code_executions = max_code_executions
        self.max_relaxation_rounds = max_relaxation_rounds

    def create_execute_code_tool(self):
        """Build the screener-scoped execute_python_code tool (no portfolio df)."""

        async def execution_env_factory():
            return build_screener_execution_env()

        return build_execute_code_tool(execution_env_factory)

    def create_worker_tool(self):
        """Build a self-contained screener LangChain tool for the orchestrator.

        Encapsulates the full pipeline: code generation → execution (with retry).
        The orchestrator calls this with a focused screening task string and receives
        the ranked/filtered stock list as a plain-text result.
        """
        execute_code_tool = self.create_execute_code_tool()
        node = self

        @tool
        async def screener_analysis_tool(task: str) -> str:
            """Screen the broader market for stocks matching specific criteria.

            Use for finding, filtering, and ranking stocks by fundamentals, valuation,
            growth trends, or any quantitative strategy.  Does NOT access the user's
            portfolio — call financial_analysis_tool for portfolio-related questions.

            Args:
                task: Screening strategy and criteria, e.g.
                      'Find Indian large-cap IT stocks with improving operating margins
                       over the last 3 quarters and PE < 30. Rank top 10 by margin trend.'
            """
            runtime = get_runtime(AgentContext)
            context = runtime.context
            screener_model = context.get("screener_model", LLMModel.GPT4p1)
            llm = node._llm_factory(screener_model)
            llm_with_tools = llm.bind_tools([execute_code_tool], tool_choice="required")

            invoke_args = build_screener_code_gen_invoke_args(
                messages=[],
                user_request=task,
            )
            ai_response = _invoke_screener_llm(llm_with_tools, invoke_args)
            messages_ctx: List[BaseMessage] = [ai_response]

            code_executions = 0
            relaxation_rounds = 0
            last_tool_result: str | None = None

            while getattr(ai_response, "tool_calls", None) and code_executions < node.max_code_executions:
                tool_call = ai_response.tool_calls[0]
                code = tool_call["args"].get("code", "")
                tool_call_id = tool_call.get("id", f"call_{code_executions}")

                tool_result: str = await execute_code_tool.ainvoke({"code": code})
                last_tool_result = tool_result
                code_executions += 1
                is_success = "STATUS: success" in tool_result

                if is_success:
                    screened = parse_screened_count_from_tool_result(tool_result)
                    need_relaxation = (
                        screened is not None
                        and screened < MIN_RANKED_STOCKS_TARGET
                        and relaxation_rounds < node.max_relaxation_rounds
                    )
                    if need_relaxation:
                        relaxation_rounds += 1
                        logger.info(
                            "screener_analysis_tool relaxing thresholds (round %s), META_SCREENED_COUNT=%s",
                            relaxation_rounds,
                            screened,
                        )
                        tool_msg = ToolMessage(content=tool_result, tool_call_id=tool_call_id)
                        relax_msg = HumanMessage(
                            content=build_relaxation_user_message(
                                screened=screened or 0,
                                relaxation_round=relaxation_rounds,
                            )
                        )
                        messages_ctx = messages_ctx + [tool_msg, relax_msg]
                        invoke_args = build_screener_code_gen_invoke_args(
                            messages=messages_ctx,
                            user_request=task,
                        )
                        ai_response = _invoke_screener_llm(llm_with_tools, invoke_args)
                        messages_ctx = messages_ctx + [ai_response]
                        continue

                    if (
                        screened is not None
                        and screened < MIN_RANKED_STOCKS_TARGET
                        and relaxation_rounds >= node.max_relaxation_rounds
                    ):
                        prefix = (
                            f"[Screener: fewer than {MIN_RANKED_STOCKS_TARGET} names after "
                            f"{node.max_relaxation_rounds} relaxation round(s); best-effort results below.]\n\n"
                        )
                        return prefix + tool_result

                    return tool_result

                # execution error — retry until max_code_executions (shared with relax loop budget)
                logger.info(
                    "screener_analysis_tool retrying after execution error (code execution %s)",
                    code_executions,
                )
                tool_msg = ToolMessage(content=tool_result, tool_call_id=tool_call_id)
                messages_ctx = messages_ctx + [tool_msg]
                invoke_args = build_screener_code_gen_invoke_args(
                    messages=messages_ctx,
                    user_request=task,
                )
                ai_response = _invoke_screener_llm(llm_with_tools, invoke_args)
                messages_ctx = messages_ctx + [ai_response]

            if last_tool_result is not None:
                return last_tool_result
            return "Screener analysis completed with no output."

        return screener_analysis_tool

    def get_runnable_sequence(self) -> RunnableLambda:
        """Return a runnable for direct graph wiring (unused in current hub-spoke design)."""

        async def screener_node_fn(state):
            return state

        return RunnableLambda(screener_node_fn)
