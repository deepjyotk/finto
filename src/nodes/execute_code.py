"""Code execution node that mirrors the reference execute_code behavior."""

import contextlib
import io
from typing import Dict

from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableLambda

from src.core.json_logging import logger_for
from src.schemas.agent_state import AgentState
from src.tools import yfinance_wrappers
from src.tools.calculate_profit_tool import calculate_profit
from src.tools.portfolio_risk import (
    download_prices,
    max_drawdown,
    max_drawdown_asset,
    portfolio_volatility,
)

logger = logger_for(__name__)


class ExecuteCodeNode:
    """Executes generated Python code with access to portfolio utilities."""

    _YF_FUNCTIONS = [
        "get_balance_sheet",
        "get_income_statement",
        "get_cash_flow",
        "get_dividends",
        "get_capital_gains",
        "get_earnings",
        "get_earnings_estimate",
        "get_revenue_estimate",
        "get_earnings_history",
        "get_eps_trend",
        "get_eps_revisions",
        "get_growth_estimates",
        "get_major_holders",
        "get_institutional_holders",
        "get_mutualfund_holders",
        "get_insider_purchases",
        "get_insider_transactions",
        "get_ticker_price",
        "get_last_close_price",
    ]

    def _build_global_env(self) -> Dict[str, object]:
        """Build the safe execution environment."""
        env: Dict[str, object] = {
            "__builtins__": __builtins__,
            "calculate_profit": calculate_profit,
            "download_prices": download_prices,
            "portfolio_volatility": portfolio_volatility,
            "max_drawdown": max_drawdown,
            "max_drawdown_asset": max_drawdown_asset,
        }
        for func_name in self._YF_FUNCTIONS:
            env[func_name] = getattr(yfinance_wrappers, func_name)
        return env

    def get_runnable_sequence(self):
        """Return runnable that executes generated Python code."""

        def execute_code_node_fn(state: AgentState) -> AgentState:
            if state.get("done"):
                return state

            code = state.get("last_code")
            messages = state.get("messages", [])
            if not code:
                observation = "Execution environment: no code to execute (last_code was empty)."
                env_msg = HumanMessage(content=observation)
                return {
                    **state,
                    "messages": messages + [env_msg],
                    "last_output": observation,
                    "last_code_success": False,
                }

            global_env = self._build_global_env()
            local_env: Dict[str, object] = {}
            stdout_capture = io.StringIO()
            error_text = None
            is_error = False

            try:
                with contextlib.redirect_stdout(stdout_capture):
                    exec(code, global_env, local_env)
                stdout_text = stdout_capture.getvalue().strip() or "<no output printed to stdout>"
                status = "success"
            except Exception as exc:  # pragma: no cover - executed code varies
                stdout_text = stdout_capture.getvalue().strip()
                error_text = repr(exc)
                status = "error"
                is_error = True

            sections = [
                "Execution result:",
                f"STATUS: {status}",
                f"STDOUT:\n{stdout_text}",
            ]
            if error_text:
                sections.append(f"ERROR:\n{error_text}")

            observation = "\n\n".join(sections)
            attempts = state.get("attempts", 0) + 1
            last_code_success = not is_error
            env_msg = HumanMessage(content=observation)

            return {
                **state,
                "messages": messages + [env_msg],
                "last_output": observation,
                "attempts": attempts,
                "last_code_success": last_code_success,
            }

        return RunnableLambda(execute_code_node_fn)
