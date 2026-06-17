# At-Risk Major Gift Alert — Elastic Demo Build Plan

A booster who historically gives $50K/year quietly stops engaging. Elastic ML detects the behavioral drift across four signals, fires an alert to Kibana Cases, and surfaces an AI-generated re-engagement brief — all before the fiscal year-end ask window closes.

---

## Decisions Locked

| Question | Decision |
|---|---|
| Data | Fully synthetic time-series engagement events, bulk-indexed into Elastic |
| AI Recovery Brief | Elastic-native only — ELSER retrieval + locally deployed generative model (no external LLM API) |
| Alert delivery | Kibana Cases only |
| Environment | Existing Elastic cluster |
| UI | Kibana Anomaly Explorer + Cases + React donor detail view |

---

## 1. The Story Arc (What the Demo Shows)

**Persona:** A major gifts officer managing a portfolio of 40 athletic boosters  
**Problem:** James Chen gives $50K every fall. This year he's gone silent — missed two emails, skipped the spring gala, hasn't logged into the alumni portal. Nobody noticed. Fiscal year-end is 90 days away.

**Demo flow:**

1. Kibana Cases shows a new high-priority case: *"At-Risk: James Chen — $50K lapse risk"*
2. Gift officer opens the case → sees the anomaly timeline: four engagement signals that all broke at the same point
3. Anomaly Explorer shows the ML job flagged the drift 3 weeks ago — with an anomaly score of 94
4. Gift officer clicks "Generate Recovery Brief" → Elastic retrieves donor history via ELSER, locally deployed model produces a personalized re-engagement script
5. Gift officer picks up the phone with a talking-points brief already in hand

**The two wow moments:**
- Anomaly Explorer: four lines converging to zero at the same date — the story tells itself visually
- AI brief generated entirely Elastic-native: no external API call, no data leaving the cluster

---

## 2. Data Architecture

This demo requires two indexes working together:

| Index | What It Stores | Granularity |
|---|---|---|
| `athletic-boosters` | Donor profiles + current scores | One doc per donor (reuse from Booster demo) |
| `booster-engagement-events` | Time-series event log per donor | One doc per engagement event |

### Engagement Events Index

Every interaction a donor has is stored as a discrete event:

```json
{
  "donor_id": "ALUM-10001",
  "event_type": "email_open",
  "event_date": "2025-03-15T09:22:00Z",
  "signal_value": 1,
  "campaign": "spring-gala-invite",
  "fiscal_year": "FY2025"
}
```

**Event types to generate:**

| event_type | signal_value | Notes |
|---|---|---|
| `email_open` | 1 (opened) / 0 (no open) | One doc per email sent |
| `event_attendance` | 1 (attended) / 0 (invited, no show) | Per event invite |
| `portal_login` | 1 per session | Daily roll-up |
| `call_completed` | 1 per completed call | Gift officer log |
| `gift_made` | gift amount | Per transaction |

---

## 3. Synthetic Data Generator

### Script: `generate_engagement_events.py`

Generates 18 months of engagement history for all donors. The key is seeding ~10 "at-risk" donors whose signals drop sharply at a specific inflection date.

