# PRD: `us-stocks-data-engineering-flow-demo`

## 1. Overview

Build an isolated data-engineering demonstration inside Arthik that streams US stock prices, evaluates user-created alert rules using Spark Structured Streaming, and delivers triggered alerts to the UI in real time.

This feature must remain completely independent from existing Arthik portfolio, AI, notification, and alert functionality.

The only existing Arthik entity referenced will be:

```text
f_users.id
```

All new database tables, APIs, Kafka topics, backend modules, and UI components must use the `demo_us_stock` naming convention.

---



## 2. Goal

Allow a user to create a simple stock-price alert rule:

```text
Stock: AAPL
Time window: 5 minutes
Percentage change: 2%
```

The system should trigger an alert when the absolute price change within the selected window reaches or exceeds the configured threshold.

```text
percentage_change =
((closing_price - opening_price) / opening_price) × 100
```

Example:

```text
Opening price: $200
Closing price: $205
Change: +2.5%
Configured threshold: 2%

Result: Alert triggered
```

---



## 3. Scope



### Included

- Alpaca WebSocket market-data ingestion
- Redpanda Kafka-compatible topic
- Databricks Spark Structured Streaming
- Window-based price aggregation
- User-specific alert-rule evaluation
- Supabase storage
- Backend SSE notifications
- Alerts-page UI
- Timescale hypertable for stock prices



### Not included

- Trading or order execution
- Portfolio integration
- Indian stock support
- AI-generated analysis
- Existing Arthik alert-system integration
- Email, SMS, or push notifications
- Production-grade market-data guarantees

---



## 4. Architecture

```text
Alpaca WebSocket
        ↓
Arthik backend market-data producer
        ↓
Redpanda topic: demo-market-prices
        ↓
Databricks Spark Structured Streaming
        ↓
 ┌──────────────────────────────┐
 │ Price ingestion              │
 │ Window aggregation           │
 │ Alert-rule evaluation        │
 └──────────────────────────────┘
        ↓
Supabase
 ├── demo_us_stock_prices
 ├── demo_us_stock_alert_rules
 └── demo_us_stock_alerts
        ↓
Arthik backend SSE
        ↓
Alerts UI
```

---



## 5. User Experience



### Alerts page

When the user opens the existing **Alerts** tab, add a separate section:

```text
US Stock Data Engineering Demo
```

Add a button:

```text
Create US Stock Alert
```



### Create-alert form

The user provides:

- **Stock symbol**
  - Example: `AAPL`, `TSLA`, `NVDA`
- **Time window**
  - 1 minute
  - 5 minutes
  - 15 minutes
- **Percentage-change threshold**
  - Example: `2%`

For the initial demo, the rule triggers for movement in either direction:

```text
absolute percentage change >= configured threshold
```



### Example

```text
Symbol: TSLA
Window: 5 minutes
Threshold: 3%
```

The rule means:

> Trigger an alert when TSLA moves up or down by at least 3% within a five-minute window.

---



## 6. Processing Flow



### Step 1: Market-data ingestion

The Arthik backend connects to the Alpaca WebSocket and subscribes to supported symbols.

Each price event is normalized:

```json
{
  "event_id": "alpaca-event-id",
  "symbol": "AAPL",
  "price": 205.42,
  "volume": 100,
  "event_time": "2026-08-01T19:30:15.100Z"
}
```



### Step 2: Publish to Redpanda

The backend publishes normalized events to:

```text
demo-market-prices
```

Recommended Kafka message key:

```text
symbol
```

This helps preserve ordering for events belonging to the same stock symbol.

### Step 3: Spark consumes the stream

Databricks Spark Structured Streaming consumes events from Redpanda.

Spark should:

1. Parse and validate each event.
2. Remove invalid or duplicate events.
3. Store valid prices in `demo_us_stock_prices`.
4. Group events by stock symbol and time window.
5. Calculate opening and closing prices.
6. Calculate percentage change.
7. Load active user alert rules.
8. Compare window results against matching rules.
9. Insert triggered alerts into `demo_us_stock_alerts`.



### Step 4: Send UI notification

The Arthik backend listens for newly created alerts and delivers them through SSE:

```text
GET /api/demo/us-stocks/alerts/stream
```

The UI displays a notification such as:

```text
TSLA moved +3.4% during the last 5 minutes.
Your configured threshold was 3%.
```

---



# 7. Database Schema



## 7.1 Stock prices

`demo_us_stock_prices` stores raw market-price events.

```sql
CREATE TABLE demo_us_stock_prices (
    event_time     TIMESTAMPTZ NOT NULL,
    event_id       TEXT NOT NULL,
    symbol         TEXT NOT NULL,
    price          NUMERIC(18, 6) NOT NULL,
    volume         BIGINT,
    source         TEXT NOT NULL DEFAULT 'alpaca',
    ingested_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    PRIMARY KEY (event_time, event_id)
);
```

Convert only this table into a Timescale hypertable:

