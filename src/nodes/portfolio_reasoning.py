from typing import List
import json
from pydantic import BaseModel, Field
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnableLambda, RunnableSequence
from langchain_openai import ChatOpenAI

from src.core.enums import LLMModel


class PlanResponse(BaseModel):
    plan: List[str] = Field(default_factory=list)
    required_tools: List[str] = Field(default_factory=list)
    requires_portfolio_data: bool = True


class PortfolioReasoningNode:
    """Interprets the user query and outputs a compact execution plan."""

    def _latest_user_text(self, msgs: List[BaseMessage]) -> str:
        for m in reversed(msgs or []):
            t = getattr(m, "type", None) or getattr(m, "role", None)
            if t in ("human", "user"):
                c = getattr(m, "content", "")
                return c if isinstance(c, str) else str(c)
        return getattr(msgs[-1], "content", "") if msgs else ""

    def get_runnable_sequence(self, model: LLMModel):
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are a planning assistant for portfolio analysis. "
                    "Given the user query and available tools, return ONLY a JSON with keys: "
                    "plan (list of steps), required_tools (list of tool names), "
                    "requires_portfolio_data (boolean). No extra text.\n\n"
                    "Available tools (exact names): "
                    "get_ticker_price, calculate_profit, get_major_holders, get_institutional_holders, "
                    "get_mutualfund_holders, get_insider_purchases, get_insider_transactions, get_dividends, "
                    "get_capital_gains, get_balance_sheet, get_cash_flow, get_income_statement, "
                    "get_earnings_estimate, get_revenue_estimate, get_earnings_history, get_eps_trend, "
                    "get_eps_revisions, get_growth_estimates, get_earnings.",
                ),
                MessagesPlaceholder("messages"),
            ]
        )
        llm = ChatOpenAI(model=model.value, temperature=0).with_structured_output(PlanResponse)

        def _wrap(msgs: List[BaseMessage]):
            return {"messages": msgs}

        def _to_ai(plan: PlanResponse):
            return [AIMessage(content=plan.model_dump_json(), name="portfolio_reasoning")]

        return RunnableLambda(_wrap) | (prompt | llm) | RunnableLambda(_to_ai)
