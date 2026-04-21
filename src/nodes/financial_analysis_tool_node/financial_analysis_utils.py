"""Helpers and small models for portfolio symbol scope, execution env, and code-gen context."""

import inspect
import re
from datetime import datetime
from typing import Callable, Dict, List, Literal
from zoneinfo import ZoneInfo

from langchain_core.messages import AIMessage, BaseMessage
from pydantic import BaseModel

from src.core.json_logging import logger_for
from src.core.schema import EquityHoldingSchema
from src.nodes.financial_analysis_tool_node.financial_analysis_prompt import (
    SYMBOL_CLASSIFIER_PROMPT_WORKER,
    SYMBOL_EXTRACTION_PROMPT,
)
from src.tools import yfinance_wrappers
from src.tools.calculate_profit_tool import calculate_profit_or_loss
from src.tools.filters import growth_filter, value_filter
from src.tools.portfolio_metrics import (
    cagr,
    calculate_all_metrics,
    current_ratio,
    debt_to_equity_ratio,
    dividend_yield,
    downside_deviation,
    portfolio_return,
    profit_margin,
    roe,
    roi,
    sharpe_ratio,
    sortino_ratio,
    win_rate,
)
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
)

# ── Tool Registry (populates on first import) ──────────────────────────────
import src.tools.register_all  # noqa: F401  — side-effect: populates registry
from src.tools.registry import registry as _tool_registry

logger = logger_for(__name__)

# Parsed from generated code stdout (embedded in execute_python_code tool output).
META_PRICE_OK_RE = re.compile(r"^META_PRICE_FETCH_OK:\s*(\d+)\s*$", re.MULTILINE)
META_PRICE_FAIL_RE = re.compile(r"^META_PRICE_FETCH_FAILED:\s*(\d+)\s*$", re.MULTILINE)
META_PRICE_FAILED_SYMS_RE = re.compile(
    r"^META_PRICE_FETCH_FAILED_SYMBOLS:\s*(.+)\s*$", re.MULTILINE
)
THROTTLE_SUSPECTED_RE = re.compile(
    r"^THROTTLE_OR_SPARSE_DATA_SUSPECTED:\s*(true|false)\s*$", re.MULTILINE
)


def parse_portfolio_price_meta_from_tool_output(tool_result: str) -> dict:
    """Extract price-fetch summary lines from tool output for partial-retry logic."""
    out: dict = {
        "ok": None,
        "failed": None,
        "failed_symbols": [],
        "throttle_suspected": None,
    }
    m = META_PRICE_OK_RE.search(tool_result)
    if m:
        out["ok"] = int(m.group(1))
    m = META_PRICE_FAIL_RE.search(tool_result)
    if m:
        out["failed"] = int(m.group(1))
    m = META_PRICE_FAILED_SYMS_RE.search(tool_result)
    if m:
        raw = m.group(1).strip()
        if raw and raw.lower() != "none":
            out["failed_symbols"] = [x.strip() for x in raw.split(",") if x.strip()]
    m = THROTTLE_SUSPECTED_RE.search(tool_result)
    if m:
        out["throttle_suspected"] = m.group(1).lower() == "true"
    return out


def build_partial_price_retry_user_message(meta: dict, task: str) -> str:
    """Follow-up when prices were partial so the model regenerates using batch APIs."""
    failed = meta.get("failed") or 0
    syms = meta.get("failed_symbols") or []
    throttle = meta.get("throttle_suspected")
    sym_part = ", ".join(syms[:80]) if syms else "(see prior STDOUT)"
    throttle_note = (
        " Prior output flagged THROTTLE_OR_SPARSE_DATA_SUSPECTED=true — Yahoo often does this "
        "when using many sequential get_last_close_price calls."
        if throttle
        else " Use batch price helpers instead of per-symbol loops."
    )
    return (
        f"PRICE_FETCH_PARTIAL: The last successful run still missed prices for {failed} holding(s). "
        f"Failed symbols (sample/list): {sym_part}.{throttle_note} "
        "Regenerate Python that (1) uses get_last_close_prices_batch(symbol_list) OR a single "
        "yf.download on the full normalized symbol list for current prices — NOT a loop of "
        "get_last_close_price; (2) reprints META_PRICE_FETCH_OK / META_PRICE_FETCH_FAILED / "
        "META_PRICE_FETCH_FAILED_SYMBOLS / THROTTLE_OR_SPARSE_DATA_SUSPECTED lines; "
        f"(3) completes the same user task: {task!r}."
    )


YF_FUNCTION_NAMES = [
    "get_balance_sheet",
    "get_income_statement",
    "get_cash_flow",
    "get_dividends",
    "get_capital_gains",
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
    "get_last_close_prices_batch",
    "get_ticker_info",
]


def get_function_with_doc_string(fns: list[Callable]) -> str:
    chunks = []
    for fn in fns:
        sig = inspect.signature(fn)
        doc = (fn.__doc__ or "").strip().replace("\n", " ")
        chunks.append(f'def {fn.__name__}{sig}:\n    """{doc}"""\n    ...')
    return "\n\n".join(chunks)


class SymbolExtractionResult(BaseModel):
    """Pydantic model for validating symbol extraction output. Returns a list of stock symbols found in the user query."""

    symbol_names: List[str]


class QueryTypeResult(BaseModel):
    """Pydantic model for classifying portfolio query scope."""

    query_type: Literal["specific_stocks_scope", "entire_portfolio_scope"]


