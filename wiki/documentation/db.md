# Database & Schema

**Backend stack**

- Postgres on Supabase (`public` schema). ORM models live in `src/models/` and share `Base.metadata`.
- Alembic env + scripts live in `src/migrations/`. The async `env.py` reads `DATABASE_URL`, converts to `postgresql+asyncpg`, and scopes the Alembic version table to the `public` schema.

This page mirrors the **`public` schema** on the live Finto Supabase project (not every historical Alembic revision).

**RLS:** Row Level Security is enabled on almost all application tables. Exceptions called out below (`f_income_statements`, `f_balance_sheets`, `f_cash_flows` currently have RLS disabled).

---

## Identity & registration

### `f_users`

- Core identity for product users.
- Columns: `user_id` (UUID PK), `username`, `email`, `full_name`, `password_hash` (nullable), `created_at`, `updated_at`, `google_id` (nullable, unique when set), `auth_provider` (text, default `local`).
- Unique indexes: `username`, `email`, `google_id`.
- Referenced by: `whatsapp_cache`, `whatsapp_metadata`, `whatsapp_chat_sessions`, `chat_sessions`, `chat_messages`, `equity_holdings_in_metadata`, `credit_transactions`, `holding_syncs`, `f_contest_picks`.

### `pending_registrations`

- Email verification flow before a row exists in `f_users`.
- Columns: `id` (UUID PK), `email` (unique), `username`, `full_name`, `password_hash`, `otp_hash`, `expires_at`, `attempts`, `created_at`.
- Indexes: unique on `email`; btree on `email`, `expires_at`.

---

## Brokers & holdings

### `brokers`

- Supported broker integrations.
- Columns: `broker_id` (UUID PK, default `gen_random_uuid()`), `broker_name` (`broker_name_enum`: AngelOne, Zerodha, Grow), `broker_type` (`broker_type_enum`: Equity, Crypto), `country` (`country_enum`: India, US).
- Referenced by: `equity_holdings_in_metadata`.

### `equity_holdings_in_metadata`

- One row per user × broker linkage (“upload batch” / account context).
- Columns: `user_broker_id` (UUID PK), `user_id` FK → `f_users`, `broker_id` FK → `brokers`, `created_at`, `updated_at`, `uploaded_via` (`uploaded_via_enum`: user_file_upload, cron_job), optional `extra_metadata` (jsonb).
- Referenced by: `equity_holdings_in`.

### `equity_holdings_in`

- Individual holdings lines tied to a metadata row (not directly to `user_id`).
- Columns: `id` (UUID PK), `user_broker_id` FK → `equity_holdings_in_metadata`, `symbol`, `company_name`, optional `sector`, quantities (`qty_available`, `qty_long_term`, `qty_pledged_margin`), `avg_price`, `prev_close_price`.

### `holding_syncs`

- Audit-style sync summaries per user.
- Columns: `id` (UUID PK), `user_id` FK → `f_users`, `synced_count`, `updated_count`, `synced_at`.

---

## WhatsApp

### `whatsapp_cache`

- Short-lived linking / verification payloads.
- Columns: `id` (UUID PK), `user_id` FK → `f_users`, `temporary_code`, `created_at`, `expires_at`, `is_active`.
- Indexes: `temporary_code`, `created_at`, `expires_at`, `is_active`.

### `whatsapp_metadata`

- Stable mapping of platform user ↔ WhatsApp E.164.
- Columns: `id` (UUID PK), `user_id` FK → `f_users`, `user_e164` (unique).

### `whatsapp_chat_sessions`

- WhatsApp conversation sessions.
- Columns: `whatsapp_session_id` (UUID PK), `user_id` FK → `f_users`, activity/expiry timestamps, `whatsapp_is_active`, optional close metadata (`whatsapp_closed_at`, `whatsapp_closed_reason` enum: timeout, user_new_chat), `whatsapp_metadata` (jsonb).

---

## In-app chat (web)

### `chat_sessions`

- Columns: `chat_session_id` (UUID PK), `user_id` FK → `f_users`, `started_at`.
- Referenced by: `chat_messages`.

