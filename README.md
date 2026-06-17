# At-Risk Major Gift Alert — Elastic Demo

Detect major donor engagement drift with Elastic ML, route high-risk alerts to Kibana Cases, and generate recovery briefs with Elastic-native AI.

## Prerequisites

- Python 3.10+
- Existing `athletic-boosters` index on your cluster (from the Booster Prospect Discovery demo)
- Elasticsearch API key with index + ML permissions

## Setup

1. Copy environment variables:

```bash
cp .env.example .env
# Edit .env with your cluster URL and API key
```

2. Install Python dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

3. Load engagement event data:

```bash
python scripts/setup_engagement_index.py --recreate
```

This generates 18 months of synthetic events for 200 donors (10 at-risk after 2025-09-01), creates `booster-engagement-events`, and bulk-indexes the data.

4. Seed the demo persona (James Chen on `ALUM-10001`):

```bash
python scripts/seed_demo_donor.py
```

5. Create and start the ML anomaly job:

```bash
python scripts/setup_ml_job.py
```

## Indexes

| Index | Purpose |
|---|---|
| `athletic-boosters` | Donor profiles (existing, shared with Booster demo) |
| `booster-engagement-events` | Time-series engagement signals per donor |

## Demo narrative

- **At-risk donors:** `ALUM-10000` … `ALUM-10009` go quiet after 2025-09-01
- **Primary persona:** James Chen (`ALUM-10001`) — $50K annual donor, anomaly score target ≥ 85
- **Kibana:** [Anomaly Explorer](https://gawdzilla-0d3e9e.kb.us-east-2.aws.elastic-cloud.com/app/ml/explorer)

## Project layout

```
data/
  generate_engagement_events.py   # Synthetic event generator
  output/                         # Generated NDJSON (gitignored)
elastic/
  mappings/                       # Index mappings
  ml/                             # ML job definitions
scripts/
  setup_engagement_index.py       # Index + bulk load
  seed_demo_donor.py              # James Chen persona
  setup_ml_job.py                 # Anomaly detection job
```

See [at-risk-gift-alert-build-plan.md](./at-risk-gift-alert-build-plan.md) for the full build checklist.