def build_portfolio_scope_message(task: str, llm) -> tuple[AIMessage, List[str]]:
    """Classify scope, extract symbols when needed, return the scope AIMessage and symbol list."""
    extracted_symbols: List[str] = []
    try:
        classifier_chain = SYMBOL_CLASSIFIER_PROMPT_WORKER | llm.with_structured_output(
            QueryTypeResult
        )
        query_type_result = classifier_chain.invoke({"user_query": task})
        if query_type_result.query_type == "specific_stocks_scope":
            symbol_chain = SYMBOL_EXTRACTION_PROMPT | llm.with_structured_output(
                SymbolExtractionResult
            )
            sym_result = symbol_chain.invoke({"user_query": task})
            from src.tools.get_symbol_name import get_symbol_names

            extracted_symbols = get_symbol_names(sym_result.symbol_names)
            logger.info("financial_analysis_tool extracted symbols: %s", extracted_symbols)
    except Exception as exc:
        logger.warning("Symbol extraction failed in financial_analysis_tool: %s", exc)

    scope_msg = AIMessage(
        content=(
            f"Identified symbols: {', '.join(extracted_symbols)}"
            if extracted_symbols
            else "User is asking about the entire portfolio"
        ),
        name="portfolio_symbol_extractor",
    )
    return scope_msg, extracted_symbols


def build_symbols_context(symbols: List[str]) -> str:
    if symbols:
        return f"Focus only on these symbols: {', '.join(symbols)}"
    return "Scope: Analyze the entire portfolio (no specific symbol filter)."


def build_execution_env() -> Dict[str, object]:
    """Build the sandboxed execution namespace with all portfolio utilities pre-imported."""
    env: Dict[str, object] = {
        "__builtins__": __builtins__,
        "calculate_profit_or_loss": calculate_profit_or_loss,
        "download_prices": download_prices,
        "portfolio_volatility": portfolio_volatility,
        "max_drawdown": max_drawdown,
        "max_drawdown_asset": max_drawdown_asset,
        "growth_filter": growth_filter,
        "value_filter": value_filter,
        "roi": roi,
        "roe": roe,
        "sharpe_ratio": sharpe_ratio,
        "sortino_ratio": sortino_ratio,
        "cagr": cagr,
        "dividend_yield": dividend_yield,
        "debt_to_equity_ratio": debt_to_equity_ratio,
        "current_ratio": current_ratio,
        "profit_margin": profit_margin,
        "win_rate": win_rate,
        "portfolio_return": portfolio_return,
        "downside_deviation": downside_deviation,
        "calculate_all_metrics": calculate_all_metrics,
    }
    for func_name in YF_FUNCTION_NAMES:
        env[func_name] = getattr(yfinance_wrappers, func_name)
    return env


def financial_analysis_tool_sandbox_function_names() -> tuple[str, ...]:
    """Alphabetical names bound in the portfolio CodeAct sandbox (excludes ``__builtins__``)."""
    return _tool_registry.all_names()


def build_execution_env_from_registry() -> Dict[str, object]:
    """Build sandboxed exec namespace using the central ToolRegistry (all functions)."""
    return _tool_registry.build_exec_env()


def get_routed_function_signatures(user_request: str) -> str:
    """Route the user query to relevant categories and return only those signatures.

    This keeps the code-gen prompt lean: instead of injecting ALL 80+ function
    docs, we inject only the 15-25 most relevant ones.
    """
    categories = _tool_registry.route_query(user_request, top_k=5)
    if not categories:
        # Fallback: return everything
        return _tool_registry.get_signatures()
    return _tool_registry.get_signatures(set(categories))


def build_code_gen_invoke_args(
    messages: List[BaseMessage],
    user_request: str,
    symbol_names: List[str],
) -> dict:
    """Assemble all template variables needed by CODE_GENERATION_PROMPT.

    Uses the ToolRegistry to inject **only** the function signatures relevant
    to the user's query (via keyword routing).  The existing per-group template
    variables are preserved for backward compatibility with the current prompt
    template, but a new ``routed_function_signatures`` variable is added that
    contains the full set of relevant functions.  You can migrate the prompt
    template to use only ``routed_function_signatures`` when ready.
    """
    return {
        "messages": messages,
        "user_request": user_request,
        "portfolio_df_schema": EquityHoldingSchema.get_holdings_schema(),
        "symbols_context": build_symbols_context(symbol_names),
        "current_date_time": datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%Y-%m-%d %H:%M:%S"),
        # ── NEW: single routed block (migrate prompt to use this) ───────
        "routed_function_signatures": get_routed_function_signatures(user_request),
        # ── Legacy per-group variables (keep until prompt migration) ────
        "risk_functions_with_doc_string": get_function_with_doc_string(
            [download_prices, portfolio_volatility, max_drawdown, max_drawdown_asset]
        ),
        "yf_financial_statement_function_with_doc_string": get_function_with_doc_string(
            [get_balance_sheet, get_income_statement, get_cash_flow]
        ),
        "yf_price_and_returns_function_with_doc_string": get_function_with_doc_string(
            [
                get_last_close_prices_batch,
                get_last_close_price,
                download_prices,
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
        "profit_calculation_function_with_doc_string": get_function_with_doc_string(
            [calculate_profit_or_loss]
        ),
        "filter_functions_with_doc_string": get_function_with_doc_string(
            [growth_filter, value_filter]
        ),
        "metrics_functions_with_doc_string": get_function_with_doc_string(
            [
                roi,
                roe,
                sharpe_ratio,
                sortino_ratio,
                cagr,
                dividend_yield,
                debt_to_equity_ratio,
                current_ratio,
                profit_margin,
                win_rate,
                portfolio_return,
                downside_deviation,
                calculate_all_metrics,
            ]
        ),
        "ticker_info_function_with_doc_string": get_function_with_doc_string([get_ticker_info]),
    }
