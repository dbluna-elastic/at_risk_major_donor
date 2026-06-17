"""Shared Elasticsearch client helpers for demo setup scripts."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")


def require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing {name}. Copy .env.example to .env and set your credentials.")
    return value


def es_request(
    method: str,
    path: str,
    *,
    json_body: dict[str, Any] | None = None,
    raw_body: bytes | None = None,
    params: dict[str, Any] | None = None,
    timeout: int = 120,
) -> requests.Response:
    url = require_env("ELASTICSEARCH_URL").rstrip("/") + path
    headers = {
        "Authorization": f"ApiKey {require_env('ELASTICSEARCH_API_KEY')}",
    }
    if json_body is not None:
        headers["Content-Type"] = "application/json"
    if raw_body is not None:
        headers["Content-Type"] = "application/x-ndjson"
    response = requests.request(
        method,
        url,
        headers=headers,
        json=json_body,
        data=raw_body,
        params=params,
        timeout=timeout,
    )
    return response


def ensure_index(index_name: str, mapping_file: Path, *, recreate: bool = False) -> None:
    exists = es_request("HEAD", f"/{index_name}").status_code == 200
    if exists and recreate:
        delete = es_request("DELETE", f"/{index_name}")
        delete.raise_for_status()
        exists = False

    if exists:
        print(f"Index '{index_name}' already exists — skipping create")
        return

    body = json.loads(mapping_file.read_text(encoding="utf-8"))
    create = es_request("PUT", f"/{index_name}", json_body=body)
    create.raise_for_status()
    print(f"Created index '{index_name}'")


def bulk_index_ndjson(index_name: str, ndjson_path: Path, *, chunk_lines: int = 2000) -> dict[str, int]:
    """Bulk index an NDJSON file produced by generate_engagement_events.py."""
    stats = {"indexed": 0, "errors": 0}
    buffer: list[str] = []

    def flush() -> None:
        if not buffer:
            return
        payload = "".join(buffer).encode("utf-8")
        response = es_request(
            "POST",
            f"/{index_name}/_bulk",
            raw_body=payload,
            params={"refresh": "wait_for"},
            timeout=300,
        )
        response.raise_for_status()
        result = response.json()
        stats["indexed"] += sum(1 for item in result.get("items", []) if item.get("index", {}).get("result") in {"created", "updated"})
        stats["errors"] += int(result.get("errors", False))
        if result.get("errors"):
            for item in result.get("items", []):
                error = item.get("index", {}).get("error")
                if error:
                    print(f"Bulk error: {error}")
        buffer.clear()

    with ndjson_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            buffer.append(line)
            if len(buffer) >= chunk_lines:
                flush()
        flush()

    return stats
