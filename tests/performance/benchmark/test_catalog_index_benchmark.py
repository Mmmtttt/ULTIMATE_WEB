from __future__ import annotations

import subprocess
import sys
import time
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

    backend_root = REPO_ROOT / "comic_backend"
    if str(backend_root) not in sys.path:
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

    assert rebuild["indexed_count"] >= 1000
    assert result.success
    assert stable_result.success
    assert "items" in result.data
    assert stable_result.data["performance"]["index"] == "sqlite"
    assert stable_result.data["performance"]["index_rebuilt"] is False
    assert stable_query_ms < max(rebuild_ms, first_query_ms)
