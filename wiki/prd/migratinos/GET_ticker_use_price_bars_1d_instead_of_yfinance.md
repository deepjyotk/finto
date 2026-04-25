GET_ticker_use_price_bars_1d_instead_of_yfinance

GET /ticker/{symbol}

Now, instead of using yfinance to get the price bars, we want to use the price_bars_1d table.


Can you change the code approrpiately, also respect the existing repo for "price_bars_1d" and "in_equities" table;
inject the appropriate repo layer in the service.


Okay, but dont delete the existing yfinance code, instead keep it behind feature flag, and move it to different function.


And also, since price_bars_1d table on UI should only support: 1M, 6M, 1Y, MAX

MAX is ofcourse 2Y since we only have 2Y of data in the price_bars_1d table.

Basically, also change the UI code base appropriately, so that it supports the new price_bars_1d table.