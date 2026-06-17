#!/usr/bin/env python3
"""Generate synthetic booster engagement events for the at-risk major gift demo."""

from __future__ import annotations

import argparse
import json
import random
from datetime import datetime, timedelta
from pathlib import Path

CAMPAIGNS = [
    "fall-kickoff",
    "giving-tuesday",
    "bowl-game-invite",
    "spring-gala",
    "alumni-weekend",
    "annual-fund-ask",
    "athletic-director-note",
    "season-ticket-renewal",
]

# Demo narrative: James Chen is the primary at-risk donor surfaced in Cases / UI.
DEMO_DONOR_ID = "ALUM-10001"
INFLECTION_DATE = datetime(2025, 9, 1)
START_DATE = datetime(2024, 3, 1)
END_DATE = datetime(2025, 12, 1)


def days_range(start: datetime, end: datetime) -> list[datetime]:
    delta = end - start
    return [start + timedelta(days=i) for i in range(delta.days)]


def is_after_inflection(date: datetime, donor_id: str, at_risk_donors: set[str]) -> bool:
    return donor_id in at_risk_donors and date >= INFLECTION_DATE


def generate_events(
    donor_ids: list[str],
    at_risk_donors: set[str],
    seed: int = 42,
) -> list[dict]:
    random.seed(seed)
    events: list[dict] = []

    for donor_id in donor_ids:
        at_risk = donor_id in at_risk_donors
        baseline_open_rate = random.uniform(0.6, 0.9) if at_risk else random.uniform(0.5, 0.9)
        baseline_attend_rate = random.uniform(0.4, 0.8)
        baseline_logins_pw = random.randint(1, 5)
        baseline_calls_pq = random.randint(0, 2)

        for month_offset in range(18):
            email_date = START_DATE + timedelta(days=month_offset * 30 + random.randint(0, 5))
            if email_date > END_DATE:
                break
            gone_quiet = is_after_inflection(email_date, donor_id, at_risk_donors)
            opened = 0 if gone_quiet else (1 if random.random() < baseline_open_rate else 0)
            events.append(
                {
                    "donor_id": donor_id,
                    "event_type": "email_open",
                    "event_date": email_date.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "signal_value": opened,
                    "campaign": random.choice(CAMPAIGNS),
                    "fiscal_year": f"FY{email_date.year}",
                }
            )

        event_dates = sorted(random.sample(days_range(START_DATE, END_DATE), 12))
        for event_date in event_dates:
            gone_quiet = is_after_inflection(event_date, donor_id, at_risk_donors)
            attended = 0 if gone_quiet else (1 if random.random() < baseline_attend_rate else 0)
            events.append(
                {
                    "donor_id": donor_id,
                    "event_type": "event_attendance",
                    "event_date": event_date.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "signal_value": attended,
                    "campaign": random.choice(CAMPAIGNS),
                    "fiscal_year": f"FY{event_date.year}",
                }
            )

        current = START_DATE
        while current < END_DATE:
            gone_quiet = is_after_inflection(current, donor_id, at_risk_donors)
            logins = 0 if gone_quiet else random.randint(0, baseline_logins_pw)
            events.append(
                {
                    "donor_id": donor_id,
                    "event_type": "portal_login",
                    "event_date": current.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "signal_value": logins,
                    "campaign": None,
                    "fiscal_year": f"FY{current.year}",
                }
            )
            current += timedelta(weeks=1)

        quarter_start = START_DATE
        while quarter_start < END_DATE:
            gone_quiet = is_after_inflection(quarter_start, donor_id, at_risk_donors)
            calls = 0 if gone_quiet else random.randint(0, baseline_calls_pq)
            events.append(
                {
                    "donor_id": donor_id,
                    "event_type": "call_completed",
                    "event_date": quarter_start.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "signal_value": calls,
                    "campaign": "gift-officer-outreach",
                    "fiscal_year": f"FY{quarter_start.year}",
                }
            )
            quarter_start += timedelta(days=90)

        for year in [2024, 2025]:
            gift_date = datetime(year, random.randint(10, 12), random.randint(1, 28))
            if at_risk and gift_date >= INFLECTION_DATE:
                continue
            if gift_date > END_DATE:
                continue
            amount = random.randint(25000, 75000) if at_risk else random.randint(5000, 75000)
            if donor_id == DEMO_DONOR_ID:
                amount = 50000
            events.append(
                {
                    "donor_id": donor_id,
                    "event_type": "gift_made",
                    "event_date": gift_date.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "signal_value": amount,
                    "campaign": "annual-fund-ask",
                    "fiscal_year": f"FY{year}",
                }
            )

    events.sort(key=lambda e: (e["donor_id"], e["event_date"], e["event_type"]))
    return events


def write_ndjson(events: list[dict], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        for index, event in enumerate(events):
            handle.write(json.dumps({"index": {"_id": f"evt-{index}"}}) + "\n")
            handle.write(json.dumps(event) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--donor-count", type=int, default=200)
    parser.add_argument("--at-risk-count", type=int, default=10)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parent / "output" / "engagement_events.ndjson",
    )
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    donor_ids = [f"ALUM-{10000 + i}" for i in range(args.donor_count)]
    at_risk_donors = set(donor_ids[: args.at_risk_count])
    events = generate_events(donor_ids, at_risk_donors, seed=args.seed)
    write_ndjson(events, args.output)

    post_inflection = [
        e
        for e in events
        if e["donor_id"] in at_risk_donors
        and e["event_date"] >= INFLECTION_DATE.strftime("%Y-%m-%dT%H:%M:%SZ")
        and e["event_type"] in {"email_open", "event_attendance", "portal_login", "call_completed"}
    ]
    zero_signals = sum(1 for e in post_inflection if e["signal_value"] == 0)

    print(f"Generated {len(events):,} engagement events for {len(donor_ids)} donors")
    print(f"Output: {args.output}")
    print(f"At-risk donors (quiet after {INFLECTION_DATE.date()}): {sorted(at_risk_donors)[:5]} ...")
    print(f"Demo donor: {DEMO_DONOR_ID}")
    print(
        f"Post-inflection engagement events for at-risk donors: {len(post_inflection):,} "
        f"({zero_signals:,} with signal_value=0)"
    )


if __name__ == "__main__":
    main()
