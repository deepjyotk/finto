"""Portfolio node: symbol extraction + code generation and execution."""

from typing import Any, Dict, List

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langchain_core.runnables import RunnableLambda
from langchain_core.tools import tool
from langgraph.runtime import get_runtime

from src.core.enums import LLMModel, Nodes
from src.core.json_logging import logger_for
from src.core.llm import LLMFactory
from src.nodes.code_execution_tool import build_execute_code_tool
from src.nodes.financial_analysis_tool_node.financial_analysis_prompt import (
    CODE_GENERATION_PROMPT,
    SYMBOL_CLASSIFIER_PROMPT_GRAPH,
    SYMBOL_EXTRACTION_PROMPT,
)
from src.nodes.financial_analysis_tool_node.financial_analysis_utils import (
    QueryTypeResult,
    SymbolExtractionResult,
    build_code_gen_invoke_args,
    build_execution_env,
    build_partial_price_retry_user_message,
    build_portfolio_scope_message,
    company_info_from_pinecone_matches,
    resolve_company_info_for_symbols,
    parse_portfolio_price_meta_from_tool_output,
)
from src.schemas.agent_state import AgentContext, AgentState
from src.services.holdings import HoldingsService
from src.tools.get_symbol_name import get_equity_id_for_symbol

logger = logger_for(__name__)


def _tool_call_args(tool_call: Any) -> dict:
    if isinstance(tool_call, dict):
        args = tool_call.get("args") or tool_call.get("arguments") or {}
    else:
        args = getattr(tool_call, "args", None) or getattr(tool_call, "arguments", None) or {}
    return args if isinstance(args, dict) else {}


def _code_gen_retry_messages(
    scope_msg: BaseMessage,
    *,
    failure_outputs: List[str] | None = None,
    extra_human: HumanMessage | None = None,
) -> List[BaseMessage]:
    """Build code-gen history for retries without OpenAI tool-call transcripts.

    ``CODE_GENERATION_PROMPT`` always appends a fresh HumanMessage(user_request)
    after ``messages``. Re-sending assistant(tool_calls)+ToolMessage through that
    template is fragile (id mismatches / unpaired tool_calls → OpenAI 400).
    Instead, fold prior execution output into HumanMessage feedback.
    """
    msgs: List[BaseMessage] = [scope_msg]
    for i, output in enumerate(failure_outputs or [], start=1):
        msgs.append(
            HumanMessage(
                content=(
                    f"Previous code execution attempt {i} failed. "
                    "Generate corrected Python code that fixes the error.\n\n"
                    f"Execution output:\n{output}"
                )
            )
        )
    if extra_human is not None:
        msgs.append(extra_human)
    return msgs


def _invoke_code_generation_llm(llm_with_tools, invoke_args: dict) -> BaseMessage:
    """Format ``CODE_GENERATION_PROMPT``, log the exact chat messages, then call the model.

    Invokes with the concrete message list (not the PromptValue) so ToolMessage /
    AIMessage tool_calls are not lost during binding.
    """
    prompt_value = CODE_GENERATION_PROMPT.invoke(invoke_args)
    llm_messages = prompt_value.to_messages()
    logger.debug(
        "Code generation LLM input (%d messages): %s",
        len(llm_messages),
        llm_messages,
    )
    return llm_with_tools.invoke(llm_messages)


