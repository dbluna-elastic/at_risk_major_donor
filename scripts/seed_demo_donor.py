#!/usr/bin/env python3
"""Patch ALUM-10001 into James Chen — the primary at-risk demo persona."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from elastic_client import es_request  # noqa: E402

DONOR_ID = "ALUM-10001"
INDEX = "athletic-boosters"

JAMES_CHEN = {
    "donor_id": DONOR_ID,
    "first_name": "James",
    "last_name": "Chen",
    "email": "james.chen@alumni.example.edu",
    "graduation_year": 1998,
    "degree": "Business",
    "location": {"city": "San Francisco", "state": "CA", "zip": "94105"},
    "giving_history": {
        "lifetime_total": 187500,
        "last_gift_date": "2024-11-03",
        "last_gift_amount": 50000,
        "gift_count": 8,
        "largest_gift": 50000,
        "restricted_to": "Athletics",
    },
    "engagement": {
        "email_open_rate_90d": 0.0,
        "last_email_open": "2025-08-28",
        "events_attended_ytd": 0,
        "game_attendance_count": 22,
        "video_play_rate": 0.15,
        "portal_logins_90d": 1,
    },
    "wealth_signals": {
        "iwave_score": 88,
        "estimated_capacity": "5M+",
        "real_estate_value_est": 3200000,
        "business_ownership": True,
        "political_giving_total": 125000,
    },
    "portfolio_status": "assigned",
    "bio_text": (
        "James Chen graduated in 1998 with a degree in Business. Based in San Francisco, CA. "
        "Has attended 22 football games including the bowl game watch party for the past three years. "
        "Lifetime giving: $187,500 across 8 gifts to the athletics fund, including an annual $50,000 "
        "fall gift. iWave score: 88. Owns a business. Estimated real estate holdings: $3,200,000."
    ),
    "affinity_score": 91.4,
}


def main() -> None:
    response = es_request("GET", f"/{INDEX}/_doc/{DONOR_ID}")
    if response.status_code == 404:
        raise SystemExit(f"{DONOR_ID} not found in {INDEX}. Expected existing booster demo data.")

    update = es_request("PUT", f"/{INDEX}/_doc/{DONOR_ID}", json_body=JAMES_CHEN)
    update.raise_for_status()
    print(f"Updated {DONOR_ID} → James Chen (${JAMES_CHEN['giving_history']['last_gift_amount']:,.0f} annual donor)")


if __name__ == "__main__":
    main()