```python
# pip install faker numpy
from faker import Faker
import random, json
from datetime import datetime, timedelta

fake = Faker()

# Configuration
DONOR_IDS = [f"ALUM-{10000 + i}" for i in range(200)]  # Use top 200 from booster index
AT_RISK_DONORS = DONOR_IDS[:10]                          # First 10 go silent
INFLECTION_DATE = datetime(2025, 9, 1)                   # When at-risk donors go quiet
START_DATE = datetime(2024, 3, 1)
END_DATE = datetime(2025, 12, 1)

CAMPAIGNS = [
    "fall-kickoff", "giving-tuesday", "bowl-game-invite",
    "spring-gala", "alumni-weekend", "annual-fund-ask",
    "athletic-director-note", "season-ticket-renewal"
]

def days_range(start, end):
    delta = end - start
    return [start + timedelta(days=i) for i in range(delta.days)]

def is_after_inflection(date, donor_id):
    return donor_id in AT_RISK_DONORS and date >= INFLECTION_DATE

events = []

for donor_id in DONOR_IDS:
    at_risk = donor_id in AT_RISK_DONORS

    # Determine baseline engagement level for this donor
    baseline_open_rate  = random.uniform(0.5, 0.9) if not at_risk else random.uniform(0.6, 0.9)
    baseline_attend_rate = random.uniform(0.4, 0.8)
    baseline_logins_pw  = random.randint(1, 5)

    # --- Email opens ---
    # One campaign email per month
    for month_offset in range(18):
        email_date = START_DATE + timedelta(days=month_offset * 30 + random.randint(0, 5))
        if email_date > END_DATE:
            break
        gone_quiet = is_after_inflection(email_date, donor_id)
        opened = 0 if gone_quiet else (1 if random.random() < baseline_open_rate else 0)
        events.append({
            "donor_id": donor_id,
            "event_type": "email_open",
            "event_date": email_date.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "signal_value": opened,
            "campaign": random.choice(CAMPAIGNS),
            "fiscal_year": f"FY{email_date.year}"
        })

    # --- Event attendance ---
    # 8 events per year = ~12 events over 18 months
    event_dates = sorted(random.sample(days_range(START_DATE, END_DATE), 12))
    for event_date in event_dates:
        gone_quiet = is_after_inflection(event_date, donor_id)
        attended = 0 if gone_quiet else (1 if random.random() < baseline_attend_rate else 0)
        events.append({
            "donor_id": donor_id,
            "event_type": "event_attendance",
            "event_date": event_date.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "signal_value": attended,
            "campaign": random.choice(CAMPAIGNS),
            "fiscal_year": f"FY{event_date.year}"
        })

    # --- Portal logins (weekly roll-up) ---
    current = START_DATE
    while current < END_DATE:
        gone_quiet = is_after_inflection(current, donor_id)
        logins = 0 if gone_quiet else random.randint(0, baseline_logins_pw)
        if logins > 0 or random.random() < 0.3:  # Include some zero-login weeks
            events.append({
                "donor_id": donor_id,
                "event_type": "portal_login",
                "event_date": current.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "signal_value": logins,
                "campaign": None,
                "fiscal_year": f"FY{current.year}"
            })
        current += timedelta(weeks=1)

    # --- Gifts (annual, before inflection) ---
    for year in [2024, 2025]:
        gift_date = datetime(year, random.randint(10, 12), random.randint(1, 28))
        if at_risk and gift_date >= INFLECTION_DATE:
            continue  # At-risk donors don't give after going quiet
        if gift_date > END_DATE:
            continue
        events.append({
            "donor_id": donor_id,
            "event_type": "gift_made",
            "event_date": gift_date.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "signal_value": random.randint(5000, 75000) if not at_risk else random.randint(25000, 75000),
            "campaign": "annual-fund-ask",
            "fiscal_year": f"FY{year}"
        })

# Write NDJSON
with open("engagement_events.ndjson", "w") as f:
    for i, e in enumerate(events):
        f.write(json.dumps({"index": {"_id": f"evt-{i}"}}) + "\n")
        f.write(json.dumps(e) + "\n")

print(f"Generated {len(events):,} engagement events for {len(DONOR_IDS)} donors")
print(f"At-risk donors (go quiet after {INFLECTION_DATE.date()}): {AT_RISK_DONORS[:3]}...")
```

Bulk index:
```bash
curl -X POST "https://<your-cluster>/booster-engagement-events/_bulk" \
  -H "Content-Type: application/x-ndjson" \
  --data-binary @engagement_events.ndjson \
  -u elastic:<password>
```

---

## 4. Elasticsearch Index Mapping

```json
PUT /booster-engagement-events
{
  "mappings": {
    "properties": {
      "donor_id":     { "type": "keyword" },
      "event_type":   { "type": "keyword" },
      "event_date":   { "type": "date" },
      "signal_value": { "type": "float" },
      "campaign":     { "type": "keyword" },
      "fiscal_year":  { "type": "keyword" }
    }
  },
  "settings": {
    "number_of_shards": 1,
    "number_of_replicas": 0
  }
}
```

