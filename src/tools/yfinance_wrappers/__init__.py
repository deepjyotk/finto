"""Simple YFinance wrapper functions for use in generated Python code.

These functions mirror the langchain tools but are plain Python functions
that can be called directly in generated code without the langchain tool wrapper.
"""

from typing import Optional

import yfinance as yf

from src.tools.common_utils import normalize_symbol


def get_balance_sheet(symbol_name: str, freq: str = "yearly", pretty: bool = False) -> dict:
    """Fetch balance sheet (yearly or quarterly) with important fields only.

    Args:
        symbol_name: Stock ticker symbol (e.g., "AAPL", "RELIANCE")
        freq: "yearly" or "quarterly"
        pretty: If True, format column names nicely

    Returns:
        {"symbol": t, "balance_sheet": {...}} with filtered important fields:
        TotalAssets, CurrentAssets, CashAndCashEquivalents, AccountsReceivable,
        Inventory, NetPPE, TotalNonCurrentAssets, Goodwill, TotalLiabilitiesNetMinorityInterest,
        CurrentLiabilities, CurrentDebt, AccountsPayable, LongTermDebt, TotalDebt,
        StockholdersEquity, CommonStockEquity, RetainedEarnings, WorkingCapital, NetDebt
    """
    try:
        if not symbol_name:
            print(f"ERROR: Symbol {symbol_name} is empty or None")
            raise ValueError("Symbol name is required.")
        normalized_symbol = normalize_symbol(symbol_name.strip().upper())
        data = yf.Ticker(normalized_symbol).get_balance_sheet(
            as_dict=True, pretty=pretty, freq=freq
        )

        # Important fields to keep
        important_fields = {
            "TotalAssets",
            "CurrentAssets",
            "CashAndCashEquivalents",
            "AccountsReceivable",
            "Inventory",
            "NetPPE",
            "TotalNonCurrentAssets",
            "Goodwill",
            "TotalLiabilitiesNetMinorityInterest",
            "CurrentLiabilities",
            "CurrentDebt",
            "AccountsPayable",
            "LongTermDebt",
            "TotalDebt",
            "StockholdersEquity",
            "CommonStockEquity",
            "RetainedEarnings",
            "WorkingCapital",
            "NetDebt",
        }

        # Convert Timestamp keys to strings and filter fields
        if isinstance(data, dict):
            balance_sheet = {}
            for date_key, fields in data.items():
                filtered_fields = {
                    field: value for field, value in fields.items() if field in important_fields
                }
                balance_sheet[str(date_key)] = filtered_fields
        else:
            balance_sheet = data

        return {"symbol": symbol_name, "balance_sheet": balance_sheet}
    except Exception as e:
        print(f"ERROR: Failed to fetch balance sheet for symbol: {symbol_name} - {e}")
        return {"symbol": symbol_name, "balance_sheet": {}, "error": str(e)}


def get_income_statement(symbol_name: str, freq: str = "yearly", pretty: bool = False) -> dict:
    """Fetch income statement (yearly or quarterly) with important fields only.

    Args:
        symbol_name: Stock ticker symbol
        freq: "yearly" or "quarterly"
        pretty: If True, format column names nicely

    Returns:
        {"symbol": t, "income_statement": {...}} with filtered important fields:
        TotalRevenue, CostOfRevenue, GrossProfit, OperatingExpense, OperatingIncome,
        EBITDA, InterestExpense, TaxProvision, NetIncome, BasicEPS, DilutedEPS
    """
    try:
        if not symbol_name:
            print(f"ERROR: Symbol {symbol_name} is empty or None")
            raise ValueError("Symbol name is required.")
        normalized_symbol = normalize_symbol(symbol_name.strip().upper())
        data = yf.Ticker(normalized_symbol).get_income_stmt(as_dict=True, pretty=pretty, freq=freq)

        # Important fields to keep
        important_fields = {
            "TotalRevenue",
            "CostOfRevenue",
            "GrossProfit",
            "OperatingExpense",
            "OperatingIncome",
            "EBITDA",
            "InterestExpense",
            "TaxProvision",
            "NetIncome",
            "BasicEPS",
            "DilutedEPS",
        }

        # Convert Timestamp keys to strings and filter fields
        if isinstance(data, dict):
            income_statement = {}
            for date_key, fields in data.items():
                filtered_fields = {
                    field: value for field, value in fields.items() if field in important_fields
                }
                income_statement[str(date_key)] = filtered_fields
        else:
            income_statement = data

        return {"symbol": symbol_name, "income_statement": income_statement}
    except Exception as e:
        print(f"ERROR: Failed to fetch income statement for symbol: {symbol_name} - {e}")
        return {"symbol": symbol_name, "income_statement": {}, "error": str(e)}


