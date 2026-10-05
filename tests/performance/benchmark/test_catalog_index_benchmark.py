from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.performance
def test_catalog_index_paginated_query_smoke(tmp_path, monkeypatch):
    meta_dir = tmp_path / "data" / "meta_data"
    script = REPO_ROOT / "tests" / "tools" / "generate_perf_dataset.py"
    subprocess.run(
        [
            sys.executable,
            str(script),
            "--output",
            str(meta_dir),
            "--items",
            "1000",
            "--tags",
            "120",
            "--lists",
            "50",
        ],
        check=True,
    )

    config_path = tmp_path / "server_config.json"
    config_path.write_text(
        '{"storage": {"data_dir": "%s"}}' % str(tmp_path / "data").replace("\\", "\\\\"),
        encoding="utf-8",
    )
    monkeypatch.setenv("SERVER_CONFIG_PATH", str(config_path))
    monkeypatch.setenv("CATALOG_INDEX_ENABLED", "1")

    child_code = f"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

repo_root = Path({str(REPO_ROOT)!r})
backend_root = repo_root / "comic_backend"
sys.path.insert(0, str(backend_root))

from application.comic_app_service import ComicAppService
from infrastructure.persistence.catalog_index import CatalogIndex

started = time.perf_counter()
rebuild = CatalogIndex().rebuild()
rebuild_ms = (time.perf_counter() - started) * 1000

service = ComicAppService()
started = time.perf_counter()
result = service.get_comic_list(
    sort_type="score",
    sort_order="desc",
    keyword="性能测试",
    include_tags=["tag_perf_0001"],
    page=1,
    page_size=24,
    paginate=True,
    summary_only=True,
)
first_query_ms = (time.perf_counter() - started) * 1000

started = time.perf_counter()
stable_result = service.get_comic_list(
    sort_type="score",
    sort_order="desc",
    keyword="性能测试",
    include_tags=["tag_perf_0001"],
    page=1,
    page_size=24,
    paginate=True,
    summary_only=True,
)
stable_query_ms = (time.perf_counter() - started) * 1000

started = time.perf_counter()
fts_result = service.get_comic_list(
    sort_type="score",
    sort_order="desc",
    keyword="000123",
    page=1,
    page_size=24,
    paginate=True,
    summary_only=True,
)
fts_query_ms = (time.perf_counter() - started) * 1000

os.environ["CATALOG_SEARCH_INDEX_ENABLED"] = "0"
started = time.perf_counter()
like_result = service.get_comic_list(
    sort_type="score",
    sort_order="desc",
    keyword="000123",
    page=1,
    page_size=24,
    paginate=True,
    summary_only=True,
)
like_query_ms = (time.perf_counter() - started) * 1000

print(json.dumps({{
    "rebuild": rebuild,
    "rebuild_ms": rebuild_ms,
    "result_success": result.success,
    "stable_success": stable_result.success,
    "stable_data": stable_result.data,
    "stable_query_ms": stable_query_ms,
    "first_query_ms": first_query_ms,
    "fts_success": fts_result.success,
    "like_success": like_result.success,
    "fts_data": fts_result.data,
    "like_data": like_result.data,
    "fts_query_ms": fts_query_ms,
    "like_query_ms": like_query_ms,
}}, ensure_ascii=False))
"""

    env = dict(os.environ)
    env["SERVER_CONFIG_PATH"] = str(config_path)
    env["CATALOG_INDEX_ENABLED"] = "1"
    completed = subprocess.run(
        [sys.executable, "-c", child_code],
        cwd=str(REPO_ROOT),
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    metrics = json.loads(completed.stdout.strip().splitlines()[-1])

    assert metrics["rebuild"]["indexed_count"] >= 1000
    assert metrics["result_success"]
    assert metrics["stable_success"]
    assert "items" in metrics["stable_data"]
    assert metrics["stable_data"]["performance"]["index"] == "sqlite"
    assert metrics["stable_data"]["performance"]["index_rebuilt"] is False
    assert metrics["stable_data"]["performance"]["search_index"] == "like_scan"
    assert metrics["stable_query_ms"] < max(metrics["rebuild_ms"], metrics["first_query_ms"])

    assert metrics["fts_success"]
    assert metrics["like_success"]
    assert metrics["fts_data"]["performance"]["search_index"] == "fts5_trigram_like"
    assert metrics["like_data"]["performance"]["search_index"] == "like_scan"
    assert metrics["like_data"]["total"] == metrics["fts_data"]["total"]
    assert [item["id"] for item in metrics["like_data"]["items"]] == [
        item["id"] for item in metrics["fts_data"]["items"]
    ]
    assert metrics["fts_query_ms"] < max(metrics["like_query_ms"] * 3, 50)
