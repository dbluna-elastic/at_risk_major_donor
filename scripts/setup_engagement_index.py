#!/usr/bin/env python3
"""Create booster-engagement-events index and bulk-load synthetic data."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from elastic_client import bulk_index_ndjson, ensure_index, es_request  # noqa: E402

MAPPING_FILE = ROOT / "elastic" / "mappings" / "booster-engagement-events.json"
GENERATOR = ROOT / "data" / "generate_engagement_events.py"
DEFAULT_NDJSON = ROOT / "data" / "output" / "engagement_events.ndjson"
INDEX_NAME = "booster-engagement-events"


def generate_data(output: Path) -> None:
    subprocess.run(
        [sys.executable, str(GENERATOR), "--output", str(output)],
        check=True,
        cwd=ROOT,
    )


def validate_at_risk_signals() -> None:
    query = {
        "size": 0,
        "query": {
            "bool": {
                "filter": [
                    {"terms": {"donor_id": [f"ALUM-{10000 + i}" for i in range(10)]}},
                    {"range": {"event_date": {"gte": "2025-09-01"}}},
                    {
                        "terms": {
                            "event_type": [
                                "email_open",
                                "event_attendance",
                                "portal_login",
                                "call_completed",
                            ]
                        }
                    },
                ]
            }
        },
        "aggs": {
            "by_donor": {
                "terms": {"field": "donor_id", "size": 10, "order": {"_key": "asc"}},
                "aggs": {
                    "avg_signal": {"avg": {"field": "signal_value"}},
                    "event_count": {"value_count": {"field": "signal_value"}},
                },
            }
        },
    }
    response = es_request("POST", f"/{INDEX_NAME}/_search", json_body=query)
    response.raise_for_status()
    buckets = response.json()["aggregations"]["by_donor"]["buckets"]
    print("\nPost-Sept-2025 avg signal by at-risk donor:")
    for bucket in buckets:
        print(
            f"  {bucket['key']}: avg={bucket['avg_signal']['value']:.3f}, "
            f"events={int(bucket['event_count']['value'])}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--recreate", action="store_true", help="Delete and recreate the index")
    parser.add_argument("--skip-generate", action="store_true", help="Use existing NDJSON file")
    parser.add_argument("--ndjson", type=Path, default=DEFAULT_NDJSON)
    args = parser.parse_args()

    if not args.skip_generate:
        generate_data(args.ndjson)

    ensure_index(INDEX_NAME, MAPPING_FILE, recreate=args.recreate)
    stats = bulk_index_ndjson(INDEX_NAME, args.ndjson)
    print(f"Bulk indexed {stats['indexed']:,} documents ({stats['errors']} errors)")

    count = es_request("GET", f"/{INDEX_NAME}/_count").json()["count"]
    print(f"Index document count: {count:,}")
    validate_at_risk_signals()


if __name__ == "__main__":
    main()