def get_cash_flow(symbol_name: str, freq: str = "yearly", pretty: bool = False) -> dict:
    """Fetch cash flow statement (yearly or quarterly) with important fields only.

    Args:
        symbol_name: Stock ticker symbol
        freq: "yearly" or "quarterly"
        pretty: If True, format column names nicely

    Returns:
        {"symbol": t, "cash_flow": {...}} with filtered important fields:
        Operating: OperatingCashFlow, NetIncomeFromContinuingOperations, DepreciationAndAmortization,
        ChangeInWorkingCapital, ChangeInReceivables, ChangeInInventory, ChangeInPayable
        Investing: InvestingCashFlow, CapitalExpenditure, PurchaseOfPPE, SaleOfPPE, PurchaseOfInvestment, SaleOfInvestment
        Financing: FinancingCashFlow, NetIssuancePaymentsOfDebt, LongTermDebtIssuance, LongTermDebtPayments, CommonStockIssuance, CashDividendsPaid
        Summary: FreeCashFlow, ChangesInCash, EndCashPosition
    """
    try:
        if not symbol_name:
            print(f"ERROR: Symbol {symbol_name} is empty or None")
            raise ValueError("Symbol name is required.")

        normalized_symbol = normalize_symbol(symbol_name.strip().upper())
        data = yf.Ticker(normalized_symbol).get_cashflow(as_dict=True, pretty=pretty, freq=freq)

        # Important fields to keep
        important_fields = {
            # Operating Cash Flow
            "OperatingCashFlow",
            "NetIncomeFromContinuingOperations",
            "DepreciationAndAmortization",
            "ChangeInWorkingCapital",
            "ChangeInReceivables",
            "ChangeInInventory",
            "ChangeInPayable",
            # Investing Cash Flow
            "InvestingCashFlow",
            "CapitalExpenditure",
            "CapitalExpenditureReported",
            "PurchaseOfPPE",
            "SaleOfPPE",
            "PurchaseOfInvestment",
            "SaleOfInvestment",
            # Financing Cash Flow
            "FinancingCashFlow",
            "NetIssuancePaymentsOfDebt",
            "LongTermDebtIssuance",
            "LongTermDebtPayments",
            "CommonStockIssuance",
            "CashDividendsPaid",
            # Summary
            "FreeCashFlow",
            "ChangesInCash",
            "EndCashPosition",
        }

        # Convert Timestamp keys to strings and filter fields
        if isinstance(data, dict):
            cash_flow = {}
            for date_key, fields in data.items():
                filtered_fields = {
                    field: value for field, value in fields.items() if field in important_fields
                }
                cash_flow[str(date_key)] = filtered_fields
        else:
            cash_flow = data

        return {"symbol": symbol_name, "cash_flow": cash_flow}

    except Exception as e:
        print(f"ERROR: Failed to fetch cash flow for symbol: {symbol_name} - {e}")
        return {"symbol": symbol_name, "cash_flow": {}, "error": str(e)}


