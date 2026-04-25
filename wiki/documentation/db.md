# Database & Schema

**Backend stack**  
- ORM models live in `src/models/` and share `Base.metadata`.  
- Alembic env + scripts live in `src/migrations/`. The async `env.py` reads `DATABASE_URL`, converts to `postgresql+asyncpg`, and scopes the Alembic version table to the `public` schema (Supabase friendly).  

## Tables

### `f_users`
- Core identity table for every product user.
- Columns: `user_id` (UUID PK), `username`, `email`, `full_name`, `password_hash`, `created_at`, `updated_at`.
- Indexes: unique b-tree on `username` and `email`.
- Referenced by: `equity_holdings_in.user_id`, `whatsapp_cache.user_id`, `whatsapp_metadata.user_id`.

### `brokers`
- Catalog of supported broker integrations.
- Columns: `broker_id` (UUID PK), `broker_name`, `broker_type`, `country`.
- Enum domains (`broker_name_enum`, `broker_type_enum`, `country_enum`) constrain values to: AngelOne/Zerodha/Grow, Equity/Crypto, India/US.
- Referenced by: `equity_holdings_in.broker_id`.

### `equity_holdings_in`
- Stores per-user holdings fetched from Indian broker statements.
- Columns: `id` (UUID PK), `user_id` FK, `broker_id` FK, `symbol`, `isin`, optional `sector`.
- Position metrics: `qty_available`, `qty_discrepant`, `qty_long_term`, `qty_pledged_margin`, `qty_pledged_loan`.
- Valuation metrics: `avg_price`, `prev_close_price`, `unrealized_pnl`, `unrealized_pnl_pct`.
- Auditing: `created_at`, `updated_at`.

### `whatsapp_cache`
- Short-lived verification tokens while linking WhatsApp sessions.
- Columns: `id` (UUID PK), `user_id` FK, `temporary_code`, `created_at`.
- Indexes: b-tree on `temporary_code` and `created_at` for fast lookups + expiry sweeps.

### `whatsapp_metadata`
- Permanent mapping of a user to their WhatsApp phone number.
- Columns: `id` (UUID PK), `user_id` FK, `user_e164` (unique, indexed).
- Ensures one WhatsApp E.164 number belongs to exactly one platform user.

## Alembic Lineage
Revisions are linear—newest at the bottom:
1. `6ea001377ab4` (baseline from SQLAlchemy models) — normalizes `f_users` constraints/indexes.  
2. `c30d1e5afb86` — adds enum domains + `brokers`.  
3. `00feae39281d` — creates `equity_holdings_in` with FK links to `f_users` and `brokers`.  
4. `baabf7e08baf` — adds `whatsapp_cache` plus supporting indexes.  
5. `26e16c887acd` — adds `whatsapp_metadata` with uniqueness + indexes on phone numbers.

Use `uv run alembic upgrade head` (Python 3.13+, per project standards) to recreate the schema from scratch.
