"""Code generation node for portfolio analysis."""

import inspect
from datetime import datetime
from typing import Callable, List
from zoneinfo import ZoneInfo

from langchain_core.messages import AIMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnableLambda
from langchain_openai import ChatOpenAI
from langgraph.runtime import get_runtime

from src.core.enums import LLMModel, Nodes
from src.core.json_logging import logger_for
from src.core.schema import EquityHoldingSchema
from src.schemas.agent_state import AgentContext, AgentState
from src.tools.calculate_profit_tool import calculate_profit_or_loss
from src.tools.filters import growth_filter, value_filter
from src.tools.portfolio_risk import (
    download_prices,
    max_drawdown,
    max_drawdown_asset,
    portfolio_volatility,
)
from src.tools.yfinance_wrappers import (
    get_balance_sheet,
    get_capital_gains,
    get_cash_flow,
    get_dividends,
    get_earnings,
    get_earnings_estimate,
    get_earnings_history,
    get_eps_revisions,
    get_eps_trend,
    get_growth_estimates,
    get_income_statement,
    get_insider_purchases,
    get_insider_transactions,
    get_institutional_holders,
    get_last_close_price,
    get_major_holders,
    get_mutualfund_holders,
    get_revenue_estimate,
)

logger = logger_for(__name__)


def get_function_with_doc_string(fns: list[Callable]) -> str:
    chunks = []
    for fn in fns:
        sig = inspect.signature(fn)
        doc = (fn.__doc__ or "").strip().replace("\n", " ")
        chunks.append(f"def {fn.__name__}{sig}:\n" f'    """{doc}"""\n' f"    ...")
    return "\n\n".join(chunks)


# def get_error_handling_rules(handling_type: Literal["strict", "lenient"]) -> str:
#     strict_rules = """
# - If any calculation encounters missing, invalid, or inconsistent financial data, raise a clear Python exception and stop further processing.
# - This is financial data; enforce strict validation and consistency. Do not silently ignore errors or auto-correct values.
# """
#     lenient_rules = """
# - If any calculation encounters missing, invalid, or inconsistent financial data, still generate valid, runnable Python code.
# - Do not fail the whole script. Instead, log or print a clear warning message and skip only the problematic item, continuing with the rest.
# - Example: If a symbol is missing or not found, print `Warning: Symbol <X> not found` and exclude it from calculations, but continue processing remaining symbols.
# """
#     return strict_rules if handling_type == "strict" else lenient_rules