def get_dividends(symbol_name: str, period: str = "max") -> dict:
    """Fetch dividend payment history.

    Args:
        symbol_name: Stock ticker symbol
        period: Period to fetch (e.g., "1y", "5y", "max")

    Returns:
        {"symbol": t, "dividends": {...}} with clean date format (YYYY-MM-DD)
    """
    try:
        if not symbol_name:
            raise ValueError("Symbol name is required.")
        normalized_symbol = normalize_symbol(symbol_name.strip().upper())
        series = yf.Ticker(normalized_symbol).get_dividends(period=period)
        # Convert Series to dict: {date: value} with clean date format
        if hasattr(series, "to_dict"):
            div_dict = {}
            for k, v in series.to_dict().items():
                try:
                    # Try to format as YYYY-MM-DD
                    date_str = k.strftime("%Y-%m-%d")
                except (AttributeError, TypeError):
                    # Fallback if k is already a string
                    date_str = str(k).split(" ")[0]  # Extract just the date part
                div_dict[date_str] = float(v)
        else:
            div_dict = {}
        return {"symbol": symbol_name, "dividends": div_dict}
    except Exception as e:
        print(f"ERROR: Failed to fetch dividends for symbol: {symbol_name} - {e}")
        return {"symbol": symbol_name, "dividends": {}, "error": str(e)}


def get_capital_gains(symbol_name: str, period: str = "max") -> dict:
    """Fetch capital gains history.

    Args:
        symbol_name: Stock ticker symbol
        period: Period to fetch (e.g., "1y", "5y", "max")

    Returns:
        {"symbol": t, "capital_gains": {...}} with clean date format (YYYY-MM-DD)
    """
    try:
        if not symbol_name:
            print(f"ERROR: Symbol {symbol_name} is empty or None")
            raise ValueError("Symbol name is required.")
        normalized_symbol = normalize_symbol(symbol_name.strip().upper())
        series = yf.Ticker(normalized_symbol).get_capital_gains(period=period)
        # Convert Series to dict: {date: value} with clean date format
        if hasattr(series, "to_dict"):
            cg_dict = {}
            for k, v in series.to_dict().items():
                try:
                    # Try to format as YYYY-MM-DD
                    date_str = k.strftime("%Y-%m-%d")
                except (AttributeError, TypeError):
                    # Fallback if k is already a string
                    date_str = str(k).split(" ")[0]  # Extract just the date part
                cg_dict[date_str] = float(v)
        else:
            cg_dict = {}
        return {"symbol": symbol_name, "capital_gains": cg_dict}
    except Exception as e:
        print(f"ERROR: Failed to fetch capital gains for symbol: {symbol_name} - {e}")
        return {"symbol": symbol_name, "capital_gains": {}, "error": str(e)}


def get_earnings_estimate(symbol_name: str) -> dict:
    """Fetch earnings estimates.

    Args:
        symbol_name: Stock ticker symbol

    Returns:
        {"symbol": t, "earnings_estimate": {...}} with columns: avg, low, high, yearAgoEps, numberOfAnalysts, growth
    """
    try:
        if not symbol_name:
            print(f"ERROR: Symbol {symbol_name} is empty or None")
            raise ValueError("Symbol name is required.")
        normalized_symbol = normalize_symbol(symbol_name.strip().upper())
        data = yf.Ticker(normalized_symbol).get_earnings_estimate(as_dict=True)
        return {
            "symbol": symbol_name,
            "earnings_estimate": data if data is not None else {},
        }
    except Exception as e:
        print(f"ERROR: Failed to fetch earnings estimate for symbol: {symbol_name} - {e}")
        return {"symbol": symbol_name, "earnings_estimate": {}, "error": str(e)}


