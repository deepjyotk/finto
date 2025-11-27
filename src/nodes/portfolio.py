"""Portfolio agent node for financial computations."""

from datetime import datetime, timedelta, timezone

# from pandas import pd
from typing import Final, cast

from langchain_core.messages import AIMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnableLambda
from langchain_openai import ChatOpenAI
from langgraph.graph import END
from langgraph.runtime import get_runtime

from src.core.enums import LLMModel, Nodes
from src.core.json_logging import logger_for
from src.schemas.agent_state import AgentContext, AgentState
from src.tools.extract_portfolio_data import extract_portfolio_data
from src.tools.get_symbol_name import get_symbol_names

logger = logger_for(__name__)


class PortfolioNode:
    """Portfolio agent node for financial computations."""

    _SYSTEM_PROMPT: Final[
        str
    ] = """You are PortfolioAgent — a precise financial assistant focused on Indian equities (NSE/BSE) and the user's portfolio.         
        Now (UTC): {today_utc_iso}
        Now (IST, UTC+5:30): {today_ist_iso}

        CAPABILITIES & TOOLS
        You have access to 2 powerful tools:
        
        1. **get_symbol_names(query)**: Extract stock symbols from user queries
        
        2. **extract_portfolio_data(query, symbols)**: POWERFUL code generation tool that:
           - Analyzes portfolio data using Python/Pandas
           - Can call ANY YFinance function for market data
           - Handles complex multi-step queries
           
           Available functions in generated code:
           • Profit calculation: calculate_profit(quantity, average_price, current_price)
           • Portfolio risk: download_prices, portfolio_volatility, max_drawdown, max_drawdown_asset
           • Financials: get_balance_sheet, get_income_statement, get_cash_flow
           • Price & returns: get_ticker_price, get_dividends, get_capital_gains
           • Earnings: get_earnings, get_earnings_estimate, get_revenue_estimate, get_earnings_history
           • Estimates: get_eps_trend, get_eps_revisions, get_growth_estimates
           • Ownership: get_major_holders, get_institutional_holders, get_mutualfund_holders
           • Insider: get_insider_purchases, get_insider_transactions

        POLICY
        1) Tool selection:
           - For queries needing market data (prices, financials, earnings, etc.) → extract_portfolio_data
           - For simple P&L calculations → calculate_profit
           - ALWAYS call get_symbol_names FIRST to extract symbols from query
        
        2) Data integrity:
           - Prefer NSE if exchange unspecified; state this assumption
           - Never fabricate data; if a tool fails, say so and suggest alternatives

        3) Formatting:
           - Interpret dates in IST (fallback: UTC)
           - Prices: 2 decimals; percentages: 1 decimal; use ₹ for INR

        4) Output style (succinct, factual, actionable):
           - Direct answer in 1–2 sentences
           - Compact breakdown (bullets/table) for metrics
           - End with "Notes" (assumptions, data freshness)

        WORKFLOW
        Step 1: Call get_symbol_names(user_query) to extract symbols
        Step 2: Call extract_portfolio_data or calculate_profit as needed
        Step 3: Synthesize and present results

        Portfolio column metadata:
        {portfolio_column_metadata}
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
        DEFAULT_PORTFOLIO_COLUMN_METADATA: dict[str, list[str]] = {
            "Symbols": ["The symbol tickers in the user's portfolio"],
            "Quantity Available": ["The quantity of shares available for each symbol"],
            "Average Price": ["The average purchase price for each symbol"],
            "Unrealized P&L": ["The unrealized profit or loss for each symbol"],
            "Unrealized P&L Pct": ["The unrealized profit or loss percentage for each symbol"],
        }
        portfolio_column_metadata = DEFAULT_PORTFOLIO_COLUMN_METADATA
        complete_template = chat_template.partial(
            today_utc_iso=now_utc,
            today_ist_iso=now_ist,
            portfolio_column_metadata=portfolio_column_metadata,
        )
        return complete_template

    def get_runnable_sequence(self):
        """
        Get the runnable sequence instance.

        Returns:
            A runnable that takes AgentState and returns AgentState
        """
        portfolio_prompt = self._agent_prompt_template()

        def portfolio_node_fn(state: AgentState) -> AgentState:
            # Access AgentContext via runtime
            runtime = get_runtime(AgentContext)
            context = runtime.context
            portfolio_model = context.get("portfolio_model", LLMModel.GPT4p1)

            # Use model name and kwargs from enum
            llm_kwargs = {"model": portfolio_model.model_name, **portfolio_model.llm_kwargs}
            llm = ChatOpenAI(**llm_kwargs)

            # Tool-enabled answer stage
            # YFinance and profit calculation functions are now available within extract_portfolio_data
            answer_chain = portfolio_prompt | llm.bind_tools(
                [
                    get_symbol_names,
                    extract_portfolio_data,
                ]
            )

            messages = state.get("messages", [])
            result = answer_chain.invoke(cast(dict, state))
            # result is expected to be an AIMessage, but handle list defensively
            if isinstance(result, list):
                new_messages = messages + result
            else:
                new_messages = messages + [result]
            return {
                **state,
                "messages": new_messages,
            }

        return RunnableLambda(portfolio_node_fn)

    def portfolio_agent_decision(self, state: AgentState) -> str:
        """
        Return either the portfolio tools node name (to execute tools next)
        OR the extract_context node name
        OR the string "END" (to terminate the run).

        Logic: look for the last AIMessage; if it requested portfolio context extraction then route to the exctract context node
        if it requested for any tool calls,
        route to the tools node; otherwise END.
        """
        messages = state.get("messages", [])

        # count AI messages and check if has crossed the limit
        ai_message_count = sum(isinstance(item, AIMessage) for item in messages)
        max_allowed = Nodes.portfolio["max_ai_messages_allowed"]
        if ai_message_count > max_allowed:
            logger.warning(
                "Portfolio agent max iterations (%d) exceeded, routing to unknown_node",
                max_allowed,
            )
            return END
        if not messages:
            return END

        # Find the most recent AI turn (ignore trailing ToolMessage(s))
        last_ai = next((m for m in reversed(messages) if isinstance(m, AIMessage)), None)
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
