"""LangChain agent with a yfinance tool to fetch ticker prices.

Provides `query(question: str) -> str` to run the agent and return the final answer.
"""
from ast import List
import os
import sys
from pathlib import Path
from unittest.mock import Base
from asyncpg import HeldCursorRequiresSameIsolationLevelError
from dotenv import load_dotenv

from langchain_openai import ChatOpenAI
from langchain.agents import create_agent
from pydantic import BaseModel, Field
from typing import Dict
import logging

# logging.basicConfig(level=logging.DEBUG, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
# logger = logging.getLogger("computation_agent")

from langchain_core.messages import HumanMessage, BaseMessage
 


# from src.tools.yfinance_wrappers.yfinance_wrappers import (
#     get_major_holders,
#     get_institutional_holders,
#     get_mutualfund_holders,
#     get_insider_purchases,
#     get_insider_transactions,
#     get_dividends,
#     get_capital_gains,
#     get_balance_sheet,
#     get_cash_flow,
#     get_income_statement,
#     get_earnings_estimate,
#     get_revenue_estimate,
#     get_earnings_history,
#     get_eps_trend,
#     get_eps_revisions,
#     get_growth_estimates,
#     get_earnings,
# )

# def _safe_import(path: str, name: str):
#     try:
#         module = __import__(path, fromlist=[name])
#         return getattr(module, name)
#     except Exception:
#         return None

# # Core / small tools
# get_ticker_price = _safe_import("src.tools.get_ticker_price", "get_ticker_price")
# get_entire_row = _safe_import("src.tools.get_row_tool", "get_entire_row")
# get_symbol_name = _safe_import("src.tools.get_symbol_name", "get_symbol_name")
# calculate_profit = _safe_import("src.tools.calculate_profit_tool", "calculate_profit")

# # financial metrics helpers
# calculate_total_investment_in_specific_stock = _safe_import(
#     "src.tools.financial_metrics_tools", "calculate_total_investment_in_specific_stock"
# )
# get_portfolio_weights = _safe_import("src.tools.financial_metrics_tools", "get_portfolio_weights")
# calculate_roi = _safe_import("src.tools.financial_metrics_tools", "calculate_roi")

# # yfinance wrappers (many helpers)
# _yf_mod = None
# try:
#     _yf_mod = __import__("src.tools.yfinance_wrappers.yfinance_wrappers", fromlist=["*"])
# except Exception:
#     _yf_mod = None

# if _yf_mod:
#     get_major_holders = getattr(_yf_mod, "get_major_holders", None)
#     get_institutional_holders = getattr(_yf_mod, "get_institutional_holders", None)
#     get_mutualfund_holders = getattr(_yf_mod, "get_mutualfund_holders", None)
#     get_insider_purchases = getattr(_yf_mod, "get_insider_purchases", None)
#     get_insider_transactions = getattr(_yf_mod, "get_insider_transactions", None)
#     get_dividends = getattr(_yf_mod, "get_dividends", None)
#     get_capital_gains = getattr(_yf_mod, "get_capital_gains", None)
#     get_balance_sheet = getattr(_yf_mod, "get_balance_sheet", None)
#     get_cash_flow = getattr(_yf_mod, "get_cash_flow", None)
#     get_income_statement = getattr(_yf_mod, "get_income_statement", None)
#     get_earnings_estimate = getattr(_yf_mod, "get_earnings_estimate", None)
#     get_revenue_estimate = getattr(_yf_mod, "get_revenue_estimate", None)
#     get_earnings_history = getattr(_yf_mod, "get_earnings_history", None)
#     get_eps_trend = getattr(_yf_mod, "get_eps_trend", None)
#     get_eps_revisions = getattr(_yf_mod, "get_eps_revisions", None)
#     get_growth_estimates = getattr(_yf_mod, "get_growth_estimates", None)
#     get_earnings = getattr(_yf_mod, "get_earnings", None)
# else:
#     get_major_holders = get_institutional_holders = get_mutualfund_holders = None
#     get_insider_purchases = get_insider_transactions = get_dividends = None
#     get_capital_gains = get_balance_sheet = get_cash_flow = None
#     get_income_statement = get_earnings_estimate = get_revenue_estimate = None
#     get_earnings_history = get_eps_trend = get_eps_revisions = None
#     get_growth_estimates = get_earnings = None