def get_revenue_estimate(symbol_name: str) -> dict:
    """Fetch revenue estimates.

    Args:
        symbol_name: Stock ticker symbol

    Returns:
        {"symbol": t, "revenue_estimate": {...}}
    """
    try:
        if not symbol_name:
            print(f"ERROR: Symbol {symbol_name} is empty or None")
            raise ValueError("Symbol name is required.")
        normalized_symbol = normalize_symbol(symbol_name.strip().upper())
        data = yf.Ticker(normalized_symbol).get_revenue_estimate()
        return {
            "symbol": symbol_name,
            "revenue_estimate": data if data is not None else {},
        }
    except Exception as e:
        print(f"ERROR: Failed to fetch revenue estimate for symbol: {symbol_name} - {e}")
        return {"symbol": symbol_name, "revenue_estimate": {}, "error": str(e)}


def get_earnings_history(symbol_name: str) -> dict:
    """Fetch earnings history.

    Args:
        symbol_name: Stock ticker symbol

    Returns:
        {"symbol": t, "earnings_history": {...}} with columns: epsActual, epsEstimate, epsDifference, surprisePercent
    """
    try:
        if not symbol_name:
            print(f"ERROR: Symbol {symbol_name} is empty or None")
            raise ValueError("Symbol name is required.")

        normalized_symbol = normalize_symbol(symbol_name.strip().upper())
        data = yf.Ticker(normalized_symbol).get_earnings_history(as_dict=True)

        # Convert Timestamp keys to strings in nested dictionaries
        if isinstance(data, dict):
            history_dict = {}
            for metric, dates_dict in data.items():
                if isinstance(dates_dict, dict):
                    history_dict[metric] = {str(k): v for k, v in dates_dict.items()}
                else:
                    history_dict[metric] = dates_dict
        else:
            history_dict = data if data is not None else {}

        return {"symbol": symbol_name, "earnings_history": history_dict}
    except Exception as e:
        print(f"ERROR: Failed to fetch earnings history for symbol: {symbol_name} - {e}")
        return {"symbol": symbol_name, "earnings_history": {}, "error": str(e)}


def get_eps_trend(symbol_name: str) -> dict:
    """Fetch EPS trend data.

    Args:
        symbol_name: Stock ticker symbol

    Returns:
        {"symbol": t, "eps_trend": {...}} with columns: current, 7daysAgo, 30daysAgo, 60daysAgo, 90daysAgo
    """
    try:
        if not symbol_name:
            print(f"ERROR: Symbol {symbol_name} is empty or None")
            raise ValueError("Symbol name is required.")
        normalized_symbol = normalize_symbol(symbol_name.strip().upper())
        data = yf.Ticker(normalized_symbol).get_eps_trend(as_dict=True)

        # Convert Timestamp keys to strings if needed
        if isinstance(data, dict):
            eps_dict = {str(k): v for k, v in data.items()}
        else:
            eps_dict = data if data is not None else {}

        return {"symbol": symbol_name, "eps_trend": eps_dict}
    except Exception as e:
        print(f"ERROR: Failed to fetch EPS trend for symbol: {symbol_name} - {e}")
        return {"symbol": symbol_name, "eps_trend": {}, "error": str(e)}


def get_eps_revisions(symbol_name: str) -> dict:
    """Fetch EPS revisions data.

    Args:
        symbol_name: Stock ticker symbol

    Returns:
        {"symbol": t, "eps_revisions": {...}}
    """
    try:
        if not symbol_name:
            print(f"ERROR: Symbol {symbol_name} is empty or None")
            raise ValueError("Symbol name is required.")
        normalized_symbol = normalize_symbol(symbol_name.strip().upper())
        data = yf.Ticker(normalized_symbol).get_eps_revisions(as_dict=True)
        return {
            "symbol": symbol_name,
            "eps_revisions": data if data is not None else {},
        }
    except Exception as e:
        print(f"ERROR: Failed to fetch EPS revisions for symbol: {symbol_name} - {e}")
        return {"symbol": symbol_name, "eps_revisions": {}, "error": str(e)}


