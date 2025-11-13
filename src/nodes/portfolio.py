"""Portfolio agent node for financial computations."""

from datetime import datetime, timedelta, timezone
from typing import Final, List

from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnableLambda
from langchain_openai import ChatOpenAI
from langgraph.graph import END

from src.core.enums import LLMModel, Nodes
from src.core.json_logging import logger_for
from src.tools.calculate_profit_tool import calculate_profit
from src.tools.get_ticker_price import get_ticker_price
from src.tools.yf_tools import (
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
    get_major_holders,
    get_mutualfund_holders,
    get_revenue_estimate,
)

logger = logger_for(__name__)


class PortfolioNode:
    """Portfolio agent node for financial computations."""

    _SYSTEM_PROMPT: Final[
        str
    ] = """
You are PortfolioAgent — a precise financial assistant focused on Indian equities (NSE/BSE) and the user's portfolio.

Now (UTC): {today_utc_iso}
Now (IST, UTC+5:30): {today_ist_iso}

CAPABILITIES & TOOLS
- Portfolio tools: get_holding_by_symbol, calculate_profit
- Price data: get_ticker_price
- Fundamental data: get_balance_sheet, get_cash_flow, get_income_statement
- Earnings & estimates: get_earnings, get_earnings_estimate, get_earnings_history, get_revenue_estimate, get_eps_trend, get_eps_revisions, get_growth_estimates
- Ownership & insider: get_major_holders, get_institutional_holders, get_mutualfund_holders, get_insider_purchases, get_insider_transactions
- Returns: get_dividends, get_capital_gains

POLICY
1) Tool order:
   a) ALWAYS call get_symbol_name(user_query) FIRST to extract the stock symbol.
   b) Smartly select additional tools based on the query (fundamentals, ownership, earnings, etc.).

2) Data integrity:
   - Prefer NSE if exchange unspecified for dual-listed companies; state this assumption.
   - Never fabricate data. If a tool fails or lacks data, say so and suggest alternatives.

3) Time & formatting:
   - Interpret relative dates (today/yesterday) in IST (fallback: UTC).
   - Prices: 2 decimals; percentages: 1 decimal; use ₹ for INR; include timestamps.

4) Output style (succinct, factual, actionable; no investment advice):
   - Direct answer in 1–2 sentences.
   - Compact breakdown (bullets/table): key metrics, calculations.
   - End with "Notes" (assumptions, tools used, data freshness).

WORKFLOW
Step 1: get_symbol_name(user_query).  
Step 2: Intelligently call relevant tools (fundamentals, ownership, earnings, portfolio, etc.).  
Step 3: Synthesize and present per "Output style".

    """

    def __init__(self):
        """
        Initialize the PortfolioNode.
        """

    def _agent_prompt_template(self) -> ChatPromptTemplate:
        now_utc = datetime.now(timezone.utc).isoformat()
        now_ist = datetime.now(timezone(timedelta(hours=5, minutes=30))).isoformat()
        chat_template = ChatPromptTemplate.from_messages(
            [
                ("system", self._SYSTEM_PROMPT),
                MessagesPlaceholder(variable_name="messages"),
            ]
        )
        complete_template = chat_template.partial(today_utc_iso=now_utc, today_ist_iso=now_ist)
        return complete_template

    def get_runnable_sequence(self, model: LLMModel):
        """
        Get the runnable sequence instance.

        Args:
            model: The model to use for the agent

        Returns:
            The initialized agent
        """
        # ------------------ UPDATED CHAIN ------------------
        # Stage 1: Generate Python code to extract relevant portfolio data (pattern borrowed from code_generatio_testing.py)
        # Stage 2: Use extracted data + original messages with the financial tools to answer the user query.

        import pandas as pd
        from langchain_core.prompts import ChatPromptTemplate
        from langchain_core.runnables import RunnableMap
        from langchain_experimental.tools import PythonREPLTool  # lightweight runtime tool

        llm = ChatOpenAI(model=model.value, temperature=0)
        code_llm = llm  # reuse same model for code-gen for now

        extraction_prompt = ChatPromptTemplate.from_template(
            """
        You are a **Python and Pandas expert** helping analyze a user's stock portfolio stored in an Excel file.

        Your task is to write **only valid Python code** tailored to the user's latest question about their portfolio.

        **Portfolio Excel file path:** {excel_path}

        **Preview of first rows:**
        {excel_preview}

        **User request:**
        {user_request}

        ### Requirements
        - Use pandas for all data manipulation: `import pandas as pd`.
        - Read the Excel file from the provided path.
        - Base the analysis strictly on the "User request". Do NOT default to computing sector summaries unless explicitly asked.
        - Choose appropriate operations (groupby/agg/sort/value_counts/percentages) depending on the request.
        - Print the final result with `print(...)` so downstream components can capture it.
        - Output must be only executable Python code (no comments, no explanations, no markdown).
        """
        )

        def _prepare(inputs):
            """Extract the latest human/user message content robustly and preview the portfolio file."""

            def _get_text(content):
                if isinstance(content, str):
                    return content
                # LangChain content can be a list of blocks with {"type": "text", "text": "..."}
                try:
                    if isinstance(content, list):
                        parts = []
                        for block in content:
                            if isinstance(block, dict) and "text" in block:
                                parts.append(str(block["text"]))
                        if parts:
                            return "\n".join(parts)
                except Exception:
                    pass
                return str(content) if content is not None else ""

            if isinstance(inputs, list):
                messages = inputs
            else:
                messages = inputs.get("messages", [])

            # Find the most recent human/user message
            user_request = ""
            for msg in reversed(messages or []):
                try:
                    role = getattr(msg, "type", None) or getattr(msg, "role", None)
                    cls = msg.__class__.__name__ if msg is not None else ""
                    if role in ("human", "user") or cls in ("HumanMessage", "Human"):
                        content = getattr(msg, "content", None)
                        user_request = _get_text(content).strip()
                        if user_request:
                            break
                    # dict-style message
                    if isinstance(msg, dict):
                        role = msg.get("role") or msg.get("type")
                        if role in ("user", "human"):
                            content = msg.get("content") or msg.get("text") or msg.get("message")
                            user_request = _get_text(content).strip()
                            if user_request:
                                break
                except Exception:
                    continue

            # Fallback to last message content if no human/user message found
            if not user_request and messages:
                last = messages[-1]
                content = getattr(last, "content", None)
                user_request = _get_text(content).strip() if content is not None else ""
            # Attempt to read portfolio.xlsx
            excel_path = "portfolio.xlsx"
            try:
                df = pd.read_excel(excel_path)
                excel_preview = df.head().to_string()
            except Exception as e:
                excel_preview = f"ERROR reading {excel_path}: {e}"
            return {
                "excel_path": excel_path,
                "excel_preview": excel_preview,
                "user_request": user_request,
                "messages": messages,
            }

        prep = RunnableLambda(_prepare)

        # Branch to produce extracted data (code generation + execution)
        generate_code_chain = extraction_prompt | code_llm | (lambda msg: msg.content)
        python_tool = PythonREPLTool()
        # Branches for generated code (string) and executed result
        generated_code_branch = prep | generate_code_chain
        extracted_branch = prep | generate_code_chain | python_tool

        # Branch to pass through original messages for final answering
        messages_branch = prep | RunnableLambda(
            lambda d: d["messages"]
        )  # keep original conversation

        # Final prompt combines system template + extracted output + user messages
        # Ensure time variables required by SYSTEM_PROMPT are provided
        now_utc = datetime.now(timezone.utc).isoformat()
        now_ist = datetime.now(timezone(timedelta(hours=5, minutes=30))).isoformat()
        final_prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    self._SYSTEM_PROMPT
                    + "\nExtracted portfolio context (raw output from code execution):\n{extracted_output}\nUse this factual extracted data when answering. If it contains an error message, state that extraction failed and proceed with available tools cautiously.",
                ),
                MessagesPlaceholder("messages"),
            ]
        ).partial(today_utc_iso=now_utc, today_ist_iso=now_ist)

        # Build mapping and log generated code + extracted data
        def _log_generated_and_extracted(data):
            try:
                gen = data.get("generated_code") if isinstance(data, dict) else None
                ext = data.get("extracted_output") if isinstance(data, dict) else None
                print("Generated Python code to extract data:\n", gen or "")
                print("Extracted data from Excel:\n", ext or "")
            except Exception as e:
                logger.warning("Failed to print generated code/extracted data: %s", e)
            return data

        mapped_with_logging = RunnableMap(
            {
                "messages": messages_branch,
                "extracted_output": extracted_branch,
                "generated_code": generated_code_branch,
            }
        ) | RunnableLambda(_log_generated_and_extracted)
        # Keep only variables required by the final prompt
        mapped_inputs = mapped_with_logging | RunnableMap(
            {
                "messages": RunnableLambda(lambda d: d["messages"]),
                "extracted_output": RunnableLambda(lambda d: d["extracted_output"]),
            }
        )

        # Tool-enabled answer stage
        answer_chain = final_prompt | llm.bind_tools(
            [
                get_ticker_price,
                calculate_profit,
                get_major_holders,
                get_institutional_holders,
                get_mutualfund_holders,
                get_insider_purchases,
                get_insider_transactions,
                get_dividends,
                get_capital_gains,
                get_balance_sheet,
                get_cash_flow,
                get_income_statement,
                get_earnings_estimate,
                get_revenue_estimate,
                get_earnings_history,
                get_eps_trend,
                get_eps_revisions,
                get_growth_estimates,
                get_earnings,
            ]
        )

        # Complete chain: mapping -> answer
        chain = mapped_inputs | answer_chain
        return chain
        # self.agent = create_agent(
        #     model=model.value,
        #     tools=[get_ticker_price, get_symbol_name, calculate_profit, get_holding_by_ticker],
        #     response_format=ToolStrategy(PortfolioQuery),
        #     system_prompt=prompt,
        # )
        # return self.agent

    def portfolio_agent_decision(self, state: List[BaseMessage]) -> str:
        """
        Return either the portfolio tools node name (to execute tools next)
        or the string "END" (to terminate the run).

        Logic: look for the last AIMessage; if it requested any tool calls,
        route to the tools node; otherwise END.
        """
        # count AI messages and check if has crossed the limit
        ai_message_count = sum(isinstance(item, AIMessage) for item in state)
        max_allowed = Nodes.portfolio["max_ai_messages_allowed"]
        if ai_message_count > max_allowed:
            logger.warning(
                "Portfolio agent max iterations (%d) exceeded, routing to unknown_node",
                max_allowed,
            )
            return END
        if not state:
            return END

        # Find the most recent AI turn (ignore trailing ToolMessage(s))
        last_ai = next((m for m in reversed(state) if isinstance(m, AIMessage)), None)
        if not last_ai:
            return END

        # Support both standard .tool_calls and legacy additional_kwargs
        tool_calls = (
            getattr(last_ai, "tool_calls", None)
            or last_ai.additional_kwargs.get("tool_calls")
            or last_ai.additional_kwargs.get("function_call")  # very old providers
        )

        if tool_calls:
            return Nodes.portfolio_tools["name"]
        else:
            return END