class PortfolioNode:
    """Portfolio node: extracts symbols, generates Python code, and executes it."""

    def __init__(
        self,
        llm_factory: LLMFactory,
        holding_service: HoldingsService,
        max_attempts: int = 4,
    ):
        """Initialize PortfolioNode with LLM factory, holdings service, and retry config."""
        self._llm_factory = llm_factory
        self._holding_service = holding_service
        self.max_attempts = max_attempts

    @staticmethod
    def _latest_user_message_content(messages: List[BaseMessage]) -> str:
        """Find the most recent human message content."""
        for message in reversed(messages):
            if isinstance(message, HumanMessage):
                return message.content
        return ""

    def create_execute_code_tool(self):
        """Build the execution-env factory and return the generic execute_python_code tool.

        PortfolioNode is responsible for knowing *what* goes into the env (portfolio
        DataFrame, yfinance helpers, metrics functions, etc.).
        code_execution_tool.py is responsible for knowing *how* to run code in that env.
        """

        async def execution_env_factory() -> Dict[str, object]:
            runtime = get_runtime(AgentContext)
            context = runtime.context
            user_id = context.get("user_id")
            broker_id = context.get("broker_id")
            env = build_execution_env()
            env["df"] = await self._holding_service.get_portfolio_df(user_id, broker_id)
            return env

        return build_execute_code_tool(execution_env_factory)

    def create_worker_tool(self):
        """Build a self-contained portfolio-analysis LangChain tool for the orchestrator.

        Encapsulates the full pipeline: symbol extraction → code generation → code
        execution (with retry).  The orchestrator calls this tool with a focused
        sub-task string and receives the raw execution output as a string.
        """
        execute_code_tool = self.create_execute_code_tool()

        node = self

        @tool
        async def financial_analysis_tool(task: str) -> str:
            """Analyse the user's portfolio: holdings, P&L, returns, allocation, risk,
            or any stock/fund query.  Use for personal portfolio questions and stock
            analysis.

            Args:
                task: Focused analysis task, e.g. 'Get top 5 holdings by current value'
                      or 'Calculate annualised returns for RELIANCE and TCS'.
            """
            runtime = get_runtime(AgentContext)
            context = runtime.context
            portfolio_model = context.get("portfolio_model", LLMModel.GPT4p1)
            llm = node._llm_factory(portfolio_model)
            llm_with_tools = llm.bind_tools([execute_code_tool], tool_choice="required")

            scope_msg, extracted_symbols, pinecone_company_info = build_portfolio_scope_message(
                task, llm
            )
            company_info = await resolve_company_info_for_symbols(
                extracted_symbols, pinecone_company_info
            )

            invoke_args = build_code_gen_invoke_args(
                messages=[scope_msg],
                user_request=task,
                symbol_names=extracted_symbols,
                company_info=company_info,
            )
            ai_response = _invoke_code_generation_llm(llm_with_tools, invoke_args)

            attempts = 0
            partial_price_retries = 0
            failure_outputs: List[str] = []

            while getattr(ai_response, "tool_calls", None) and attempts < node.max_attempts:
                tool_calls = list(ai_response.tool_calls or [])
                # Prefer the first execute_python_code call; ignore extras.
                primary = tool_calls[0]
                code = _tool_call_args(primary).get("code", "")
                if not isinstance(code, str):
                    code = str(code or "")

                tool_result: str = await execute_code_tool.ainvoke({"code": code})
                attempts += 1
                is_success = "STATUS: success" in tool_result

                if is_success:
                    price_meta = parse_portfolio_price_meta_from_tool_output(tool_result)
                    failed_n = price_meta.get("failed")
                    if partial_price_retries < 1 and failed_n is not None and failed_n > 0:
                        partial_price_retries += 1
                        logger.info(
                            "financial_analysis_tool retrying after partial price fetch "
                            "(META_PRICE_FETCH_FAILED=%s)",
                            failed_n,
                        )
                        relax_msg = HumanMessage(
                            content=build_partial_price_retry_user_message(price_meta, task)
                        )
                        # Do NOT replay assistant(tool_calls)+ToolMessage into the prompt —
                        # that path caused OpenAI 400 unpaired tool_call_id errors.
                        retry_msgs = _code_gen_retry_messages(
                            scope_msg,
                            failure_outputs=failure_outputs,
                            extra_human=relax_msg,
                        )
                        invoke_args = build_code_gen_invoke_args(
                            messages=retry_msgs,
                            user_request=task,
                            symbol_names=extracted_symbols,
                            company_info=company_info,
                        )
                        ai_response = _invoke_code_generation_llm(llm_with_tools, invoke_args)
                        continue

                    return tool_result

                failure_outputs.append(tool_result)

                if attempts >= node.max_attempts:
                    return tool_result

                logger.info(
                    "financial_analysis_tool retrying code generation (attempt %d)",
                    attempts + 1,
                )
                retry_msgs = _code_gen_retry_messages(
                    scope_msg, failure_outputs=failure_outputs
                )
                invoke_args = build_code_gen_invoke_args(
                    messages=retry_msgs,
                    user_request=task,
                    symbol_names=extracted_symbols,
                    company_info=company_info,
                )
                ai_response = _invoke_code_generation_llm(llm_with_tools, invoke_args)

            return "Portfolio analysis completed with no output."

        return financial_analysis_tool

    def get_runnable_sequence(self) -> RunnableLambda:
        """Return the combined runnable for symbol extraction and code generation/execution."""

        async def portfolio_node_fn(state: AgentState) -> AgentState:
            if state.get("done"):
                return state

            messages = state.get("messages", [])
            user_request = state.get("user_request") or self._latest_user_message_content(messages)
            user_request = (user_request or "").strip()

            runtime = get_runtime(AgentContext)
            context = runtime.context
            portfolio_model = context.get("portfolio_model", LLMModel.GPT4p1)
            llm = self._llm_factory(portfolio_model)

            execute_code_tool = self.create_execute_code_tool()
            llm_with_tools = llm.bind_tools([execute_code_tool], tool_choice="required")

            last_message = messages[-1] if messages else None
            if isinstance(last_message, ToolMessage):
                tool_output = getattr(last_message, "content", str(last_message))
                is_success = "STATUS: success" in tool_output
                attempts = state.get("attempts", 0) + 1

                if is_success or attempts >= self.max_attempts:
                    status_note = (
                        "successfully" if is_success else f"after {attempts} attempt(s) with errors"
                    )
                    done_msg = AIMessage(
                        content=f"Code execution complete ({status_note}).",
                        name="portfolio_code_done",
                    )
                    return {
                        **state,
                        "messages": messages + [done_msg],
                        "last_output": tool_output,
                        "last_code_success": is_success,
                        "attempts": attempts,
                    }

                logger.info("Retrying code generation (attempt %d)", attempts + 1)
                # Strip prior assistant(tool_calls) transcripts — only pass symbol
                # context + failure feedback so OpenAI never sees unpaired tool_calls.
                symbol_msgs = [
                    m
                    for m in messages
                    if isinstance(m, AIMessage)
                    and getattr(m, "name", None) == "portfolio_symbol_extractor"
                    and not getattr(m, "tool_calls", None)
                ]
                scope_msg = symbol_msgs[-1] if symbol_msgs else AIMessage(
                    content="Continue portfolio analysis.",
                    name="portfolio_symbol_extractor",
                )
                retry_msgs = _code_gen_retry_messages(
                    scope_msg, failure_outputs=[str(tool_output)]
                )
                invoke_args = build_code_gen_invoke_args(
                    messages=retry_msgs,
                    user_request=user_request,
                    symbol_names=state.get("symbol_names", []),
                    company_info=state.get("symbol_company_info", []),
                )
                ai_response = _invoke_code_generation_llm(llm_with_tools, invoke_args)
                return {
                    **state,
                    "messages": messages + [ai_response],
                    "attempts": attempts,
                    "last_code_success": False,
                }

            if not user_request:
                error_msg = "No user request available for portfolio analysis."
                ai_msg = AIMessage(content=error_msg, name="code_execution_error")
                return {
                    **state,
                    "messages": messages + [ai_msg],
                    "last_code": None,
                    "last_output": error_msg,
                    "last_code_success": False,
                    "done": True,
                    "final_rendered_ui_answer": error_msg,
                }

            extracted_symbols: List[str] = []
            classifier_chain = SYMBOL_CLASSIFIER_PROMPT_GRAPH | llm.with_structured_output(
                QueryTypeResult
            )
            try:
                query_type = classifier_chain.invoke({"user_query": user_request})
            except Exception as exc:
                logger.error("Query type classification failed: %s", exc, exc_info=True)
                query_type = None

            if query_type and query_type.query_type == "specific_stocks_scope":
                symbol_chain = SYMBOL_EXTRACTION_PROMPT | llm.with_structured_output(
                    SymbolExtractionResult
                )
                result = symbol_chain.invoke({"user_query": user_request})
                matches = [
                    r for r in get_equity_id_for_symbol(result.symbol_names) if r.get("symbol")
                ]
                extracted_symbols = [r["symbol"] for r in matches]
                pinecone_company_info = company_info_from_pinecone_matches(matches)
                logger.info("Extracted symbols: %s", extracted_symbols)
                summary = (
                    f"Identified symbols: {', '.join(extracted_symbols)}"
                    if extracted_symbols
                    else "No valid symbols detected in the user request."
                )
            else:
                summary = "User is asking about the entire portfolio"
                pinecone_company_info = []

            symbol_message = AIMessage(content=summary, name="portfolio_symbol_extractor")
            company_info = await resolve_company_info_for_symbols(
                extracted_symbols, pinecone_company_info
            )

            invoke_args = build_code_gen_invoke_args(
                messages=messages + [symbol_message],
                user_request=user_request,
                symbol_names=extracted_symbols,
                company_info=company_info,
            )
            ai_response = _invoke_code_generation_llm(llm_with_tools, invoke_args)

            return {
                **state,
                "messages": messages + [symbol_message, ai_response],
                "symbol_names": extracted_symbols,
                "symbol_company_info": company_info,
                "attempts": 0,
            }

        return RunnableLambda(portfolio_node_fn)

    def portfolio_agent_decision(self, state: AgentState) -> str:
        """Route to code_execution_node if the last message has tool calls, else to final_response."""
        messages = state.get("messages", [])
        if messages:
            last = messages[-1]
            if isinstance(last, AIMessage) and getattr(last, "tool_calls", None):
                return Nodes.code_execution["name"]
        return Nodes.final_response["name"]