class CodeGenerationNode:
    """LLM code generation node similar to the reference agent_step."""

    _PROMPT_TEMPLATE = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """
# ROLE & GOAL
You are a Python and Pandas expert helping analyze a user's stock portfolio.
Your goal is to generate Python code that can be executed to answer the user's request.

# RUNTIME ENVIRONMENT
You are running inside a controlled Python execution environment where:
- df is a pandas DataFrame that already contains the user's portfolio data.
- pd is available as the pandas module.
- All helper functions listed below are already imported and available.
- The current IST(UTC+5:30) (Asia/Kolkata) date and time is {current_date_time}.
- The environment does NOT allow:
  - Reading files (no pd.read_excel, open, etc.)
  - Network calls (except through provided helper functions)
  - User input (no input()).


# MANDATORY CODE PRELUDE
Your output must begin with EXACTLY the following Python code:

import pandas as pd
import yfinance as yf

if not isinstance(df, pd.DataFrame):
    raise ValueError("df is not a DataFrame")

After these lines, continue writing Python code to solve the user request.
Do NOT repeat these imports or checks later in the code.

# INPUTS PROVIDED TO YOU

Portfolio DataFrame Schema:
{portfolio_df_schema}

Symbols Context:
{symbols_context}



# AVAILABLE PORTFOLIO ANALYSIS FUNCTIONS:

## Profit/Loss Calculation
{profit_calculation_function_with_doc_string}

## Risk Functions
{risk_functions_with_doc_string}

# AVAILABLE YFINANCE DATA FUNCTIONS:
The following functions are already implemented and imported in the runtime environment:

## Financial Statements:
{yf_financial_statement_function_with_doc_string}

## Price & Returns:
{yf_price_and_returns_function_with_doc_string}

## Earnings & Estimates:
{yf_earnings_and_estimates_function_with_doc_string}

## Ownership & Insider Activity:
{yf_ownership_and_insider_activity_function_with_doc_string}

# STOCK FILTERING FUNCTIONS:
{filter_functions_with_doc_string}

# STRICT RULES:
- Always respect all argument types and argument descriptions when calling any function.
- Prefer batch functions whenever working with multiple items.
- You may use pandas operations (groupby, agg, sort_values, filters, etc.), but ensure the code is correct for financial data. If you drop any row for a valid reason, you must print a warning with print(...). Never drop a row without a clearly justified reason.
- IMPORTANT: You are only allowed to call functions from 'AVAILABLE PORTFOLIO ANALYSIS FUNCTIONS' and 'AVAILABLE YFINANCE DATA FUNCTIONS'. No other functions may be called.
- Always use the DataFrame variable named df.
- Do NOT reload data from files.
- Do NOT use markdown, comments, or explanations.
- Do NOT define any new functions or classes in the generated code.
- Absolutely no `def`, `class`, or `function` declarations of any kind.
- Write a single, linear Python script that can be executed as-is in the current environment.
- Bases all calculations strictly on the user request and available data.
- If any symbol has missing values, print a clear warning listing them. Write the code such that execution never fails because of missing data — simply skip those entries and continue with the rest.


# CODING REQUIREMENTS
When generating Python code:
- Always begin with the required import + df-check block.
- Use pandas operations (groupby, agg, sort_values, filter, etc.).
- The code must be executable as-is.
- Always cast every numeric value to float before using it.
- Convert any numeric-like value (Decimal, int, etc.) to float before use, e.g.:
    value = float(value)
    df[col] = df[col].astype(float)

# OUTPUT FORMAT
Your output must:
- Contain ONLY executable Python code.
- Have no comments.
- Have no markdown.
- Have no explanations.
- Begin with the mandatory import + df-check block.
- Print the final result using print(...).
                """,
            ),
            MessagesPlaceholder(variable_name="messages"),
            ("user", "{user_request}"),
        ]
    )

    def __init__(self, llm_factory: Callable[[LLMModel], ChatOpenAI], max_attempts: int = 2):
        self._llm_factory = llm_factory
        self.max_attempts = max_attempts

    def _build_symbols_context(self, symbols: List[str]) -> str:
        if symbols:
            return f"Focus only on these symbols: {', '.join(symbols)}"
        return "Scope: Analyze the entire portfolio (no specific symbol filter)."

    def get_runnable_sequence(self) -> RunnableLambda:
        """Return runnable for generating Python code from the portfolio query."""

        def code_generation_node_fn(state: AgentState) -> AgentState:
            if state.get("done"):
                return state

            runtime = get_runtime(AgentContext)
            context = runtime.context
            portfolio_model = context.get("portfolio_model", LLMModel.GPT4p1)
            llm = self._llm_factory(portfolio_model)

            # Build function-docstring context
            risk_functions_with_doc_string: str = get_function_with_doc_string(
                [download_prices, portfolio_volatility, max_drawdown, max_drawdown_asset]
            )
            yf_financial_statement_function_with_doc_string: str = get_function_with_doc_string(
                [get_balance_sheet, get_income_statement, get_cash_flow]
            )
            yf_price_and_returns_function_with_doc_string: str = get_function_with_doc_string(
                [get_last_close_price, download_prices, get_dividends, get_capital_gains]
            )
            yf_earnings_and_estimates_function_with_doc_string: str = get_function_with_doc_string(
                [
                    get_earnings,
                    get_earnings_estimate,
                    get_revenue_estimate,
                    get_earnings_history,
                    get_eps_trend,
                    get_eps_revisions,
                    get_growth_estimates,
                ]
            )
            yf_ownership_and_insider_activity_function_with_doc_string: str = (
                get_function_with_doc_string(
                    [
                        get_major_holders,
                        get_institutional_holders,
                        get_mutualfund_holders,
                        get_insider_purchases,
                        get_insider_transactions,
                    ]
                )
            )
            profit_calculation_function_with_doc_string: str = get_function_with_doc_string(
                [calculate_profit_or_loss]
            )
            filter_functions_with_doc_string: str = get_function_with_doc_string(
                [growth_filter, value_filter]
            )

            user_request = state.get("user_request", "").strip()
            messages = state.get("messages", [])

            if not user_request:
                error_msg = "No user request available for portfolio analysis."
                ai_msg = AIMessage(content=error_msg, name="code_generation_error")
                return {
                    **state,
                    "messages": messages + [ai_msg],
                    "last_code": None,
                    "last_output": error_msg,
                    "last_code_success": False,
                    "done": True,
                    "final_answer": error_msg,
                }

            portfolio_df_schema: str = EquityHoldingSchema.get_holdings_schema()
            symbols_context = self._build_symbols_context(state.get("symbol_names", []))
            current_date_time_ist = datetime.now(ZoneInfo("Asia/Kolkata")).strftime(
                "%Y-%m-%d %H:%M:%S"
            )

            chain = self._PROMPT_TEMPLATE | llm
            ai_response = chain.invoke(
                {
                    "messages": messages,
                    "portfolio_df_schema": portfolio_df_schema,
                    "symbols_context": symbols_context,
                    "user_request": user_request,
                    "yf_financial_statement_function_with_doc_string": yf_financial_statement_function_with_doc_string,
                    "yf_price_and_returns_function_with_doc_string": yf_price_and_returns_function_with_doc_string,
                    "yf_earnings_and_estimates_function_with_doc_string": yf_earnings_and_estimates_function_with_doc_string,
                    "yf_ownership_and_insider_activity_function_with_doc_string": yf_ownership_and_insider_activity_function_with_doc_string,
                    "profit_calculation_function_with_doc_string": profit_calculation_function_with_doc_string,
                    "risk_functions_with_doc_string": risk_functions_with_doc_string,
                    "filter_functions_with_doc_string": filter_functions_with_doc_string,
                    "current_date_time": current_date_time_ist,
                }
            )

            generated_code = (
                ai_response.content if hasattr(ai_response, "content") else str(ai_response)
            )

            ai_msg = AIMessage(content=generated_code, name="portfolio_code_generation")

            return {
                **state,
                "messages": messages + [ai_msg],
                "last_code": generated_code,
            }

        return RunnableLambda(code_generation_node_fn)

    def code_generation_agent_decision(self, state: AgentState):
        """Decide whether to end or request another generation cycle."""
        if state.get("done"):
            return Nodes.final_response["name"]

        attempts = state.get("attempts", 0)
        last_output = state.get("last_output") or ""
        last_code_success = state.get("last_code_success", False)

        # If code executed successfully and produced output, move to final_response
        if last_code_success and last_output:
            state["done"] = True
            return Nodes.final_response["name"]

        # If we've exhausted attempts, end with an error message
        if attempts >= self.max_attempts:
            state["done"] = True
            state["final_answer"] = (
                f"Failed after {attempts} attempts.\n\nLast execution:\n{last_output}"
                if last_output
                else f"Failed after {attempts} attempts with no execution output."
            )
            return Nodes.final_response["name"]

        # Otherwise, request another code generation attempt
        state["done"] = False
        return Nodes.code_generation["name"]
