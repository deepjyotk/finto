# PRD: Daily stock price bars (`price_bars_1d`)

**Status:** Draft  
**Last updated:** 24 April 2026  
**Owner:** Finto / Data  

## 1. Summary

Introduce a first-class **daily OHLCV** store (`price_bars_1d`) keyed by **`in_equities.id`** (no denormalized symbol on the bar row). Populate **~2 years** of history via a one-off backfill (`period=2y`, `interval=1d`), then keep the table current with a **scheduled job** after Indian market hours.

## 2. Goals

- Persist **one row per (equity, trading day)** with open, high, low, close, volume.
- Align with **industry practice**: store **only trading days** (no synthetic weekend rows).
- Reuse canonical equity identity from **`in_equities`** via **`in_equity_id` FK**.
- Operate reliably at startup scale: simple Postgres on **Supabase**, no separate time-series DB.

## 3. Non-goals (v1)

- Intraday bars (`1m`, `5m`, …) — out of scope; may be a later PRD.
- Real-time ticks — out of scope.
- Non-NSE symbols — v1 assumes Yahoo `.NS` mapping consistent with existing ticker flows.

## 4. Data model

### 4.1 Table: `price_bars_1d`

| Column         | Type        | Notes |
|----------------|-------------|--------|
| `in_equity_id` | UUID        | FK → `in_equities.id`, part of PK |
| `trade_date`   | DATE        | Session date in Yahoo daily series, part of PK |
| `open`         | NUMERIC(18,6) | Nullable if source omits |
| `high`         | NUMERIC(18,6) | |
| `low`          | NUMERIC(18,6) | |
| `close`        | NUMERIC(18,6) | |
| `volume`       | BIGINT      | Nullable |
| `created_at`   | TIMESTAMPTZ | Default `now()` |
| `updated_at`   | TIMESTAMPTZ | Default `now()`, updated on upsert |

- **Primary key:** `(in_equity_id, trade_date)`.
- **FK:** `in_equity_id` → `in_equities.id` with **`ON DELETE RESTRICT`** (avoid silent loss of history if a row were removed).
- **Index:** `trade_date` (optional range scans / housekeeping).

**Why no `symbol` column:** `in_equities` is the source of truth for symbol strings; bars reference identity by id only.

### 4.2 Trading days only

Yahoo Finance **daily** history returns **only dates with a session bar** (weekends and typical holidays absent). The ingestion layer **does not fabricate** rows for non-trading dates. This matches how Bloomberg-style daily series and most quant DBs consume exchange calendars at the daily granularity.

## 5. Data source

- **Provider:** Yahoo Finance via **`yfinance`** (same family as existing ticker chart code).
- **Symbol mapping:** `SYMBOL` → `SYMBOL.NS` for NSE-listed names in `in_equities`.
- **Backfill call shape:** `Ticker(...).history(period="2y", interval="1d", auto_adjust=True)`.
- **Operational note:** Respect gentle pacing between symbols (configurable delay) to reduce rate-limit risk.

## 6. Deliverables

### 6.1 Schema migration (Alembic)

- Revision: `k5l6m7n8o9p0_add_price_bars_1d` (depends on current head).
- Creates `price_bars_1d` as above.

**Apply:**

```bash
cd finto && uv run alembic upgrade head
```

### 6.2 One-off backfill script

- **Path:** `src/cron-jobs/price-bars-1d/past_data_update_price_bars_1d.py`
- **Behaviour:** For each row in `in_equities`, fetch `2y` daily history, upsert all returned trading days.
- **CLI:** `--period` (default `2y`), `--limit N` (smoke test), `--delay` (seconds between symbols).

**Run:**

```bash
cd finto && uv run python src/cron-jobs/price-bars-1d/past_data_update_price_bars_1d.py
```

### 6.3 Daily incremental script

- **Path:** `src/cron-jobs/price-bars-1d/daily_price_bars_1d_cron.py`
- **Behaviour:** Re-fetch a **short rolling window** (default `14d` of daily bars) per symbol and **upsert** — idempotent across weekends, holidays, and missed runs.
- **CLI:** `--period`, `--limit`, `--delay`.

**Run:**

```bash
cd finto && uv run python src/cron-jobs/price-bars-1d/daily_price_bars_1d_cron.py
```

### 6.4 Shared implementation

- **`src/cron-jobs/price-bars-1d/services/price_bars_1d_ingest.py`** — yfinance fetch + batched PostgreSQL upsert.
- **`src/models/price_bar_1d.py`** — SQLAlchemy model for type-safe upserts.

## 7. Scheduling (GCP)

**Product choice:** **Google Cloud Scheduler** (managed cron) hitting a **Cloud Run** target after the cash session.

- **Cadence:** Weekdays **16:00 Asia/Kolkata (IST)** — after NSE cash close (~15:30 IST), allowing vendor bar finalization.
- **Cron expression (Scheduler, IST timezone on the job):**  
  `0 16 * * 1-5`  
  (minute=0, hour=16, Mon–Fri; set job timezone to `Asia/Kolkata`.)
- **Target options:**
  1. **HTTPS** → secured FastAPI route (service auth / secret header) that runs the same upsert logic; or  
  2. **Cloud Run Job** invoked on a schedule; or  
  3. **Compute** VM cron running `uv run python …/daily_price_bars_1d_cron.py` with `DATABASE_URL`.

**Secrets:** `DATABASE_URL` (and any auth for the HTTP path) via Secret Manager / Cloud Run secrets — consistent with existing `finto` deploy.

## 8. Success criteria

- Migration applies cleanly on Supabase Postgres.
- Backfill completes for full `in_equities` universe without unique violations; reruns are safe (upsert).
- Row count per symbol ≈ number of **trading days** in ~2 years (not calendar days).
- Daily job completes within acceptable wall time (tune `--delay` vs rate limits).

## 9. Risks & mitigations

| Risk | Mitigation |
|------|------------|
| Yahoo rate limits / blocks | Configurable inter-symbol delay; backoff retries (future). |
| Symbol delisted / no history | Log and skip; no row insert. |
| Long backfill runtime | Batch by symbol with commit per symbol; optional `--limit` for staging. |

## 10. Open questions (future PRDs)

- Official NSE calendar table vs Yahoo-implied calendar for corporate actions audit.
- Wire API `/ticker/...` chart to read from `price_bars_1d` instead of live yfinance.