```sql
SELECT create_hypertable(
    'demo_us_stock_prices',
    'event_time',
    if_not_exists => TRUE
);
```

Create an index for stock-history queries:

```sql
CREATE INDEX idx_demo_us_stock_prices_symbol_time
ON demo_us_stock_prices (symbol, event_time DESC);
```

This does not change other Supabase tables. Only `demo_us_stock_prices` becomes a hypertable.

---



## 7.2 Alert rules

`demo_us_stock_alert_rules` stores user-created rules.

```sql
CREATE TABLE demo_us_stock_alert_rules (
    id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    user_id                  UUID NOT NULL
                             REFERENCES f_users(id)
                             ON DELETE CASCADE,

    symbol                   TEXT NOT NULL,

    window_seconds           INTEGER NOT NULL
                             CHECK (window_seconds IN (60, 300, 900)),

    percentage_threshold     NUMERIC(8, 4) NOT NULL
                             CHECK (percentage_threshold > 0),

    is_active                BOOLEAN NOT NULL DEFAULT TRUE,

    created_at               TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at               TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

Recommended index:

```sql
CREATE INDEX idx_demo_us_stock_rules_active_symbol
ON demo_us_stock_alert_rules (symbol, window_seconds)
WHERE is_active = TRUE;
```

---



## 7.3 Triggered alerts

`demo_us_stock_alerts` stores generated alert instances.

```sql
CREATE TABLE demo_us_stock_alerts (
    id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    rule_id                  UUID NOT NULL
                             REFERENCES demo_us_stock_alert_rules(id)
                             ON DELETE CASCADE,

    user_id                  UUID NOT NULL
                             REFERENCES f_users(id)
                             ON DELETE CASCADE,

    symbol                   TEXT NOT NULL,

    window_start             TIMESTAMPTZ NOT NULL,
    window_end               TIMESTAMPTZ NOT NULL,

    opening_price            NUMERIC(18, 6) NOT NULL,
    closing_price            NUMERIC(18, 6) NOT NULL,

    percentage_change        NUMERIC(10, 4) NOT NULL,
    threshold_percentage     NUMERIC(8, 4) NOT NULL,

    message                  TEXT NOT NULL,

    is_read                  BOOLEAN NOT NULL DEFAULT FALSE,
    triggered_at             TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (rule_id, window_start, window_end)
);
```

The unique constraint prevents Spark retries from creating duplicate alerts for the same rule and time window.

Recommended index:

```sql
CREATE INDEX idx_demo_us_stock_alerts_user_time
ON demo_us_stock_alerts (user_id, triggered_at DESC);
```

---



## 8. Alert-Evaluation Logic

For each completed window:

```text
opening_price = first price in the window
closing_price = last price in the window
```

Calculate:

```text
percentage_change =
((closing_price - opening_price) / opening_price) × 100
```

Trigger an alert when:

```text
ABS(percentage_change) >= percentage_threshold
```

The rule must also match:

```text
rule.symbol = aggregated symbol
rule.window_seconds = aggregation window
rule.is_active = true
```

---



## 9. Backend APIs

```text
POST   /api/demo/us-stocks/alert-rules
GET    /api/demo/us-stocks/alert-rules
PATCH  /api/demo/us-stocks/alert-rules/{rule_id}
DELETE /api/demo/us-stocks/alert-rules/{rule_id}

GET    /api/demo/us-stocks/alerts
PATCH  /api/demo/us-stocks/alerts/{alert_id}/read
GET    /api/demo/us-stocks/alerts/stream
```

All rule and alert endpoints must derive the authenticated `user_id` from the session. The client must not be allowed to submit another user’s ID.

---



## 10. Feature Isolation

Use separate naming throughout the implementation:

```text
Feature directory:
demo_us_stocks_data_engineering

Redpanda topic:
demo-market-prices

Spark job:
demo_us_stock_alert_processor

Supabase tables:
demo_us_stock_prices
demo_us_stock_alert_rules
demo_us_stock_alerts

Backend routes:
/api/demo/us-stocks/*

UI components:
DemoUsStockAlerts
DemoUsStockAlertForm
DemoUsStockAlertList
```

The feature must not:

- Modify existing Arthik portfolio tables
- Read existing holdings
- Reuse existing alert tables
- Trigger existing AI workflows
- Change existing user functionality

---



## 11. Demo Acceptance Criteria

The feature is complete when:

1. A user can create an alert rule from the Alerts tab.
2. The rule is linked to `f_users.id`.
3. The Arthik backend publishes Alpaca price events to Redpanda.
4. Databricks Spark consumes the events.
5. Spark stores price events in `demo_us_stock_prices`.
6. Spark calculates price changes for supported windows.
7. Spark evaluates active user rules.
8. A matching rule creates exactly one alert record per window.
9. The backend sends the alert through SSE.
10. The UI displays the triggered alert without refreshing the page.

**Implementation assumption:** the current Supabase project supports the TimescaleDB extension. If it does not, keep the same schema as a regular PostgreSQL table for the demo.