# # assemble the tools list preserving a stable order
# for t in (
#     get_ticker_price,
#     get_symbol_name,
#     get_entire_row,
#     calculate_profit,
#     calculate_total_investment_in_specific_stock,
#     get_portfolio_weights,
#     calculate_roi,
#     get_major_holders,
#     get_institutional_holders,
#     get_mutualfund_holders,
#     get_insider_purchases,
#     get_insider_transactions,
#     get_dividends,
#     get_capital_gains,
#     get_balance_sheet,
#     get_cash_flow,
#     get_income_statement,
#     get_earnings_estimate,
#     get_revenue_estimate,
#     get_earnings_history,
#     get_eps_trend,
#     get_eps_revisions,
#     get_growth_estimates,
#     get_earnings,
# ):
#     if t is not None:
#         available_tools.append(t)
# load environment
# Ensure project root is on sys.path so `import src.*` works when running this file directly.
# This makes `from src.tools...` resolvable even when the module is executed as a script.
ROOT = Path(__file__).resolve().parents[2]
root_str = str(ROOT)
if root_str not in sys.path:
    sys.path.insert(0, root_str)

from src.tools.get_ticker_price import get_ticker_price
from src.tools.yfinance_wrappers.yfinance_wrappers import (
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
load_dotenv()

# from .schemas import AgentMessage, AgentResponse

# Import available tools from the project's tools package. Use safe imports
# so an individual tool module with import-time side-effects doesn't break app startup.
available_tools = []

for i in (
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
):
    if i:
        available_tools.append(i)

# # ---- paste after available_tools is assembled (before create_agent) ----
# import functools
# import time
# import collections
# import json

# # Circular buffer of recent calls
# TOOL_CALL_LOG = collections.deque(maxlen=1000)
# # Simple stack to track nested tool calls
# TOOL_CALL_STACK = []

# # Config
# RECURSION_ALERT_DEPTH = 20  # raise/log if stack > this
# RECURSION_REPEAT_THRESHOLD = 6  # detect repeated tool call pattern length

# def _record(event: dict):
#     event["timestamp"] = time.time()
#     TOOL_CALL_LOG.append(event)
#     # Log concise line for each event (debug level)
#     try:
#         # avoid heavy reprs in logs; show tool, phase and stack depth
#         logger.debug("TOOL_EVENT %s tool=%s phase=%s stack_len=%d",
#                      time.strftime("%H:%M:%S", time.localtime(event["timestamp"])),
#                      event.get("tool"),
#                      event.get("phase"),
#                      len(event.get("stack", [])))
#     except Exception:
#         # fallback safe print if logging fails
#         print("TOOL_EVENT", event)

# def wrap_tool_callable(func, name: str | None = None):
#     name = name or getattr(func, "__name__", repr(func))

#     @functools.wraps(func)
#     def _wrapped(*args, **kwargs):
#         stack_snapshot = list(TOOL_CALL_STACK)
#         _record({"phase": "start", "tool": name, "args": repr(args), "kwargs": repr(kwargs), "stack": stack_snapshot})
#         TOOL_CALL_STACK.append(name)
#         # recursion detection - alert early
#         if len(TOOL_CALL_STACK) > RECURSION_ALERT_DEPTH:
#             _record({"phase": "recursion_alert", "tool": name, "stack": list(TOOL_CALL_STACK)})
#         try:
#             result = func(*args, **kwargs)
#             _record({"phase": "end", "tool": name, "result": repr(result), "stack": list(TOOL_CALL_STACK)})
#             return result
#         except Exception as e:
#             _record({"phase": "error", "tool": name, "error": repr(e), "stack": list(TOOL_CALL_STACK)})
#             raise
#         finally:
#             TOOL_CALL_STACK.pop()

#     return _wrapped

# # Helper to detect repeating sequences in the log (useful to detect loops)
# def detect_repeated_sequence(max_seq_len: int = 6, lookback: int = 200):
#     names = [entry["tool"] for entry in TOOL_CALL_LOG if entry.get("phase") == "start"][-lookback:]
#     # try sequence lengths 1..max_seq_len
#     for seq_len in range(1, max_seq_len + 1):
#         if len(names) < seq_len * RECURSION_REPEAT_THRESHOLD:
#             continue
#         seq = names[-seq_len:]
#         repeats = 1
#         idx = len(names) - seq_len - 1
#         while idx - seq_len + 1 >= 0 and names[idx - seq_len + 1: idx + 1] == seq:
#             repeats += 1
#             idx -= seq_len
#         if repeats >= RECURSION_REPEAT_THRESHOLD:
#             return {"sequence": seq, "repeats": repeats}
#     return None

# # Replace functions in available_tools with wrapped versions
# wrapped_tools = []
# for t in available_tools:
#     # tools could be callables or LangChain Tool objects with .func or .run
#     try:
#         # LangChain's Tool (older versions) exposes a callable 'func' or 'run'
#         func = getattr(t, "func", None) or getattr(t, "run", None)
#         if callable(func) and hasattr(t, "name"):
#             wrapped = wrap_tool_callable(func, getattr(t, "name", None))
#             # try to produce a new Tool-like wrapper preserving tool metadata if possible.
#             # Many LangChain Tool objects are simple dataclasses, attempt to replace function:
#             try:
#                 # Some Tool implementations offer .with_changes(func=...) to create a new instance
#                 wrapped_tool = t.with_changes(func=wrapped)  # type: ignore[attr-defined]
#             except Exception:
#                 # fallback: use a plain callable wrapper
#                 wrapped_tool = wrapped
#             wrapped_tools.append(wrapped_tool)
#         elif callable(t):
#             wrapped_tools.append(wrap_tool_callable(t, getattr(t, "__name__", None)))
#         else:
#             wrapped_tools.append(t)
#     except Exception:
#         # If anything fails, keep the original tool to avoid blocking startup
#         wrapped_tools.append(t)

# # Replace available_tools with the wrapped list
# available_tools = wrapped_tools

# # Utility functions available for debugging
# def get_tool_log(as_json: bool = False):
#     entries = list(TOOL_CALL_LOG)
#     if as_json:
#         return json.dumps(entries, default=str, indent=2)
#     return entries

# def clear_tool_log():
#     TOOL_CALL_LOG.clear()
#     TOOL_CALL_STACK.clear()

# Optionally, after a query run, check for repeated sequences:
# rep = detect_repeated_sequence()
# if rep:
#     print("Detected repeated sequence:", rep)
# -----------------------------------------------------------------------

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")


class ComputationQuery(BaseModel):
    """Outputs the final computation result of the user's query."""

    computation: str = Field(
        ...,
        description="The final result of the computation that was performed.",
    )

class ToolSequence(BaseModel):
    """Represents the ordered list of tool calls to execute."""

    tool_sequence: Dict[int, str] = Field(
        ...,
        title="Tool Sequence",
        description="A mapping of sequence order number to tool name.",
    )


_PROMPT_FILE = Path(__file__).resolve().parent / "system_prompt.txt"
if _PROMPT_FILE.exists():
    system_prompt = _PROMPT_FILE.read_text(encoding="utf-8")
_llm = ChatOpenAI(model=DEFAULT_MODEL, temperature=0)
_tool_execution_sequence_agent = create_agent(
    model=_llm,
    tools=available_tools,
    system_prompt=system_prompt
)
raw = _tool_execution_sequence_agent.invoke( {"messages": [{"role": "user", "content": "What is the stock price and who are the major shareholders of USHAMART.NS?"}]})

print("LLM Response:", raw)


# _PROMPT_FILE = Path(__file__).resolve().parent / "system_prompt.txt"
# if _PROMPT_FILE.exists():
#     system_prompt = _PROMPT_FILE.read_text(encoding="utf-8")
# else:
#     system_prompt = (
#         "You are a precise financial assistant.\n"
#         "You have access to a set of tools (finance APIs and portfolio helpers).\n"
#         "When the user asks for facts, data, or calculations, call the relevant tools to retrieve or compute results;"
#         "Cite the data source when relevant. Provide a concise final answer."
#         "If a tool call doesn't return any data, respond with 'No data found.' for that particular query.\n"
#     )
# _agent = create_agent(
#     model=_llm,
#     tools=available_tools,
#     system_prompt=system_prompt
# )

# raw = _agent.invoke(
#         {"messages": [{"role": "user", "content": "what is the price of  USHAMART.NS and give me the major shareholders of this company?"}]},
#         config={"recursion_limit": 12},
#     )
# print(raw)
# try:
#     raw = _agent.invoke(
#         {"messages": [{"role": "user", "content": "what is the price of  USHAMART.NS and give me the major shareholders of this company?"}]},
#         config={"recursion_limit": 12},
#     )
#     print(raw)
# except Exception as e:
#     # Dump last 200 tool log entries (JSON) for debugging
#     logger.exception("Agent invocation failed: %s", e)
#     try:
#         logger.debug("Recent tool calls: %s", get_tool_log(as_json=True))
#         rep = detect_repeated_sequence()
#         if rep:
#             logger.warning("Detected repeated tool sequence: %s", rep)
#     except Exception as dump_err:
#         logger.exception("Failed dumping tool log: %s", dump_err)
#     raise

# def query(question: str) -> str:
#     """Run the agent on the provided question and return the final answer text.

#     The agent is configured to prefer tool calls for data retrieval/computation.
#     """
#     if not isinstance(question, str) or not question.strip():
#         raise ValueError("question must be a non-empty string")
#     if not OPENAI_API_KEY:
#         raise RuntimeError("OPENAI_API_KEY is not set. Set it in the environment or .env file")
#     raw = _agent.invoke(
#         {"messages": [{"role": "user", "content": question}]},
#         config={"recursion_limit": 12},
#     )
#     # Expect the last message to be the AI's final content string
#     msgs = raw.get("messages") or []
#     if msgs and hasattr(msgs[-1], "content"):
#         return msgs[-1].content or ""
#     # Fallback: stringify raw
#     return str(raw)