> Keep it flat and simple — the ML jobs aggregate over this index directly.

---

## 5. ML Anomaly Detection

### 5a. Multi-Metric Anomaly Job

Create one job that watches all four signals per donor simultaneously.

```json
PUT _ml/anomaly_detectors/booster-engagement-drift
{
  "description": "Detects when a major gift donor's engagement signals drop abnormally",
  "analysis_config": {
    "bucket_span": "1w",
    "detectors": [
      {
        "function": "mean",
        "field_name": "signal_value",
        "over_field_name": "donor_id",
        "partition_field_name": "event_type",
        "detector_description": "Unusual drop in signal_value per donor per event_type"
      }
    ],
    "influencers": ["donor_id", "event_type"]
  },
  "data_description": {
    "time_field": "event_date",
    "time_format": "epoch_ms"
  },
  "datafeed_config": {
    "indices": ["booster-engagement-events"],
    "query": {
      "bool": {
        "must": [
          { "terms": { "event_type": ["email_open", "event_attendance", "portal_login", "call_completed"] } }
        ]
      }
    }
  }
}
```

**How it works:** The job learns each donor's normal weekly engagement baseline per signal type. When James Chen's `email_open` mean drops from 0.75 to 0 for three consecutive weeks — and the same pattern appears in `event_attendance` and `portal_login` — the anomaly score spikes toward 100.

### 5b. Anomaly Score Thresholds

| Anomaly Score | Risk Level | Action |
|---|---|---|
| 75–84 | Medium | Logged in Anomaly Explorer, no case created |
| 85–94 | High | Kibana Case created, gift officer notified |
| 95–100 | Critical | Case created + flagged for AD review |

### 5c. Alerting Rule → Kibana Cases

Create a rule in Kibana under **Stack Management → Rules**:

- **Rule type:** Anomaly detection alert
- **Job:** `booster-engagement-drift`
- **Condition:** Anomaly score ≥ 85
- **Action:** Create Kibana Case
- **Case title template:** `At-Risk: {{donor_id}} — Est. lapse risk ${{lifetime_giving}}`
- **Case tags:** `at-risk`, `major-gift`, fiscal year tag
- **Severity:** Map anomaly score 85–94 → Medium, 95+ → Critical

---

## 6. AI Recovery Brief (Elastic-Native)

No external LLM. The brief is generated using a two-step Elastic-native pipeline:

### Architecture

```
Kibana Case "Generate Brief" trigger
        ↓
1. ELSER Retrieval
   Query athletic-boosters index for donor profile
   Query booster-engagement-events for last 90 days of events
        ↓
2. Context Assembly
   Build structured donor context block from retrieved docs
        ↓
3. Locally Deployed Generative Model
   Model: phi-3-mini-4k-instruct (deployed via Elastic ML node)
   Runs entirely within the Elasticsearch cluster
        ↓
4. Response rendered in Kibana Case or React UI
```

### Step 1: Deploy the Generative Model

Download and deploy a small instruction-tuned model to the Elastic ML node:

```bash
# Using eland to deploy phi-3-mini from Hugging Face
eland_import_hub_model \
  --url https://<your-cluster> \
  --es-username elastic \
  --es-password <password> \
  --hub-model-id microsoft/Phi-3-mini-4k-instruct \
  --task-type text_generation \
  --es-model-id phi-3-mini-instruct \
  --start
```

> **Note:** Requires an ML node with ≥8GB RAM. Phi-3-mini is ~2.3GB — well within a standard ML tier.

### Step 2: Retrieve Donor Context

```json
GET /athletic-boosters/_search
{
  "query": {
    "term": { "donor_id": "ALUM-10001" }
  },
  "_source": [
    "first_name", "last_name", "graduation_year", "degree",
    "giving_history", "engagement", "wealth_signals", "bio_text"
  ]
}
```

Simultaneously retrieve last 90 days of events:

