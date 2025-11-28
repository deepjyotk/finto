"""Code generation node for portfolio analysis."""

from typing import List

import pandas as pd
from langchain_core.messages import AIMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda
from langchain_openai import ChatOpenAI
from langgraph.graph import END
from langgraph.runtime import get_runtime

from src.core.enums import LLMModel, Nodes
from src.core.json_logging import logger_for
from src.schemas.agent_state import AgentContext, AgentState

logger = logger_for(__name__)


class CodeGenerationNode:
    """LLM code generation node similar to the reference agent_step."""

    _PROMPT_TEMPLATE = ChatPromptTemplate.from_template(
        """You are a Python and Pandas expert helping analyze a user's stock portfolio.

        Write **only valid Python code** to answer the user's query about their portfolio.

        **Portfolio Excel file path:** {excel_path}

        **Preview of first rows:**
        {excel_preview}
        {symbol_context}

        **User request:**
        {user_request}

        ### Requirements
        - Use pandas: `import pandas as pd`
        - Read the Excel file from the provided path
        - If specific symbols are mentioned, filter the dataframe to those symbols first
        - Base analysis strictly on the user request
        - Use appropriate operations (groupby/agg/sort/filter/etc.)
        - Print the final result with `print(...)`
        - Output ONLY executable Python code (no comments, no explanations, no markdown)
        
        ### Available Portfolio Analysis Functions
        
        **Profit Calculation:**
        - calculate_profit(quantity, average_price, current_price)
          Returns: {{"profit": float}} - Profit/loss amount
          Example: `result = calculate_profit(100, 50.0, 55.0)  # {{"profit": 500.0}}`
        
        **Risk Calculation Functions:**
        
        1. **download_prices(tickers, start=None, end=None, interval="1d")**
           - Downloads adjusted close prices for given tickers
           - Returns: (DataFrame, List[str]) - prices and successfully retrieved tickers
           - Example: `prices, tickers = download_prices(["AAPL", "MSFT"], start="2023-01-01")`
        
        2. **portfolio_volatility(tickers, weights=None, start=None, end=None, interval="1d")**
           - Calculates annualized portfolio volatility
           - Returns: (annualized_vol, details_dict)
           - Example: `vol, details = portfolio_volatility(["AAPL", "MSFT"], [0.6, 0.4])`
        
        3. **max_drawdown(price_series)**
           - Calculates maximum drawdown from a price series
           - Returns: float (e.g., 0.25 for 25% drawdown)
        
        4. **max_drawdown_asset(tickers=None, prices=None, weights=None, start=None, end=None)**
           - Finds stocks with worst drawdowns
           - Returns: List[dict] with ticker, max_drawdown, peak_date, trough_date
        
        ### Available YFinance Data Functions
        All these functions take symbol_name as first parameter and return dict with data:
        
        **Financial Statements:**
        - get_balance_sheet(symbol, freq="yearly", pretty=False)
        - get_income_statement(symbol, freq="yearly", pretty=False)
        - get_cash_flow(symbol, freq="yearly", pretty=False)
        
        **Price & Returns:**
        - get_last_close_price(symbol)
          Returns: {{"symbol": str, "last_close_price": float, "date": str}}
          Example: `price_data = get_last_close_price("AAPL")  # {{"symbol": "AAPL", "last_close_price": 150.25, "date": "2024-01-15"}}`
        - download_prices(tickers, start=None, end=None, interval="1d")
          Returns: (DataFrame, List[str]) - prices and successfully retrieved tickers
        - get_dividends(symbol, period="max")
        - get_capital_gains(symbol, period="max")
        
        **Earnings & Estimates:**
        - get_earnings(symbol, freq="yearly")
        - get_earnings_estimate(symbol)
        - get_revenue_estimate(symbol)
        - get_earnings_history(symbol)
        - get_eps_trend(symbol)
        - get_eps_revisions(symbol)
        - get_growth_estimates(symbol)
        
        **Ownership & Insider Data:**
        - get_major_holders(symbol)
        - get_institutional_holders(symbol)
        - get_mutualfund_holders(symbol)
        - get_insider_purchases(symbol)
        - get_insider_transactions(symbol)
        
        All functions handle errors gracefully and return dictionaries.
        Example: `data = get_balance_sheet("AAPL")` returns {{"symbol": "AAPL", "balance_sheet": {{...}}}}"""
    )

    def __init__(self, max_attempts: int = 5):
        self.max_attempts = max_attempts

    def _build_symbol_context(self, symbols: List[str]) -> str:
        if symbols:
            return f"\n**Focus on these symbols only:** {', '.join(symbols)}"
        return "\n**Scope:** Analyze the entire portfolio (no specific symbol filter)."

    def get_runnable_sequence(self):
        """Return runnable for generating Python code from the portfolio query."""

        def code_generation_node_fn(state: AgentState) -> AgentState:
            if state.get("done"):
                return state

            runtime = get_runtime(AgentContext)
            context = runtime.context
            portfolio_model = context.get("portfolio_model", LLMModel.GPT4p1)
            llm_kwargs = {"model": portfolio_model.model_name, **portfolio_model.llm_kwargs}
            llm = ChatOpenAI(**llm_kwargs)

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

            excel_path = "portfolio.xlsx"
            try:
                df = pd.read_excel(excel_path)
                excel_preview = df.head().to_string()
            except Exception as exc:  # pragma: no cover - IO heavy
                error_msg = f"ERROR reading portfolio file: {exc}"
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

            symbol_context = self._build_symbol_context(state.get("symbol_names", []))
            chain = self._PROMPT_TEMPLATE | llm
            ai_response = chain.invoke(
                {
                    "excel_path": excel_path,
                    "excel_preview": excel_preview,
                    "symbol_context": symbol_context,
                    "user_request": user_request,
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
            return END

        attempts = state.get("attempts", 0)
        last_output = state.get("last_output") or ""
        last_code_success = state.get("last_code_success", False)

        if last_code_success and last_output:
            state["done"] = False
            return Nodes.final_response["name"]

        if attempts >= self.max_attempts:
            state["done"] = True
            state["final_answer"] = (
                f"Failed after {attempts} attempts.\n\nLast execution:\n{last_output}"
                if last_output
                else f"Failed after {attempts} attempts with no execution output."
            )
            return END

        state["done"] = False
        return Nodes.code_generation["name"]
