"""Helpers and utilities for the screener node execution environment.

The screener operates on the broader market (no user portfolio df).
It has access to all yfinance data functions and the pre-built filter functions.
"""

import inspect
import re
from datetime import datetime
from typing import Callable, Dict, List
from zoneinfo import ZoneInfo

# Minimum ranked names before the node stops asking for relaxed thresholds.
MIN_RANKED_STOCKS_TARGET: int = 5

# Machine-parseable line printed by generated screener code (stdout is embedded in tool output).
META_SCREENED_COUNT_PATTERN: re.Pattern[str] = re.compile(
    r"^META_SCREENED_COUNT:\s*(\d+)\s*$",
    re.MULTILINE,
)


def parse_screened_count_from_tool_result(tool_result: str) -> int | None:
    """Extract META_SCREENED_COUNT from execute_python_code tool output, if present."""
    m = META_SCREENED_COUNT_PATTERN.search(tool_result)
    if not m:
        return None
    return int(m.group(1))


def build_relaxation_user_message(screened: int, relaxation_round: int) -> str:
    """Human follow-up when too few names passed the screen — steer wider / looser thresholds."""
    return (
        f"SCREENING_COVERAGE_REQUIREMENT: The last run reported META_SCREENED_COUNT={screened} "
        f"(relaxation round {relaxation_round}, target at least {MIN_RANKED_STOCKS_TARGET} names). "
        "At least 5 ranked stocks are required. Regenerate Python that: "
        "(1) widens the universe or adds adjacent sectors if the pool is small; "
        "(2) relaxes numeric thresholds in clear steps (e.g. PE cap, growth floor, margin floor) "
        "and documents BOTH previous and new values in === SCREENING_CONSTRAINTS ===; "
        "(3) keeps scoring so the best names still rank first; "
        "(4) uses statement/estimate fallbacks for sparse Yahoo info; "
        "(5) prints === SCREENING_CONSTRAINTS === (summary), === RANKED_RESULTS ===, then "
        "a single line exactly: META_SCREENED_COUNT: <N> where N equals the number of rows "
        "in the ranked table."
    )


from src.tools import yfinance_wrappers
from src.tools.filters import growth_filter, value_filter
from src.tools.yfinance_wrappers import (
    get_balance_sheet,
    get_capital_gains,
    get_cash_flow,
    get_dividends,
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
    get_last_close_prices_batch,
    get_major_holders,
    get_mutualfund_holders,
    get_revenue_estimate,
    get_ticker_info,
    get_ticker_price,
)

# All yfinance functions available in the screener environment.
# Includes BOTH + SCREENER-category functions (see yfinance_wrappers/__init__.py).
# Portfolio-only functions (calculate_profit_or_loss, portfolio metrics, etc.) are excluded.
SCREENER_YF_FUNCTION_NAMES: List[str] = [
    # BOTH: useful in both portfolio and screener contexts
    "get_balance_sheet",
    "get_income_statement",
    "get_cash_flow",
    "get_ticker_price",
    "get_last_close_price",
    "get_last_close_prices_batch",
    "get_ticker_info",
    # PORTFOLIO: income streams — included for yield-based screeners
    "get_dividends",
    "get_capital_gains",
    # SCREENER: forward-looking and market-research functions
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
]


def get_function_with_doc_string(fns: list[Callable]) -> str:
    chunks = []
    for fn in fns:
        sig = inspect.signature(fn)
        doc = (fn.__doc__ or "").strip().replace("\n", " ")
        chunks.append(f'def {fn.__name__}{sig}:\n    """{doc}"""\n    ...')
    return "\n\n".join(chunks)


def build_screener_execution_env() -> Dict[str, object]:
    """Build the sandboxed execution namespace for screener (no portfolio df)."""
    env: Dict[str, object] = {
        "__builtins__": __builtins__,
        "growth_filter": growth_filter,
        "value_filter": value_filter,
    }
    for func_name in SCREENER_YF_FUNCTION_NAMES:
        env[func_name] = getattr(yfinance_wrappers, func_name)
    return env


def screener_analysis_tool_sandbox_function_names() -> tuple[str, ...]:
    """Alphabetical names bound in the screener CodeAct sandbox (excludes ``__builtins__``)."""
    return tuple(sorted(k for k in build_screener_execution_env().keys() if k != "__builtins__"))


def build_screener_code_gen_invoke_args(
    messages: list,
    user_request: str,
) -> dict:
    """Assemble all template variables needed by SCREENER_CODE_GENERATION_PROMPT."""
    return {
        "messages": messages,
        "user_request": user_request,
        "current_date_time": datetime.now(ZoneInfo("Asia/Kolkata")).strftime(
            "%Y-%m-%d %H:%M:%S"
        ),
        "screening_context": (
            "You are screening the broader market — no user portfolio is involved. "
            "Define a relevant stock universe for the requested strategy, apply quantitative "
            "filters, score each stock, and return a ranked shortlist."
        ),
        "ticker_info_function_with_doc_string": get_function_with_doc_string([get_ticker_info]),
        "yf_financial_statement_function_with_doc_string": get_function_with_doc_string(
            [get_balance_sheet, get_income_statement, get_cash_flow]
        ),
        "yf_price_and_returns_function_with_doc_string": get_function_with_doc_string(
            [
                get_last_close_prices_batch,
                get_last_close_price,
                get_ticker_price,
                get_dividends,
                get_capital_gains,
            ]
        ),
        "yf_earnings_and_estimates_function_with_doc_string": get_function_with_doc_string(
            [
                get_earnings_estimate,
                get_revenue_estimate,
                get_earnings_history,
                get_eps_trend,
                get_eps_revisions,
                get_growth_estimates,
            ]
        ),
        "yf_ownership_and_insider_activity_function_with_doc_string": get_function_with_doc_string(
            [
                get_major_holders,
                get_institutional_holders,
                get_mutualfund_holders,
                get_insider_purchases,
                get_insider_transactions,
            ]
        ),
        "filter_functions_with_doc_string": get_function_with_doc_string(
            [growth_filter, value_filter]
        ),
    }