```json
GET /booster-engagement-events/_search
{
  "query": {
    "bool": {
      "filter": [
        { "term": { "donor_id": "ALUM-10001" } },
        { "range": { "event_date": { "gte": "now-90d" } } }
      ]
    }
  },
  "aggs": {
    "by_type": {
      "terms": { "field": "event_type" },
      "aggs": {
        "signal_sum": { "sum": { "field": "signal_value" } }
      }
    }
  }
}
```

### Step 3: Inference Call to Deployed Model

```json
POST /_inference/completion/phi-3-mini-instruct
{
  "input": "You are an assistant to a university major gifts officer.\n\nDonor: James Chen (Class of 1998, Business)\nLifetime giving: $187,500 across 8 gifts to the Athletics fund\nLast gift: $50,000 on 2024-11-03\nGame attendance: 22 football games\nRecent 90-day engagement:\n  - Email opens: 0 (was averaging 3/month)\n  - Event attendance: 0 (skipped spring gala, bowl game watch party)\n  - Portal logins: 1 (was averaging 8/month)\n  - Calls completed: 0\nAnomaly score: 94 — detected 2025-09-22\n\nWrite a 4-sentence re-engagement brief for the gift officer. Include:\n1. What changed and when\n2. What to reference in the opening of the call\n3. A soft ask approach appropriate to the relationship\n4. The ideal timing for outreach\n\nGround your response only in the data above. Do not invent details."
}
```

### Expected Output

> *James Chen's engagement dropped sharply in early September — email opens, event attendance, and portal activity all fell to near-zero after averaging strong through the summer. Open your call by referencing his 22-game attendance record and the bowl game watch party he's attended the past three years — that personal connection is the strongest anchor you have. Given his $50K annual giving pattern, frame the conversation around the impact of his gifts on the current scholarship class rather than leading with an ask; let him re-engage emotionally first. Ideal timing: reach out in the next two weeks, before mid-October, to preserve the November giving window.*

---

## 7. Kibana Views

### View 1: Anomaly Explorer

- Open ML → Anomaly Explorer
- Select job: `booster-engagement-drift`
- **Swimlane view:** One row per donor, one column per week — color intensity = anomaly score
- **Timeline view:** Multi-signal overlay for a single at-risk donor
- **Influencers panel:** Shows which event_type contributed most to the anomaly

> **Demo move:** Click into James Chen's swimlane → the four signal lines converging to zero is the visual story.

### View 2: Kibana Cases — At-Risk Queue

- Stack Management → Cases
- Filter by tag: `at-risk`
- Each case shows: donor name, anomaly score, estimated lapse value, assigned gift officer
- Gift officer opens a case → sees anomaly summary + "Generate Recovery Brief" button

### Dashboard: Engagement Health Overview

| Panel | Type | Query |
|---|---|---|
| At-risk donors this month | Metric | Cases created in last 30d with tag `at-risk` |
| Anomaly score distribution | Histogram | ML results index, score buckets |
| Revenue at risk (total) | Metric | Sum of `last_gift_amount` for at-risk donor IDs |
| Signal breakdown by event type | Stacked bar | Avg signal_value per event_type per week |
| Engagement trend (all boosters) | Line chart | Weekly avg signal_value across all donors |
| Cases by severity | Donut | Case severity field |

---

## 8. React Web App (Donor Detail View)

The React UI from the Booster demo gets a new panel added to the `DonorDrawer`:

### New Component: `AtRiskPanel`

```
DonorDrawer
├── DonorHeader
├── AffinityScore
├── EngagementTimeline   ← UPDATED: shows anomaly score overlay
├── WealthPanel
├── AtRiskPanel          ← NEW
│   ├── AnomalyScoreBadge  (score + severity color)
│   ├── SignalBreakdown    (4 signal bars: current vs. baseline)
│   ├── InflectionMarker   ("Engagement broke: Sept 1, 2025")
│   └── GenerateBriefBtn   → POST to inference endpoint → renders brief
├── AIBrief              ← shared with Booster demo, reused here
└── AddToPortfolio
```

### Engagement Timeline Enhancement

Overlay the ML anomaly score as a shaded band on the existing timeline chart:
- X-axis: date
- Y-axis left: signal_value (0–1)
- Y-axis right: anomaly score (0–100)
- Red shaded region: weeks where anomaly score ≥ 85