def get_growth_estimates(symbol_name: str) -> dict:
    """Fetch growth estimates.

    Args:
        symbol_name: Stock ticker symbol

    Returns:
        {"symbol": t, "growth_estimates": {...}} with columns: stockTrend, indexTrend
    """
    try:
        if not symbol_name:
            print(f"ERROR: Symbol {symbol_name} is empty or None")
            raise ValueError("Symbol name is required.")
        normalized_symbol = normalize_symbol(symbol_name.strip().upper())
        data = yf.Ticker(normalized_symbol).get_growth_estimates(as_dict=True)

        # Convert NaN values to None for JSON serialization
        if isinstance(data, dict):
            growth_dict = {}
            for trend_key, trend_data in data.items():
                if isinstance(trend_data, dict):
                    growth_dict[trend_key] = {
                        k: (None if (isinstance(v, float) and v != v) else v)
                        for k, v in trend_data.items()
                    }
                else:
                    growth_dict[trend_key] = trend_data
        else:
            growth_dict = data if data is not None else {}

        return {"symbol": symbol_name, "growth_estimates": growth_dict}
    except Exception as e:
        print(f"ERROR: Failed to fetch growth estimates for symbol: {symbol_name} - {e}")
        return {"symbol": symbol_name, "growth_estimates": {}, "error": str(e)}


def get_major_holders(symbol_name: str) -> dict:
    """Fetch major holders information.

    Args:
        symbol_name: Stock ticker symbol

    Returns:
        {"symbol": t, "major_holders": {...}}
    """
    try:
        if not symbol_name:
            print(f"ERROR: Symbol {symbol_name} is empty or None")
            raise ValueError("Symbol name is required.")
        normalized_symbol = normalize_symbol(symbol_name.strip().upper())
        data = yf.Ticker(normalized_symbol).get_major_holders(as_dict=True)
        return {
            "symbol": symbol_name,
            "major_holders": data if data is not None else {},
        }
    except Exception as e:
        print(f"ERROR: Failed to fetch major holders for symbol: {symbol_name} - {e}")
        return {"symbol": symbol_name, "major_holders": {}, "error": str(e)}


def get_institutional_holders(symbol_name: str) -> dict:
    """Fetch institutional holders information.

    Args:
        symbol_name: Stock ticker symbol

    Returns:
        {"symbol": t, "institutional_holders": {...}}
    """
    try:
        if not symbol_name:
            print(f"ERROR: Symbol {symbol_name} is empty or None")
            raise ValueError("Symbol name is required.")
        normalized_symbol = normalize_symbol(symbol_name.strip().upper())
        data = yf.Ticker(normalized_symbol).get_institutional_holders(as_dict=True)
        return {
            "symbol": symbol_name,
            "institutional_holders": data if data is not None else {},
        }
    except Exception as e:
        print(f"ERROR: Failed to fetch institutional holders for symbol: {symbol_name} - {e}")
        return {"symbol": symbol_name, "institutional_holders": {}, "error": str(e)}


def get_mutualfund_holders(symbol_name: str) -> dict:
    """Fetch mutual fund holders information.

    Args:
        symbol_name: Stock ticker symbol

    Returns:
        {"symbol": t, "mutualfund_holders": {...}}
    """
    try:
        if not symbol_name:
            print(f"ERROR: Symbol {symbol_name} is empty or None")
            raise ValueError("Symbol name is required.")
        normalized_symbol = normalize_symbol(symbol_name.strip().upper())
        data = yf.Ticker(normalized_symbol).get_mutualfund_holders(as_dict=True)
        return {
            "symbol": symbol_name,
            "mutualfund_holders": data if data is not None else {},
        }
    except Exception as e:
        print(f"ERROR: Failed to fetch mutual fund holders for symbol: {symbol_name} - {e}")
        return {"symbol": symbol_name, "mutualfund_holders": {}, "error": str(e)}


