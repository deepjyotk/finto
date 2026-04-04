"""Test script for all YFinance wrapper functions."""

import pandas as pd

import json
from src.tools.yfinance_wrappers import (
    get_balance_sheet,
    get_income_statement,
    get_cash_flow,
    get_dividends,
    get_capital_gains,
    get_earnings_estimate,
    get_revenue_estimate,
    get_earnings_history,
    get_eps_trend,
    get_eps_revisions,
    get_growth_estimates,
    get_major_holders,
    get_institutional_holders,
    get_mutualfund_holders,
    get_insider_purchases,
    get_insider_transactions,
    get_ticker_price,
    get_last_close_price,
)


def print_result(function_name: str, result: dict):
    """Print test result in a formatted way."""
    print(f"\n{'=' * 80}")
    print(f"Testing: {function_name}")
    print(f"{'=' * 80}")

    # Check if there's an error
    if "error" in result or "message" in result:
        print(f"❌ Error: {result.get('error') or result.get('message')}")
    else:
        print("✅ Success")

    # Print result preview (truncated for large data)
    result_str = json.dumps(result, indent=2, default=str)
    if len(result_str) > 10000:
        print(f"Result preview (first 500 chars):\n{result_str[:500]}...")
    else:
        print(f"Result:\n{result_str}")


def test_financial_statements(symbol: str):
    """Test financial statement functions."""
    print(f"\n\n{'#' * 80}")
    print(f"# TESTING FINANCIAL STATEMENTS - {symbol}")
    print(f"{'#' * 80}")

    # Balance Sheet
    try:
        result = get_balance_sheet(symbol, freq="yearly")
        print_result("get_balance_sheet (yearly)", result)
    except Exception as e:
        print(f"❌ get_balance_sheet failed: {e}")

    try:
        result = get_balance_sheet(symbol, freq="quarterly")
        print_result("get_balance_sheet (quarterly)", result)
    except Exception as e:
        print(f"❌ get_balance_sheet (quarterly) failed: {e}")

    # Income Statement
    try:
        result = get_income_statement(symbol, freq="yearly")
        print_result("get_income_statement (yearly)", result)
    except Exception as e:
        print(f"❌ get_income_statement failed: {e}")

    # Cash Flow
    try:
        result = get_cash_flow(symbol, freq="yearly")
        print_result("get_cash_flow (yearly)", result)
    except Exception as e:
        print(f"❌ get_cash_flow failed: {e}")


def test_price_and_returns(symbol: str):
    """Test price and returns functions."""
    print(f"\n\n{'#' * 80}")
    print(f"# TESTING PRICE & RETURNS - {symbol}")
    print(f"{'#' * 80}")

    # Last Close Price
    try:
        result = get_last_close_price(symbol)
        print_result("get_last_close_price", result)
    except Exception as e:
        print(f"❌ get_last_close_price failed: {e}")

    # Ticker Price
    try:
        result = get_ticker_price(symbol, period="1mo", interval="1d")
        print_result("get_ticker_price (1mo, 1d)", result)
    except Exception as e:
        print(f"❌ get_ticker_price failed: {e}")

    # Dividends
    try:
        result = get_dividends(symbol, period="5y")
        print_result("get_dividends (5y)", result)
    except Exception as e:
        print(f"❌ get_dividends failed: {e}")

    # Capital Gains
    try:
        result = get_capital_gains(symbol, period="5y")
        print_result("get_capital_gains (5y)", result)
    except Exception as e:
        print(f"❌ get_capital_gains failed: {e}")