---

## 9. Build Checklist

### Phase 1 — Data & Index (Days 1–3)
- [ ] Create `booster-engagement-events` index with mapping above
- [ ] Run `generate_engagement_events.py` → produces `engagement_events.ndjson`
- [ ] Bulk index events
- [ ] Validate at-risk donor events look correct (zero signal after Sept 1)
- [ ] Confirm event counts per donor look realistic in Dev Tools

### Phase 2 — ML Job (Days 3–5)
- [ ] Create `booster-engagement-drift` anomaly detector via Dev Tools or Kibana ML wizard
- [ ] Create and start datafeed
- [ ] Run job over full 18-month dataset
- [ ] Open Anomaly Explorer — confirm at-risk donors show high anomaly scores
- [ ] Tune bucket_span if results are too noisy (try `2w` if `1w` is jumpy)
- [ ] Verify influencer panel names the right `donor_id` and `event_type`

### Phase 3 — Alerting & Cases (Days 5–6)
- [ ] Create alerting rule in Kibana (anomaly score ≥ 85 → create Case)
- [ ] Test rule by manually bumping a donor's anomaly threshold
- [ ] Confirm Cases appear with correct title, tags, and severity
- [ ] Assign cases to a demo gift officer user in Kibana

### Phase 4 — Generative Model (Days 6–8)
- [ ] Confirm ML node has sufficient RAM (≥8GB available)
- [ ] Install `eland` CLI
- [ ] Deploy `phi-3-mini-instruct` to cluster
- [ ] Test inference call via Dev Tools with a sample donor context
- [ ] Validate output is grounded and sensible (run against 5 at-risk donor profiles)
- [ ] Tune prompt template for tone and length

### Phase 5 — Kibana Dashboards (Days 7–9)
- [ ] Build Engagement Health Overview dashboard (6 panels)
- [ ] Configure Anomaly Explorer swimlane for demo flow
- [ ] Set up Cases queue filtered to `at-risk` tag
- [ ] Save all views and test navigation flow

### Phase 6 — React UI Updates (Days 8–11)
- [ ] Add `AtRiskPanel` component to `DonorDrawer`
- [ ] Wire anomaly score fetch from ML results index
- [ ] Add anomaly overlay to EngagementTimeline chart
- [ ] Wire "Generate Recovery Brief" button to inference endpoint
- [ ] Add loading + error states for brief generation
- [ ] End-to-end test: Case → open donor → anomaly panel → generate brief

### Phase 7 — Demo Polish (Days 11–13)
- [ ] Script the demo narrative: alert fires → case opens → anomaly explorer → brief generated → call made
- [ ] Pre-warm the ML job so Anomaly Explorer loads instantly
- [ ] Confirm brief generation completes in < 10 seconds on demo hardware
- [ ] Record Loom walkthrough
- [ ] Write one-page demo narrative for AE / SC use

---

## 10. Tech Stack Summary

| Layer | Tool |
|---|---|
| Search & storage | Elasticsearch 8.x (existing cluster) |
| Semantic retrieval | ELSER `.elser-2-elasticsearch` |
| ML anomaly detection | Elastic ML — multi-metric anomaly job |
| Generative model | `phi-3-mini-instruct` deployed via `eland` on ML node |
| Alerting | Kibana Alerting rules → Cases |
| Case management | Kibana Cases |
| Dashboards | Kibana Lens + Anomaly Explorer |
| Web app | React + EUI (extends Booster demo app) |
| Synthetic data | Python + Faker → NDJSON bulk index |

---

## 11. How the Two Demos Connect

Both demos share the same `athletic-boosters` index and the same React app. The Booster Prospect Discovery demo surfaces *who to pursue*. The At-Risk Alert demo surfaces *who you're about to lose*. Together they tell a complete revenue protection story:

```
Find hidden high-capacity donors     →    Booster Prospect Discovery
                ↓
Onboard them into the portfolio
                ↓
Monitor for engagement drift         →    At-Risk Major Gift Alert
                ↓
AI brief → gift officer call → gift retained
```

A single demo session can show both use cases back-to-back in the same UI.
