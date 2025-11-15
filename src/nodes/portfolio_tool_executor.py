import json
from typing import List
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda
from langchain_openai import ChatOpenAI

from src.core.enums import LLMModel
from src.tools.get_ticker_price import get_ticker_price
from src.tools.calculate_profit_tool import calculate_profit
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


class PortfolioToolExecutorNode:
    """Issues tool calls (e.g., get_ticker_price) based on plan + context."""

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
                    (
                        "You are a tool-calling assistant for portfolio analysis. Output ONLY a JSON array. No prose, no explanations.\n" 
                        "Tools you may call (exact names, case-sensitive): get_ticker_price, calculate_profit, get_major_holders, get_institutional_holders, "
                        "get_mutualfund_holders, get_insider_purchases, get_insider_transactions, get_dividends, get_capital_gains, get_balance_sheet, get_cash_flow, "
                        "get_income_statement, get_earnings_estimate, get_revenue_estimate, get_earnings_history, get_eps_trend, get_eps_revisions, get_growth_estimates, get_earnings.\n" 
                        "Schema description (write JSON accordingly): Each element is an object with exactly two keys: 'tool' (string) and 'args' (object).\n" 
                        "Rules: 1) Return [] if no tools needed. 2) One get_ticker_price per distinct symbol. 3) Include calculate_profit only if you have current_price, buy_price, quantity. 4) Args minimal required fields. 5) Follow selection instructions in plan (e.g., top 5 by quantity). 6) Omit undeclared symbols silently.\n" 
                        "Do not include any keys other than 'tool' and 'args'. Produce ONLY the JSON array."
                    ),
                ),
                (
                    "user",
                    "Plan: {plan}\nPortfolio (JSON): {portfolio_json}\nUser Query: {user_query}",
                ),
            ]
        )

        # Runtime guard: ensure only expected template variables are present. If stray variables appear (e.g. '"tool"'), rebuild a minimal safe prompt.
        expected_vars = {"plan", "portfolio_json", "user_query"}
        current_vars = set(getattr(prompt, "input_variables", []))
        if current_vars != expected_vars:
            safe_system = (
                "You are a portfolio tool-calling assistant. Output ONLY a JSON array. Each item has keys 'tool' and 'args'. "
                "Return [] if no tools needed. Tools allowed: get_ticker_price, calculate_profit, get_major_holders, get_institutional_holders, "
                "get_mutualfund_holders, get_insider_purchases, get_insider_transactions, get_dividends, get_capital_gains, get_balance_sheet, get_cash_flow, "
                "get_income_statement, get_earnings_estimate, get_revenue_estimate, get_earnings_history, get_eps_trend, get_eps_revisions, get_growth_estimates, get_earnings."
            )
            prompt = ChatPromptTemplate.from_messages([
                ("system", safe_system),
                ("user", "Plan: {plan}\nPortfolio (JSON): {portfolio_json}\nUser Query: {user_query}"),
            ])
        # Bind full portfolio tool set so the LLM can call any needed tool (price, fundamentals, ownership, gains, statements, etc.)
        llm = ChatOpenAI(model=model.value, temperature=0).bind_tools([
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
        ])

        def _build_input(msgs: List[BaseMessage]):
            plan = []
            portfolio = []
            user_query = self._latest_user_text(msgs)
            for m in msgs:
                n = getattr(m, "name", "")
                if n == "portfolio_reasoning":
                    try:
                        data = json.loads(m.content) if isinstance(m.content, str) else m.content
                        if isinstance(data, dict):
                            plan = data.get("plan", [])
                    except Exception:
                        pass
                elif n == "context_loader":
                    try:
                        data = json.loads(m.content) if isinstance(m.content, str) else m.content
                        if isinstance(data, dict):
                            portfolio = data.get("portfolio_data", [])
                    except Exception:
                        pass
            return {
                "plan": "\n".join(plan),
                "portfolio_json": json.dumps(portfolio)[:8000],
                "user_query": user_query,
            }

        # Returns an AIMessage containing tool_calls
        return RunnableLambda(_build_input) | (prompt | llm) | RunnableLambda(lambda ai: [ai])
