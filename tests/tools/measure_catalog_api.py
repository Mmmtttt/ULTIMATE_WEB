#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import statistics
import time
from typing import Any, Dict, List
from urllib.parse import urlencode

import requests


def _base_params(page_size: int) -> Dict[str, str]:
    return {
        "paginate": "1",
        "summary": "1",
        "page": "1",
        "page_size": str(page_size),
    }


def _default_endpoints(keyword: str, page_size: int) -> tuple[tuple[str, str, Dict[str, str]], ...]:
    score_params = {
        **_base_params(page_size),
        "sort_type": "score",
        "sort_order": "desc",
    }
    search_params = {
        **_base_params(page_size),
        "keyword": keyword,
    }
    random_params = {
        **_base_params(page_size),
        "sort_type": "random",
    }
    return (
        ("comic_list_score", "/api/v1/comic/list", dict(score_params)),
        ("comic_list_score_with_authors", "/api/v1/comic/list", {**score_params, "include_available_authors": "1"}),
        ("comic_list_search", "/api/v1/comic/list", dict(search_params)),
        ("comic_list_random", "/api/v1/comic/list", dict(random_params)),
        ("video_list_score", "/api/v1/video/list", dict(score_params)),
        ("video_list_score_with_authors", "/api/v1/video/list", {**score_params, "include_available_authors": "1"}),
        ("video_list_search", "/api/v1/video/list", dict(search_params)),
        ("video_list_random", "/api/v1/video/list", dict(random_params)),
        ("preview_comic_list_score", "/api/v1/recommendation/list", dict(score_params)),
        ("preview_comic_list_search", "/api/v1/recommendation/list", dict(search_params)),
        ("preview_video_list_score", "/api/v1/video/recommendation/list", dict(score_params)),
        ("preview_video_list_search", "/api/v1/video/recommendation/list", dict(search_params)),
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
    index_durations: List[float] = []
    response_sizes: List[int] = []
    failures = 0
    last_total = None
    last_index = ""
    last_search_index = ""
    last_index_rebuilt = None
    thumbnail_url = ""

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
            response_sizes.append(len(response.content or b""))
            data = payload.get("data") or {}
            last_total = data.get("total")
            performance = data.get("performance") or {}
            last_index = str(performance.get("index") or "json")
            last_search_index = str(performance.get("search_index") or "")
            last_index_rebuilt = performance.get("index_rebuilt")
            index_elapsed = performance.get("elapsed_ms")
            if isinstance(index_elapsed, (int, float)):
                index_durations.append(float(index_elapsed))
            items = data.get("items") if isinstance(data, dict) else []
            if not thumbnail_url and isinstance(items, list):
                for item in items:
                    if isinstance(item, dict) and item.get("cover_thumbnail_url"):
                        thumbnail_url = str(item.get("cover_thumbnail_url") or "")
                        break
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
        "search_index": last_search_index,
        "index_rebuilt": last_index_rebuilt,
        "total": last_total,
        "response_bytes": _summarize(response_sizes),
        "client_ms": _summarize(durations),
        "server_ms": _summarize(server_durations),
        "index_ms": _summarize(index_durations),
        "thumbnail": _measure_thumbnail(base_url, thumbnail_url, timeout) if thumbnail_url else None,
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


def _measure_thumbnail(base_url: str, path: str, timeout: float) -> Dict[str, Any]:
    url = f"{base_url.rstrip('/')}{path}"
    attempts: List[Dict[str, Any]] = []
    for _ in range(2):
        started = time.perf_counter()
        try:
            response = requests.get(url, timeout=timeout)
            attempts.append(
                {
                    "status": response.status_code,
                    "client_ms": round((time.perf_counter() - started) * 1000, 3),
                    "bytes": len(response.content or b""),
                    "cache": response.headers.get("X-Cover-Thumbnail-Cache", ""),
                    "cache_control": response.headers.get("Cache-Control", ""),
                }
            )
        except Exception as exc:
            attempts.append({"status": 0, "error": str(exc)})
    return {"url": url, "attempts": attempts}


def main() -> None:
    parser = argparse.ArgumentParser(description="Measure key catalog API latency against a running backend.")
    parser.add_argument("--base-url", default="http://127.0.0.1:5035")
    parser.add_argument("--rounds", type=int, default=20)
    parser.add_argument("--timeout", type=float, default=10)
    parser.add_argument("--keyword", default="test")
    parser.add_argument("--page-size", type=int, default=24)
    args = parser.parse_args()

    results = [
        _measure_endpoint(args.base_url, name, path, params, args.rounds, args.timeout)
        for name, path, params in _default_endpoints(args.keyword, args.page_size)
    ]
    print(json.dumps({"base_url": args.base_url, "results": results}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