### `chat_messages`

- Columns: `id` (UUID PK), `session_id` FK → `chat_sessions`, `seq_no`, optional `user_id` FK → `f_users`, `content`, `message_type` (`chat_message_type`: User, AI), `created_at`, `edited_at`.
- Unique constraint: `(session_id, seq_no)`. Indexes include `(session_id, created_at DESC)` and `(session_id, seq_no)`.

---

## Agent checkpoints (LangGraph / Postgres saver)

### `checkpoint_migrations`

- Internal migration version integer (`v` PK).

### `checkpoints`

- Columns: composite PK `(thread_id, checkpoint_ns, checkpoint_id)`, optional parent/type, `checkpoint` + `metadata` (jsonb).

### `checkpoint_blobs`

- Composite PK `(thread_id, checkpoint_ns, channel, version)`; stores typed blobs (`bytea`).

### `checkpoint_writes`

- Composite PK `(thread_id, checkpoint_ns, checkpoint_id, task_id, idx)`; pending writes per checkpoint.

---

## Credits & billing

### `user_credits`

- Comment (DB): credits left per user.
- Columns: `user_id` (PK), `credits_left`, `created_at`, `updated_at`.

### `credit_transactions`

- Ledger of credit movements and LLM usage metadata.
- Columns: `id` (UUID PK), `user_id` FK → `f_users`, `amount`, `transaction_type`, `balance_before`, `balance_after`, optional `model_name`, `input_tokens`, `output_tokens`, `usd_cost`, `request_id`, `description`, `created_at`.
- Indexes: `user_id`, `(user_id, created_at)`, `created_at`, `request_id`.

---

## Market reference & prices

### `in_equities`

- Listed equity master data (Indian equities dataset).
- Columns: `id` (UUID PK), `symbol` (unique), `company_name`, optional listing/fundamentals fields (`series`, `date_of_listing`, `paid_up_value`, `market_lot`, `face_value`), `isin_number` (unique), `created_at`, `updated_at`, optional `company_metadata` (jsonb).
- Referenced by: `price_bars_1d`, `f_income_statements`, `f_balance_sheets`, `f_cash_flows`.

### `price_bars_1d`

- Daily OHLCV per equity.
- Composite PK `(in_equity_id, trade_date)` FK → `in_equities`; columns `open`, `high`, `low`, `close`, `volume`, `created_at`, `updated_at`.

---

## Financial statements (fundamentals)

**RLS is currently disabled** on these three tables—treat access control as application-layer or tighten RLS if exposing via Supabase Data API.

### `f_income_statements`

- PK `id` (bigint identity). FK `in_equity_id` → `in_equities`. `statement_type`, `period`, revenue/income/EPS-style numeric columns, `updated_at`.

### `f_balance_sheets`

- PK `id` (bigint identity). FK `in_equity_id` → `in_equities`. Balance sheet line items (assets, liabilities, equity, debt, etc.), `updated_at`.

### `f_cash_flows`

- PK `id` (bigint identity). FK `in_equity_id` → `in_equities`. Operating/investing/financing cash flow detail, `updated_at`.

---

## Contests

### `f_daily_contests`

- Columns: `contest_id` (UUID PK), `contest_date`, optional Nifty open/close/return, `is_settled`, `created_at`.
- Referenced by: `f_contest_picks`.

### `f_contest_picks`

- Columns: `pick_id` (UUID PK), `contest_id` FK → `f_daily_contests`, optional `user_id` FK → `f_users`, five stock symbols + optional entry prices and return breakdown, ranking fields, optional `anon_id`, `display_name`, `ip_address`, `created_at`.

---

## Migration bookkeeping

### `alembic_version`

- Single column `version_num` (varchar PK)—tracks applied Alembic revision on this database.

---

## Operational notes

- Apply migrations locally against Supabase using project conventions: `uv run alembic upgrade head` (Python 3.13+).
- Enum types in frequent use: `broker_name_enum`, `broker_type_enum`, `country_enum`, `uploaded_via_enum`, `chat_message_type`, `whatsapp_chat_session_closed_reason`.
