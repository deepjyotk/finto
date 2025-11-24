
from typing import Optional
from langchain_core.tools import tool
from langchain_experimental.tools import PythonREPLTool
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
import pandas as pd
from src.repositories.holding_repo import get_portfolio_df_from_db

# Internal function that accepts context
def _extract_portfolio_data_internal(query: str, context: dict, symbols: Optional[list[str]] = None) -> str:
    """Internal function to extract portfolio data with context.
    
    Use this tool when you need to:
    - Retrieve specific holdings or attributes from the portfolio
    - Calculate aggregations (total value, sector allocation, top holdings, etc.)
    - Filter or sort portfolio holdings
    - Compute custom metrics from the portfolio data
    - Analyze portfolio composition or distribution
    
    Args:
        query: A natural language description of what portfolio data to extract.
               Examples:
               - "Get the quantity and purchase price of my holdings in Tesla"
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

    # Fetch portfolio from DB using user_id from context
    user_id = context.get("user_id")
    if not user_id:
        return "ERROR: user_id not found in context."
    try:
        df = get_portfolio_df_from_db(str(user_id))
        if df is None or df.empty:
            return f"No portfolio data found for user {user_id}."
        excel_preview = df.head().to_string()
    except Exception as e:
        return f"ERROR fetching portfolio from DB: {e}"

    # Build symbol context for the prompt
    if symbols and len(symbols) > 0:
        symbol_context = f"\n**Focus on these symbols only:** {', '.join(symbols)}"
    else:
        symbol_context = "\n**Scope:** Analyze the entire portfolio (no specific symbol filter)."

    # Create prompt for code generation
    extraction_prompt = ChatPromptTemplate.from_template(
        """You are a Python and Pandas expert helping analyze a user's stock portfolio.

            Write **only valid Python code** to answer the user's query about their portfolio.

            **Preview of first rows:**
            {excel_preview}
            {symbol_context}

            **User request:**
            {user_request}

            ### Requirements
            - Use pandas: `import pandas as pd`
            - The portfolio data is already loaded in a DataFrame called `df`
            - If specific symbols are mentioned, filter the dataframe to those symbols first
            - Base analysis strictly on the user request
            - Use appropriate operations (groupby/agg/sort/filter/etc.)
            - Print the final result with `print(...)`
            - Output ONLY executable Python code (no comments, no explanations, no markdown)"""
    )

    # Generate code
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    code_chain = extraction_prompt | llm | (lambda msg: msg.content)

    generated_code = code_chain.invoke({
        "excel_preview": excel_preview,
        "symbol_context": symbol_context,
        "user_request": query
    })

    # Execute code and return result
    # Inject df into the generated code's namespace using setattr on builtins
    import builtins
    setattr(builtins, 'df', df)
    
    python_tool = PythonREPLTool()
    try:
        result = python_tool.invoke(generated_code)
        symbol_info = f" (Filtered to: {', '.join(symbols)})" if symbols else " (Entire portfolio)"
        return f"Extracted Portfolio Data{symbol_info}:\n{result}"
    except Exception as e:
        return f"Error executing extraction code: {e}\n\nGenerated code:\n{generated_code}"
    finally:
        # Clean up the injected variable
        try:
            delattr(builtins, 'df')
        except AttributeError:
            pass

# Public tool interface without context parameter (context injected by wrapper)
@tool("extract_portfolio_data")
def extract_portfolio_data(query: str, symbols: Optional[list[str]] = None) -> str:
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
               - "Get the quantity and purchase price of my holdings in Tesla"
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
    # This is a placeholder - actual execution happens through wrapper in execute_tools.py
    # that injects the context with user_id from runtime
    return "ERROR: This tool must be called through the portfolio_tools_with_context wrapper"