Yes—what you’re describing **absolutely exists in finance**, and you’re thinking in the right direction for building an agent.

The umbrella term is:

> 🧠 **Event-Driven Investing / Event-Driven Trading**

This is a formal strategy used by hedge funds and quants.

---

# 🧩 1. Standard Finance Terminology (What you should use)

Here’s how your “news types” map to **industry-standard categories**:

---

## 📉 1. Management / Governance Events

**Keywords:**

* CEO resignation
* CFO exit
* Board changes

**Finance term:**

> **Management Change Event** or **Corporate Governance Event**

⚠️ Tracked closely by regulators like
Securities and Exchange Board of India

---

## 📊 2. Earnings Events

**Keywords:**

* Results announced
* Profit up/down
* Margin change

**Finance term:**

> **Earnings Announcement Event**

Sub-types:

* Earnings Beat
* Earnings Miss
* Guidance Upgrade/Downgrade

---

## 🧾 3. Business / Contract Events

**Keywords:**

* Order win
* Contract cancellation
* New client

**Finance term:**

> **Material Business Update**
> or
> **Order Flow / Contract Event**

---

## ⚖️ 4. Regulatory / Legal Events

**Keywords:**

* SEBI action
* Fine / ban
* Investigation

**Finance term:**

> **Regulatory Event** or **Legal Event**

---

## 💰 5. Corporate Actions

**Keywords:**

* Buyback
* Dividend
* Stock split

**Finance term:**

> **Corporate Action Event**

---

## 🏦 6. Capital Structure Events

**Keywords:**

* Fundraising
* Debt issuance
* Equity dilution

**Finance term:**

> **Capital Raising Event**

---

## 🔗 7. M&A Events

**Keywords:**

* Acquisition
* Merger
* Stake sale

**Finance term:**

> **Mergers & Acquisitions (M&A Event)**

---

## 🚨 8. Distress / Negative Shock Events

**Keywords:**

* Fraud
* Auditor resignation
* Bankruptcy risk

**Finance term:**

> **Credit Event** or **Distress Event**

---

## 🌍 9. Macro / Policy Events

**Keywords:**

* Budget
* RBI policy
* Interest rates

**Finance term:**

> **Macro Event** or **Policy Event**

---

# 🧠 2. What Professionals Actually Do (Important Insight)

They don’t just classify events.

They classify:

### 👉 Event + Surprise + Market Reaction

Example:

| Event    | Expectation     | Classification        |
| -------- | --------------- | --------------------- |
| Earnings | Expected high   | Neutral               |
| Earnings | Much higher     | **Positive Surprise** |
| Earnings | Slightly higher | Weak signal           |

---

# 🏗️ 3. How YOU Should Design Your Agent (Practical Architecture)

If you just classify events → **low edge**

If you classify like this → **high edge**

---

## ✅ Level 1: Event Type

```
{
  "event_type": "earnings",
  "sub_type": "earnings_beat"
}
```

---

## ✅ Level 2: Sentiment

```
"sentiment": "positive | negative | neutral"
```

---

## ✅ Level 3: Surprise Factor (VERY IMPORTANT)

```
"surprise": "high | medium | low"
```

👉 This is where money is made.

---

## ✅ Level 4: Impact Scope

```
"impact_scope": "company | sector | market"
```

---

## ✅ Level 5: Tradability Score (your secret sauce)

```
"tradability_score": 0–100
```

Based on:

* liquidity
* past reaction patterns
* news credibility

---

# 🧪 4. Example (What your agent should output)

### Input:

> “Company wins ₹5000 Cr order”

### Output:

```json
{
  "event_type": "business_update",
  "sub_type": "large_order_win",
  "sentiment": "positive",
  "surprise": "high",
  "impact_scope": "company",
  "tradability_score": 78
}
```

---

# ⚠️ 5. One Hard Truth (Don’t skip this)

If your agent only does:

* “CEO left → negative”

It will fail.

Because markets care about:

* **expectation vs reality**
* not the event itself

---

# 💡 Final Insight (This is the edge)

You’re not building:

> a news classifier

You’re building:

> a **market reaction predictor**

---

If you want, I can:

* Design a **complete taxonomy + schema (ready for DB + API)**
* Or help you build a **LangGraph pipeline for this agent (end-to-end)**
