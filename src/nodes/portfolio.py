"""Portfolio agent node for financial computations."""

from datetime import datetime, timedelta, timezone
from typing import Final, List

from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnableLambda
from langchain_openai import ChatOpenAI
from langgraph.graph import END

from src.core.enums import LLMModel, Nodes
from src.schemas.portfolio import PortfolioQuery
from src.tools.calculate_profit_tool import calculate_profit
from src.tools.get_row_tool import get_holding_by_symbol
from src.tools.get_symbol_name import get_symbol_name
from src.tools.get_ticker_price import get_ticker_price
from src.tools.yf_tools import (
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
)
from src.core.json_logging import logger_for

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
        llm = ChatOpenAI(model=model.value, temperature=0)
        chain = self._agent_prompt_template() | llm.bind_tools(
            [
                get_symbol_name,
                get_ticker_price,
                get_holding_by_symbol,
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
        if ai_message_count > Nodes.portfolio.get("max_ai_messages_allowed"):
            logger.warning(
                "Portfolio agent max iterations (%d) exceeded, routing to unknown_node",
                Nodes.portfolio.get("max_ai_messages_allowed"),
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
            return Nodes.portfolio_tools.get("name")
        else:
            return END