def get_insider_purchases(symbol_name: str) -> dict:
    """Fetch insider purchase transactions.

    Args:
        symbol_name: Stock ticker symbol

    Returns:
        {"symbol": t, "insider_purchases": {...}}
    """
    try:
        if not symbol_name:
            print(f"ERROR: Symbol {symbol_name} is empty or None")
            raise ValueError("Symbol name is required.")
        normalized_symbol = normalize_symbol(symbol_name.strip().upper())
        data = yf.Ticker(normalized_symbol).get_insider_purchases(as_dict=True)
        return {
            "symbol": symbol_name,
            "insider_purchases": data if data is not None else {},
        }
    except Exception as e:
        print(f"ERROR: Failed to fetch insider purchases for symbol: {symbol_name} - {e}")
        return {"symbol": symbol_name, "insider_purchases": {}, "error": str(e)}


def get_insider_transactions(symbol_name: str) -> dict:
    """Fetch all insider transactions.

    Args:
        symbol_name: Stock ticker symbol

    Returns:
        {"symbol": t, "insider_transactions": {...}}
    """
    try:
        if not symbol_name:
            print(f"ERROR: Symbol {symbol_name} is empty or None")
            raise ValueError("Symbol name is required.")
        normalized_symbol = normalize_symbol(symbol_name.strip().upper())
        data = yf.Ticker(normalized_symbol).get_insider_transactions(as_dict=True)
        return {
            "symbol": symbol_name,
            "insider_transactions": data if data is not None else {},
        }
    except Exception as e:
        print(f"ERROR: Failed to fetch insider transactions for symbol: {symbol_name} - {e}")
        return {"symbol": symbol_name, "insider_transactions": {}, "error": str(e)}


def get_ticker_price(
    symbol_name: str,
    period: str = "1d",
    interval: str = "1d",
    adjust_mode: str = "auto",
    prepost: bool = False,
    repair: bool = False,
    timeout: Optional[float] = 10.0,
) -> dict:
    """Fetch historical price data for a ticker.

    Args:
        symbol_name: Stock ticker symbol (e.g., "RELIANCE", "AAPL")
        period: Period to fetch (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max) (default: 1d)
        interval: Data interval (1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h, 1d, 5d, 1wk, 1mo, 3mo) (default: 1d)
        adjust_mode: "auto", "back", or "none" for price adjustment (default: auto)
        prepost: Include pre/post market data (default: False)
        repair: Attempt to fix data errors (default: False)
        timeout: Request timeout in seconds (default: 10.0)

    Returns:
        {"symbol": symbol_name, "prices": {...}, "period": period, "interval": interval}
    """

    if not symbol_name:
        print(f"ERROR: Symbol {symbol_name} is empty or None")
        raise ValueError("Symbol name is required.")
    normalized_symbol = normalize_symbol(symbol_name.strip().upper())
    # Map adjust_mode to yfinance parameters
    auto_adjust = adjust_mode == "auto"
    back_adjust = adjust_mode == "back"

    try:
        hist = yf.Ticker(normalized_symbol).history(
            period=period,
            interval=interval,
            auto_adjust=auto_adjust,
            back_adjust=back_adjust,
            prepost=prepost,
            repair=repair,
            timeout=timeout,
        )

        if hist.empty:
            return {"symbol": symbol_name, "prices": {}, "message": "No data available"}

        # Convert to dict mapping date -> close price
        price_dict = {}
        for idx, row in hist.iterrows():
            # idx is the date index, convert to string
            try:
                date_str = idx.strftime("%Y-%m-%d")  # type: ignore
            except AttributeError:
                date_str = str(idx)
            price_dict[date_str] = float(row["Close"])

        return {
            "symbol": symbol_name,
            "prices": price_dict,
            "period": period,
            "interval": interval,
        }
    except Exception as e:
        print(f"ERROR: Failed to fetch ticker price for symbol: {symbol_name} - {e}")
        return {"symbol": symbol_name, "prices": {}, "message": str(e)}