def test_earnings_and_estimates(symbol: str):
    """Test earnings and estimates functions."""
    print(f"\n\n{'#' * 80}")
    print(f"# TESTING EARNINGS & ESTIMATES - {symbol}")
    print(f"{'#' * 80}")

    # Earnings Estimate
    try:
        result = get_earnings_estimate(symbol)
        print_result("get_earnings_estimate", result)
    except Exception as e:
        print(f"❌ get_earnings_estimate failed: {e}")

    # Revenue Estimate
    try:
        result = get_revenue_estimate(symbol)
        print_result("get_revenue_estimate", result)
    except Exception as e:
        print(f"❌ get_revenue_estimate failed: {e}")

    # Earnings History
    try:
        result = get_earnings_history(symbol)
        print_result("get_earnings_history", result)
    except Exception as e:
        print(f"❌ get_earnings_history failed: {e}")

    # EPS Trend
    try:
        result = get_eps_trend(symbol)
        print_result("get_eps_trend", result)
    except Exception as e:
        print(f"❌ get_eps_trend failed: {e}")

    # EPS Revisions
    try:
        result = get_eps_revisions(symbol)
        print_result("get_eps_revisions", result)
    except Exception as e:
        print(f"❌ get_eps_revisions failed: {e}")

    # Growth Estimates
    try:
        result = get_growth_estimates(symbol)
        print_result("get_growth_estimates", result)
    except Exception as e:
        print(f"❌ get_growth_estimates failed: {e}")


def test_ownership_and_insider(symbol: str):
    """Test ownership and insider data functions."""
    print(f"\n\n{'#' * 80}")
    print(f"# TESTING OWNERSHIP & INSIDER DATA - {symbol}")
    print(f"{'#' * 80}")

    # Major Holders
    try:
        result = get_major_holders(symbol)
        print_result("get_major_holders", result)
    except Exception as e:
        print(f"❌ get_major_holders failed: {e}")

    # Institutional Holders
    try:
        result = get_institutional_holders(symbol)
        print_result("get_institutional_holders", result)
    except Exception as e:
        print(f"❌ get_institutional_holders failed: {e}")

    # Mutual Fund Holders
    try:
        result = get_mutualfund_holders(symbol)
        print_result("get_mutualfund_holders", result)
    except Exception as e:
        print(f"❌ get_mutualfund_holders failed: {e}")

    # Insider Purchases
    try:
        result = get_insider_purchases(symbol)
        print_result("get_insider_purchases", result)
    except Exception as e:
        print(f"❌ get_insider_purchases failed: {e}")

    # Insider Transactions
    try:
        result = get_insider_transactions(symbol)
        print_result("get_insider_transactions", result)
    except Exception as e:
        print(f"❌ get_insider_transactions failed: {e}")


if __name__ == "__main__":
    # Test with US stock
    us_symbol = "AAPL"
    print(f"\n\n{'*' * 80}")
    print(f"* STARTING TESTS FOR US STOCK: {us_symbol}")
    print(f"{'*' * 80}")

    # test_financial_statements(us_symbol)
    # test_price_and_returns(us_symbol)
    # test_earnings_and_estimates(us_symbol)
    # test_ownership_and_insider(us_symbol)

    # Test with Indian stock
    indian_symbol = "RELIANCE.NS"
    print(f"\n\n{'*' * 80}")
    print(f"* STARTING TESTS FOR INDIAN STOCK: {indian_symbol}")
    print(f"{'*' * 80}")

    # test_financial_statements(indian_symbol)
    # test_price_and_returns(indian_symbol)
    # test_earnings_and_estimates(indian_symbol)
    # test_ownership_and_insider(indian_symbol)

    symbols = ["USHAMART.NS", "RELIANCE.NS"]
    results = {}
    for symbol in symbols:
        try:
            income_data = get_income_statement(symbol, freq="yearly")
            if "income_statement" not in income_data or not income_data["income_statement"]:
                print(f"Warning: No income statement data found for {symbol}. Skipping.")
                continue
            print(f"Income DataFrame for {symbol}:\n{income_data}")
            income_df = pd.DataFrame(income_data["income_statement"]).T

            income_df.index = pd.to_datetime(income_df.index)
            income_df = income_df.sort_index()

            if "NetIncome" not in income_df.columns:
                print(f"Warning: NetIncome column missing for {symbol}. Skipping.")
                continue
            net_income_series = income_df["NetIncome"].astype(float)
            results[symbol] = net_income_series
        except Exception as e:
            print(f"Warning: Failed to fetch or process NetIncome for {symbol}: {e}")
    print(f"\nNet Income Results:\n{results}")
    print(f"\n\n{'*' * 80}")
    print("* ALL TESTS COMPLETED")
    print(f"{'*' * 80}\n")
