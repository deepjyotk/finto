from typing import Optional

import pandas as pd
from langchain.tools import ToolRuntime, tool
from langchain_core.prompts import ChatPromptTemplate
from langchain_experimental.tools import PythonREPLTool
from langchain_openai import ChatOpenAI

from src.core.enums import LLMModel
from src.schemas.agent_state import AgentContext
from src.tools.calculate_profit_tool import calculate_profit
from src.tools.portfolio_risk import portfolio_volatility, max_drawdown, download_prices, max_drawdown_asset
from src.tools.yfinance_wrappers import (
    get_balance_sheet,
    get_income_statement,
    get_cash_flow,
    get_dividends,
    get_capital_gains,
    get_earnings,
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
    get_last_close_price,
)


@tool("extract_portfolio_data")
def extract_portfolio_data(
    runtime: ToolRuntime[AgentContext], query: str, symbols: Optional[list[str]] = None
) -> str:
    """Extract specific data from the user's portfolio using Python/Pandas code generation.

    Use this tool when you need to:
    - Retrieve specific holdings or attributes from the portfolio
    - Calculate aggregations (total value, sector allocation, top holdings, etc.)
    - Filter or sort portfolio holdings
    - Compute custom metrics from the portfolio data
    - Analyze portfolio composition or distribution

    Args:
        query: A natural language description of what portfolio data to extract.
               Examples:
               - "Get the quantity and purchase price of my holdings in Adani Green Energy"
               - "Calculate total portfolio value"
               - "Show top 5 holdings by value"
               - "Group by sector and show allocation percentage"
               - "Find holdings with unrealized loss > 10%"
        symbols: Optional list of stock symbols to filter the analysis.
                 Examples: ["RELIANCE.NS", "TCS.NS", "INFY.NS"]
                 Leave as None for portfolio-wide queries like sector analysis.

    Returns:
        Extracted portfolio data as a formatted string.
    """
    # Read and preview the portfolio file
    excel_path = "portfolio.xlsx"
    try:
        df = pd.read_excel(excel_path)
        excel_preview = df.head().to_string()
    except Exception as e:
        return f"ERROR reading portfolio file: {e}"

    # Build symbol context for the prompt
    symbol_context = ""
    if symbols and len(symbols) > 0:
        symbol_context = f"\n**Focus on these symbols only:** {', '.join(symbols)}"
    else:
        symbol_context = "\n**Scope:** Analyze the entire portfolio (no specific symbol filter)."

    # Create prompt for code generation
    extraction_prompt = ChatPromptTemplate.from_template(
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

    context = runtime.context
    portfolio_model = context.get("portfolio_model", LLMModel.GPT4p1)
    # Generate code
    llm_kwargs = {"model": portfolio_model.model_name, **portfolio_model.llm_kwargs}
    llm = ChatOpenAI(**llm_kwargs)
    code_chain = extraction_prompt | llm | (lambda msg: msg.content)

    generated_code = code_chain.invoke(
        {
            "excel_path": excel_path,
            "excel_preview": excel_preview,
            "symbol_context": symbol_context,
            "user_request": query,
        }
    )

    # Execute code and return result
    # Inject all available functions into the REPL environment
    import builtins
    
    # Profit calculation
    setattr(builtins, 'calculate_profit', calculate_profit)
    
    # Portfolio risk functions
    setattr(builtins, 'portfolio_volatility', portfolio_volatility)
    setattr(builtins, 'max_drawdown', max_drawdown)
    setattr(builtins, 'download_prices', download_prices)
    setattr(builtins, 'max_drawdown_asset', max_drawdown_asset)
    
    # YFinance data functions
    setattr(builtins, 'get_last_close_price', get_last_close_price)
    setattr(builtins, 'get_balance_sheet', get_balance_sheet)
    setattr(builtins, 'get_income_statement', get_income_statement)
    setattr(builtins, 'get_cash_flow', get_cash_flow)
    setattr(builtins, 'get_dividends', get_dividends)
    setattr(builtins, 'get_capital_gains', get_capital_gains)
    setattr(builtins, 'get_earnings', get_earnings)
    setattr(builtins, 'get_earnings_estimate', get_earnings_estimate)
    setattr(builtins, 'get_revenue_estimate', get_revenue_estimate)
    setattr(builtins, 'get_earnings_history', get_earnings_history)
    setattr(builtins, 'get_eps_trend', get_eps_trend)
    setattr(builtins, 'get_eps_revisions', get_eps_revisions)
    setattr(builtins, 'get_growth_estimates', get_growth_estimates)
    setattr(builtins, 'get_major_holders', get_major_holders)
    setattr(builtins, 'get_institutional_holders', get_institutional_holders)
    setattr(builtins, 'get_mutualfund_holders', get_mutualfund_holders)
    setattr(builtins, 'get_insider_purchases', get_insider_purchases)
    setattr(builtins, 'get_insider_transactions', get_insider_transactions)
    
    python_tool = PythonREPLTool()
    try:
        result = python_tool.invoke(generated_code)
        symbol_info = f" (Filtered to: {', '.join(symbols)})" if symbols else " (Entire portfolio)"
        return f"Extracted Portfolio Data{symbol_info}:\n{result}"
    except Exception as e:
        return f"Error executing extraction code: {e}\n\nGenerated code:\n{generated_code}"
    finally:
        # Clean up injected functions
        try:
            delattr(builtins, 'calculate_profit')
            delattr(builtins, 'portfolio_volatility')
            delattr(builtins, 'max_drawdown')
            delattr(builtins, 'download_prices')
            delattr(builtins, 'max_drawdown_asset')
            delattr(builtins, 'get_last_close_price')
            delattr(builtins, 'get_balance_sheet')
            delattr(builtins, 'get_income_statement')
            delattr(builtins, 'get_cash_flow')
            delattr(builtins, 'get_dividends')
            delattr(builtins, 'get_capital_gains')
            delattr(builtins, 'get_earnings')
            delattr(builtins, 'get_earnings_estimate')
            delattr(builtins, 'get_revenue_estimate')
            delattr(builtins, 'get_earnings_history')
            delattr(builtins, 'get_eps_trend')
            delattr(builtins, 'get_eps_revisions')
            delattr(builtins, 'get_growth_estimates')
            delattr(builtins, 'get_major_holders')
            delattr(builtins, 'get_institutional_holders')
            delattr(builtins, 'get_mutualfund_holders')
            delattr(builtins, 'get_insider_purchases')
            delattr(builtins, 'get_insider_transactions')
        except AttributeError:
            pass
