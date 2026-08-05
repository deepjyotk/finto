-- TimescaleDB schema for the US stocks data-engineering demo.
--
-- Mounted into the container at /docker-entrypoint-initdb.d/01-schema.sql, so a
-- fresh volume is provisioned automatically. `make timescale-schema` runs the
-- same file against an existing database, which is why every statement is
-- idempotent.
--
-- This file is deliberately not managed by Alembic: continuous aggregates
-- cannot be created inside a transaction block, and Alembic wraps each
-- migration in one. Run it with plain `psql` (no --single-transaction).

CREATE EXTENSION IF NOT EXISTS timescaledb;

-- ────────────────────────────────────────────────────────────────────────────
-- Raw price ticks
-- ────────────────────────────────────────────────────────────────────────────

-- One row per market-data event, written by the Spark streaming job. The
-- primary key doubles as the idempotency key for replayed Kafka offsets, and it
-- leads with event_time because a hypertable requires the partitioning column
-- in every unique constraint.
CREATE TABLE IF NOT EXISTS demo_us_stock_prices (
    event_time  TIMESTAMPTZ    NOT NULL,
    event_id    TEXT           NOT NULL,
    symbol      TEXT           NOT NULL,
    price       NUMERIC(18, 6) NOT NULL,
    volume      BIGINT,
    source      TEXT           NOT NULL DEFAULT 'simulator',
    ingested_at TIMESTAMPTZ    NOT NULL DEFAULT now(),

    PRIMARY KEY (event_time, event_id)
);

SELECT create_hypertable(
    'demo_us_stock_prices',
    'event_time',
    chunk_time_interval => INTERVAL '1 day',
    if_not_exists       => TRUE,
    migrate_data        => TRUE
);

-- Every chart query filters on one symbol over a recent time range.
CREATE INDEX IF NOT EXISTS idx_demo_us_stock_prices_symbol_time
    ON demo_us_stock_prices (symbol, event_time DESC);

-- ────────────────────────────────────────────────────────────────────────────
-- Continuous aggregates — OHLCV bars
-- ────────────────────────────────────────────────────────────────────────────
--
-- `materialized_only = false` turns these into real-time aggregates: a query
-- unions the materialized buckets with a live aggregation over ticks the
-- refresh policy has not covered yet. Without it the newest bucket would stay
-- invisible until the next policy run, which is very obvious on a 1-day bar.

CREATE MATERIALIZED VIEW IF NOT EXISTS demo_us_stock_price_bars_1m
WITH (
    timescaledb.continuous,
    timescaledb.materialized_only = false
)
AS
SELECT
    time_bucket('1 minute', event_time) AS bucket,
    symbol,
    first(price, event_time)            AS open,
    max(price)                          AS high,
    min(price)                          AS low,
    last(price, event_time)             AS close,
    sum(coalesce(volume, 0))            AS volume
FROM demo_us_stock_prices
GROUP BY bucket, symbol
WITH NO DATA;

CREATE MATERIALIZED VIEW IF NOT EXISTS demo_us_stock_price_bars_5m
WITH (
    timescaledb.continuous,
    timescaledb.materialized_only = false
)
AS
SELECT
    time_bucket('5 minutes', event_time) AS bucket,
    symbol,
    first(price, event_time)             AS open,
    max(price)                           AS high,
    min(price)                           AS low,
    last(price, event_time)              AS close,
    sum(coalesce(volume, 0))             AS volume
FROM demo_us_stock_prices
GROUP BY bucket, symbol
WITH NO DATA;

CREATE MATERIALIZED VIEW IF NOT EXISTS demo_us_stock_price_bars_1d
WITH (
    timescaledb.continuous,
    timescaledb.materialized_only = false
)
AS
SELECT
    time_bucket('1 day', event_time) AS bucket,
    symbol,
    first(price, event_time)         AS open,
    max(price)                       AS high,
    min(price)                       AS low,
    last(price, event_time)          AS close,
    sum(coalesce(volume, 0))         AS volume
FROM demo_us_stock_prices
GROUP BY bucket, symbol
WITH NO DATA;

-- Refresh policies. `end_offset` is at least one bucket wide so a policy never
-- materializes a bucket that is still receiving ticks; the real-time part of
-- the view covers that edge.
SELECT add_continuous_aggregate_policy(
    'demo_us_stock_price_bars_1m',
    start_offset      => INTERVAL '2 hours',
    end_offset        => INTERVAL '1 minute',
    schedule_interval => INTERVAL '1 minute',
    if_not_exists     => TRUE
);

SELECT add_continuous_aggregate_policy(
    'demo_us_stock_price_bars_5m',
    start_offset      => INTERVAL '1 day',
    end_offset        => INTERVAL '5 minutes',
    schedule_interval => INTERVAL '5 minutes',
    if_not_exists     => TRUE
);

