Basically, what I want is:

1. There is duplication of `symbol` and `symbol_ns` in the `f_financials_statements` table.

2. Drop both columns and instead use the corresponding `in_equities.id` column. Basically, identify a stock using the foreign key `in_equities.id`.

For above 2 points, create a single migration file. And once migration is successful using 
alebic upgrade head, make changes to the codebase appropriately (point 3 below).

3. Update the code as well:

* In the `get_ticker` service, first query the `in_equities` table to get the stock ID from the symbol.
* Then set `symbol_ns = symbol + ".NS"`.
