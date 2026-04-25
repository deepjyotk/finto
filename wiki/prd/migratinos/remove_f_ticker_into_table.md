The `f_ticker_info` table is no longer required.

We use the `in_equities` table instead, with a JSONB column **`company_metadata`** holding the same yfinance snapshot that used to live in `f_ticker_info.data`.

## Migration plan

1. **Add** `in_equities.company_metadata` (JSONB, nullable) and a GIN index for the same screener-style `data->>'...'` queries as before.
2. **Backfill** from `f_ticker_info` into `in_equities` (match on NSE `symbol`, with a fallback join on `split_part(symbol_ns, '.', 1)`).
3. **Drop** `f_ticker_info` and its indexes.
4. **Code:** `TickerInfoRepo` and `scripts/db-scripts/load_ticker_info.py` read/write `in_equities.company_metadata` instead of `f_ticker_info`.

All of the above is implemented in a **single** Alembic revision: `l7m8n9o0p1q2_move_ticker_info_into_in_equities.py` (revises `k5l6m7n8o9p0`).

After `alembic upgrade head` succeeds, use the updated loader and app code; no separate migration step is required for application changes.