SELECT add_continuous_aggregate_policy(
    'demo_us_stock_price_bars_1d',
    start_offset      => INTERVAL '90 days',
    end_offset        => INTERVAL '1 day',
    schedule_interval => INTERVAL '1 hour',
    if_not_exists     => TRUE
);

-- ────────────────────────────────────────────────────────────────────────────
-- Alert rules
-- ────────────────────────────────────────────────────────────────────────────

-- user_id holds the Supabase f_users.user_id. It is intentionally not a foreign
-- key: f_users lives in a different database, so referential integrity is
-- enforced by the API, which only ever writes the authenticated user's id.
CREATE TABLE IF NOT EXISTS demo_us_stock_alert_rules (
    id                   UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id              UUID          NOT NULL,
    symbol               TEXT          NOT NULL,
    window_seconds       INTEGER       NOT NULL,
    percentage_threshold NUMERIC(8, 4) NOT NULL,
    -- up: close >= open by threshold%; down: close <= open by threshold%
    direction            TEXT          NOT NULL DEFAULT 'up',
    is_active            BOOLEAN       NOT NULL DEFAULT TRUE,
    created_at           TIMESTAMPTZ   NOT NULL DEFAULT now(),
    updated_at           TIMESTAMPTZ   NOT NULL DEFAULT now(),

    CONSTRAINT ck_demo_us_stock_alert_rules_window_seconds
        CHECK (window_seconds IN (60, 300, 900)),
    CONSTRAINT ck_demo_us_stock_alert_rules_percentage_threshold
        CHECK (percentage_threshold > 0),
    CONSTRAINT ck_demo_us_stock_alert_rules_direction
        CHECK (direction IN ('up', 'down'))
);

CREATE INDEX IF NOT EXISTS idx_demo_us_stock_rules_user
    ON demo_us_stock_alert_rules (user_id, created_at DESC);

-- Spark loads active rules per window size on every micro-batch.
CREATE INDEX IF NOT EXISTS idx_demo_us_stock_rules_active_symbol
    ON demo_us_stock_alert_rules (symbol, window_seconds)
    WHERE is_active = TRUE;

-- ────────────────────────────────────────────────────────────────────────────
-- Triggered alerts
-- ────────────────────────────────────────────────────────────────────────────

-- The unique constraint on (rule_id, window_start, window_end) is what keeps a
-- Spark retry from producing a duplicate alert for the same window. Both it and
-- the primary key include window_start because that is the partitioning column.
CREATE TABLE IF NOT EXISTS demo_us_stock_alerts (
    id                   UUID           NOT NULL DEFAULT gen_random_uuid(),
    rule_id              UUID           NOT NULL
        REFERENCES demo_us_stock_alert_rules (id) ON DELETE CASCADE,
    user_id              UUID           NOT NULL,
    symbol               TEXT           NOT NULL,
    window_start         TIMESTAMPTZ    NOT NULL,
    window_end           TIMESTAMPTZ    NOT NULL,
    opening_price        NUMERIC(18, 6) NOT NULL,
    closing_price        NUMERIC(18, 6) NOT NULL,
    percentage_change    NUMERIC(10, 4) NOT NULL,
    threshold_percentage NUMERIC(8, 4)  NOT NULL,
    message              TEXT           NOT NULL,
    is_read              BOOLEAN        NOT NULL DEFAULT FALSE,
    triggered_at         TIMESTAMPTZ    NOT NULL DEFAULT now(),

    PRIMARY KEY (id, window_start),
    CONSTRAINT uq_demo_us_stock_alerts_rule_window
        UNIQUE (rule_id, window_start, window_end)
);

SELECT create_hypertable(
    'demo_us_stock_alerts',
    'window_start',
    chunk_time_interval => INTERVAL '7 days',
    if_not_exists       => TRUE,
    migrate_data        => TRUE
);

CREATE INDEX IF NOT EXISTS idx_demo_us_stock_alerts_user_time
    ON demo_us_stock_alerts (user_id, triggered_at DESC);

-- ────────────────────────────────────────────────────────────────────────────
-- Idempotent upgrades for volumes that already ran an older schema.sql
-- ────────────────────────────────────────────────────────────────────────────

ALTER TABLE demo_us_stock_alert_rules
    ADD COLUMN IF NOT EXISTS direction TEXT NOT NULL DEFAULT 'up';

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'ck_demo_us_stock_alert_rules_direction'
    ) THEN
        ALTER TABLE demo_us_stock_alert_rules
            ADD CONSTRAINT ck_demo_us_stock_alert_rules_direction
            CHECK (direction IN ('up', 'down'));
    END IF;
END $$;