def get_last_close_price(symbol_name: str) -> dict:
    """Fetch the most recent close price for a ticker.

    Args:
        symbol_name: Stock ticker symbol (e.g., "AAPL", "RELIANCE")

    Returns:
        {"symbol": symbol_name, "last_close_price": last_close_price, "date": date}
    """
    if not symbol_name:
        print(f"ERROR: Symbol {symbol_name} is empty or None")
        raise ValueError("Symbol name is required.")

    normalized_symbol = normalize_symbol(symbol_name.strip().upper())
    try:
        ticker = yf.Ticker(normalized_symbol)
        # Get last 5 days to ensure we have data
        hist = ticker.history(period="5d")

        if hist.empty:
            return {
                "symbol": symbol_name,
                "last_close_price": None,
                "date": None,
                "error": "No price data available",
            }

        # Get the last row
        last_date = hist.index[-1]
        last_close = float(hist["Close"].iloc[-1])
        try:
            date_str = last_date.strftime("%Y-%m-%d")  # type: ignore
        except AttributeError:
            date_str = str(last_date)

        return {"symbol": symbol_name, "last_close_price": last_close, "date": date_str}
    except Exception as e:
        print(f"ERROR: Failed to fetch last close price for symbol: {symbol_name} - {e}")
        return {
            "symbol": symbol_name,
            "last_close_price": None,
            "date": None,
            "error": str(e),
        }


def get_ticker_info(symbol: str) -> dict:
    """Fetch comprehensive ticker information with 24+ stable metrics.

    Returns key financial metrics for valuation, growth, profitability, financial health, dividends, and price.

    Args:
        symbol: Stock ticker symbol (e.g., "AAPL", "RELIANCE.NS")

    Returns:
        {"symbol": t, "marketCap": ..., "trailingPE": ..., ...} containing:

        Valuation metrics:
        - trailingPE, forwardPE, priceToBook, priceToSalesTrailing12Months, enterpriseValue, marketCap

        Growth metrics:
        - revenueGrowth, earningsGrowth, earningsQuarterlyGrowth

        Profitability metrics:
        - profitMargins, grossMargins, operatingMargins, returnOnEquity, returnOnAssets

        Financial Health metrics:
        - debtToEquity, currentRatio, quickRatio, totalDebt, totalCash

        Dividend metrics:
        - dividendYield, payoutRatio, dividendRate

        Price metrics:
        - currentPrice, fiftyTwoWeekHigh, fiftyTwoWeekLow

    Example:
        info = get_ticker_info("AAPL")
        market_cap = info.get("marketCap")
        pe = info.get("trailingPE")
        revenue_growth = info.get("revenueGrowth")
    """
    if not symbol:
        raise ValueError("Symbol is required")

    # Allowed and stable keys only
    allowed_keys = {
        # Valuation
        "trailingPE",
        "forwardPE",
        "priceToBook",
        "priceToSalesTrailing12Months",
        "enterpriseValue",
        "marketCap",
        # Growth
        "revenueGrowth",
        "earningsGrowth",
        "earningsQuarterlyGrowth",
        # Profitability
        "profitMargins",
        "grossMargins",
        "operatingMargins",
        "returnOnEquity",
        "returnOnAssets",
        # Financial Health
        "debtToEquity",
        "currentRatio",
        "quickRatio",
        "totalDebt",
        "totalCash",
        # Dividends
        "dividendYield",
        "payoutRatio",
        "dividendRate",
        # Price Stats
        "currentPrice",
        "fiftyTwoWeekHigh",
        "fiftyTwoWeekLow",
    }

    try:
        normalized_symbol = normalize_symbol(symbol.strip().upper())
        ticker = yf.Ticker(normalized_symbol)
        info = ticker.info

        # Filter to only allowed keys and include symbol
        result = {"symbol": symbol}
        if isinstance(info, dict):
            filtered_info = {k: v for k, v in info.items() if k in allowed_keys}
            result.update(filtered_info)

        return result
    except Exception as e:
        print(f"ERROR: Failed to fetch ticker info for {symbol}: {str(e)}")
        return {"symbol": symbol, "error": str(e)}
