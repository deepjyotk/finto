So, if you closely follow the feature of @Hitl-screener.md, you will see that we are using the yfinance wrapper functions to get the data.


- If you see the run_get_screened_stocks_sync function in @screener_tool.py, you will see that we are using the yfinance wrapper functions to get the data.


- But, now since we store the data in the database, no need to use yfinance wrapper for it.


- Understand the schema for:

    - f_balance_sheets
    - f_cash_flows
    - f_income_statements
    - in_equities
    - price_bars_1d


Very closely, understand the schema, how and what data they have. How they are related to each other. Understand the relationships between the tables.


Once, done, use proper repo layer (there must be already an repo layer for these tables), and change the implementation of: run_get_screened_stocks in @screener_tool.py to use the data from the database instead of yfinance wrapper.


Write modular code, make no mistakes and follow existing coding standards of DI and SOLID principles, and DRY principles.

