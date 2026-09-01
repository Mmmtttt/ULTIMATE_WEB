#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import statistics
import time
from typing import Any, Dict, List
from urllib.parse import urlencode

import requests


DEFAULT_ENDPOINTS = (
    (
        "comic_list_score",
        "/api/v1/comic/list",
        {
            "paginate": "1",
            "summary": "1",
            "page": "1",
            "page_size": "24",
            "sort_type": "score",
            "sort_order": "desc",
        },
    ),
    (
        "comic_list_search",
        "/api/v1/comic/list",
        {
            "paginate": "1",
            "summary": "1",
            "page": "1",
            "page_size": "24",
            "keyword": "test",
        },
    ),
    (
        "video_list_score",
        "/api/v1/video/list",
        {
            "paginate": "1",
            "summary": "1",
            "page": "1",
            "page_size": "24",
            "sort_type": "score",
            "sort_order": "desc",
        },
    ),
    (
        "video_list_search",
        "/api/v1/video/list",
        {
            "paginate": "1",
            "summary": "1",
            "page": "1",
            "page_size": "24",
            "keyword": "test",
        },
    ),
)


def _percentile(values: List[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * percentile)))
    return ordered[index]


def _measure_endpoint(base_url: str, name: str, path: str, params: Dict[str, str], rounds: int, timeout: float) -> Dict[str, Any]:
    url = f"{base_url.rstrip('/')}{path}?{urlencode(params)}"
    durations: List[float] = []
    server_durations: List[float] = []
    failures = 0
    last_total = None
    last_index = ""

    for _ in range(rounds):
        started = time.perf_counter()
        try:
            response = requests.get(url, timeout=timeout)
            elapsed_ms = (time.perf_counter() - started) * 1000
            durations.append(elapsed_ms)
            if response.status_code != 200:
                failures += 1
                continue
            payload = response.json()
            if payload.get("code") != 200:
                failures += 1
                continue
            data = payload.get("data") or {}
            last_total = data.get("total")
            last_index = str(((data.get("performance") or {}).get("index") or "json"))
            header_elapsed = response.headers.get("X-Ultimate-Elapsed-Ms")
            if header_elapsed:
                try:
                    server_durations.append(float(header_elapsed))
                except ValueError:
                    pass
        except Exception:
            failures += 1
        time.sleep(0.05)

    return {
        "name": name,
        "url": url,
        "rounds": rounds,
        "failures": failures,
        "index": last_index,
        "total": last_total,
        "client_ms": _summarize(durations),
        "server_ms": _summarize(server_durations),
    }


def _summarize(values: List[float]) -> Dict[str, float]:
    if not values:
        return {"min": 0, "p50": 0, "p95": 0, "max": 0, "avg": 0}
    return {
        "min": round(min(values), 3),
        "p50": round(statistics.median(values), 3),
        "p95": round(_percentile(values, 0.95), 3),
        "max": round(max(values), 3),
        "avg": round(statistics.mean(values), 3),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Measure key catalog API latency against a running backend.")
    parser.add_argument("--base-url", default="http://127.0.0.1:5035")
    parser.add_argument("--rounds", type=int, default=20)
    parser.add_argument("--timeout", type=float, default=10)
    args = parser.parse_args()

    results = [
        _measure_endpoint(args.base_url, name, path, params, args.rounds, args.timeout)
        for name, path, params in DEFAULT_ENDPOINTS
    ]
    print(json.dumps({"base_url": args.base_url, "results": results}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
