#!/usr/bin/env python3
"""Create and start the booster-engagement-drift ML anomaly detection job."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from elastic_client import es_request  # noqa: E402

JOB_ID = "booster-engagement-drift"
JOB_FILE = ROOT / "elastic" / "ml" / "booster-engagement-drift.json"


def job_exists() -> bool:
    response = es_request("GET", f"/_ml/anomaly_detectors/{JOB_ID}")
    return response.status_code == 200


def create_job() -> None:
    body = json.loads(JOB_FILE.read_text(encoding="utf-8"))
    response = es_request("PUT", f"/_ml/anomaly_detectors/{JOB_ID}", json_body=body)
    if response.status_code == 400 and "resource_already_exists" in response.text:
        print(f"ML job '{JOB_ID}' already exists")
        return
    response.raise_for_status()
    print(f"Created ML job '{JOB_ID}'")


def create_datafeed() -> None:
    datafeed_id = f"datafeed-{JOB_ID}"
    body = {
        "job_id": JOB_ID,
        "indices": ["booster-engagement-events"],
        "query": {
            "bool": {
                "must": [
                    {
                        "terms": {
                            "event_type": [
                                "email_open",
                                "event_attendance",
                                "portal_login",
                                "call_completed",
                            ]
                        }
                    }
                ]
            }
        },
    }
    response = es_request("PUT", f"/_ml/datafeeds/{datafeed_id}", json_body=body)
    if response.status_code == 400 and "resource_already_exists" in response.text:
        print(f"Datafeed '{datafeed_id}' already exists")
        return
    response.raise_for_status()
    print(f"Created datafeed '{datafeed_id}'")


def start_datafeed() -> None:
    datafeed_id = f"datafeed-{JOB_ID}"
    status = es_request("GET", f"/_ml/datafeeds/{datafeed_id}/_stats").json()
    state = status["datafeeds"][0]["state"]
    if state == "started":
        print(f"Datafeed '{datafeed_id}' already running")
        return
    response = es_request("POST", f"/_ml/datafeeds/{datafeed_id}/_start")
    response.raise_for_status()
    print(f"Started datafeed '{datafeed_id}'")


def open_job() -> None:
    response = es_request("POST", f"/_ml/anomaly_detectors/{JOB_ID}/_open")
    if response.status_code == 200:
        print(f"Opened job '{JOB_ID}'")
    elif "already open" in response.text.lower():
        print(f"Job '{JOB_ID}' already open")


def wait_for_datafeed(timeout_seconds: int = 300) -> None:
    datafeed_id = f"datafeed-{JOB_ID}"
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        stats = es_request("GET", f"/_ml/datafeeds/{datafeed_id}/_stats").json()
        state = stats["datafeeds"][0]["state"]
        if state == "started":
            print(f"Datafeed state: {state}")
            return
        time.sleep(5)
    raise TimeoutError(f"Datafeed did not start within {timeout_seconds}s")


def main() -> None:
    if not job_exists():
        create_job()
        create_datafeed()
    open_job()
    start_datafeed()
    wait_for_datafeed()
    print(
        "\nNext: open Kibana → Machine Learning → Anomaly Detection → "
        f"{JOB_ID} → Anomaly Explorer"
    )
    print("Look for ALUM-10001 (James Chen) with high anomaly scores after Sept 2025.")


if __name__ == "__main__":
    main()
