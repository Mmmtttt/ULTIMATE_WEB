from __future__ import annotations

import pytest
import requests

from tests.shared.runtime_data import load_json, save_json


@pytest.mark.integration
def test_comic_paginated_list_uses_sqlite_index_and_matches_json_contract(integration_runtime):
    base_url = integration_runtime["base_url"]
    meta_dir = integration_runtime["meta_dir"]

    response = requests.get(
        f"{base_url}/api/v1/comic/list",
        params={
            "paginate": "1",
            "summary": "1",
            "page": 1,
            "page_size": 2,
            "sort_type": "score",
            "sort_order": "desc",
            "include_tag_ids": "tag_action",
        },
        timeout=5,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 200
    assert payload["data"]["performance"]["index"] == "sqlite"

    comics = load_json(meta_dir / "comics_database.json").get("comics", [])
    active = [
        item
        for item in comics
        if not item.get("is_deleted", False) and "tag_action" in (item.get("tag_ids") or [])
    ]
    expected_ids = [
        item["id"]
        for item in sorted(active, key=lambda item: item.get("score") or 0, reverse=True)[:2]
    ]
    assert [item["id"] for item in payload["data"]["items"]] == expected_ids
    assert payload["data"]["total"] == len(active)


@pytest.mark.integration
def test_comic_paginated_index_rebuilds_after_json_changes(integration_runtime):
    base_url = integration_runtime["base_url"]
    meta_dir = integration_runtime["meta_dir"]
    comics_path = meta_dir / "comics_database.json"
    original = load_json(comics_path)
    mutated = load_json(comics_path)

    new_item = dict(mutated["comics"][0])
    new_item.update(
        {
            "id": "PERF_INDEX_NEW_COMIC",
            "title": "Index Freshness Comic",
            "author": "Index Tester",
            "score": 12,
            "tag_ids": ["tag_action"],
            "is_deleted": False,
        }
    )
    mutated["comics"].append(new_item)
    mutated["total_comics"] = len(mutated["comics"])

    try:
        save_json(comics_path, mutated)
        response = requests.get(
            f"{base_url}/api/v1/comic/list",
            params={
                "paginate": "1",
                "summary": "1",
                "page": 1,
                "page_size": 1,
                "sort_type": "score",
                "sort_order": "desc",
                "include_tag_ids": "tag_action",
            },
            timeout=5,
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["code"] == 200
        assert payload["data"]["items"][0]["id"] == "PERF_INDEX_NEW_COMIC"
        assert payload["data"]["performance"]["index"] == "sqlite"
    finally:
        save_json(comics_path, original)


@pytest.mark.integration
def test_comic_paginated_index_preserves_default_score_semantics(integration_runtime):
    base_url = integration_runtime["base_url"]
    meta_dir = integration_runtime["meta_dir"]
    comics_path = meta_dir / "comics_database.json"
    original = load_json(comics_path)
    mutated = load_json(comics_path)

    default_score_item = dict(mutated["comics"][0])
    default_score_item.update(
        {
            "id": "PERF_INDEX_DEFAULT_SCORE_COMIC",
            "title": "Index Default Score Comic",
            "author": "Index Tester",
            "score": None,
            "tag_ids": ["tag_action"],
            "is_deleted": False,
        }
    )
    mutated["comics"].append(default_score_item)
    mutated["total_comics"] = len(mutated["comics"])

    try:
        save_json(comics_path, mutated)
        response = requests.get(
            f"{base_url}/api/v1/comic/list",
            params={
                "paginate": "1",
                "summary": "1",
                "page": 1,
                "page_size": 100,
                "sort_type": "score",
                "sort_order": "desc",
                "include_tag_ids": "tag_action",
                "min_score": 8,
                "max_score": 8,
            },
            timeout=5,
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["code"] == 200
        returned = {item["id"]: item for item in payload["data"]["items"]}
        assert returned["PERF_INDEX_DEFAULT_SCORE_COMIC"]["score"] == 8.0
    finally:
        save_json(comics_path, original)


@pytest.mark.integration
def test_video_paginated_list_uses_sqlite_index_and_matches_json_contract(integration_runtime):
    base_url = integration_runtime["base_url"]
    meta_dir = integration_runtime["meta_dir"]

    response = requests.get(
        f"{base_url}/api/v1/video/list",
        params={
            "paginate": "1",
            "summary": "1",
            "page": 1,
            "page_size": 2,
            "sort_type": "score",
            "sort_order": "desc",
            "include_tag_ids": "tag_video",
        },
        timeout=5,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 200
    assert payload["data"]["performance"]["index"] == "sqlite"

    videos = load_json(meta_dir / "videos_database.json").get("videos", [])
    active = [
        item
        for item in videos
        if not item.get("is_deleted", False) and "tag_video" in (item.get("tag_ids") or [])
    ]
    expected_ids = [
        item["id"]
        for item in sorted(active, key=lambda item: item.get("score") or 0, reverse=True)[:2]
    ]
    assert [item["id"] for item in payload["data"]["items"]] == expected_ids
    assert payload["data"]["total"] == len(active)


@pytest.mark.integration
def test_recommendation_paginated_list_uses_sqlite_index(integration_runtime):
    base_url = integration_runtime["base_url"]
    meta_dir = integration_runtime["meta_dir"]
    recommendations_path = meta_dir / "recommendations_database.json"
    original = load_json(recommendations_path)
    mutated = load_json(recommendations_path)

    item = {
        "id": "PERF_INDEX_PREVIEW_COMIC",
        "title": "Index Preview Comic",
        "author": "Preview Tester",
        "desc": "preview index contract",
        "cover_path": "/static/cover/JM/100001.png",
        "total_page": 10,
        "current_page": 1,
        "score": 11,
        "tag_ids": ["tag_action"],
        "list_ids": [],
        "create_time": "2026-09-01T00:00:00",
        "last_read_time": "2026-09-01T00:00:00",
        "is_deleted": False,
    }
    mutated["recommendations"] = [item]
    mutated["total_recommendations"] = 1

    try:
        save_json(recommendations_path, mutated)
        response = requests.get(
            f"{base_url}/api/v1/recommendation/list",
            params={
                "paginate": "1",
                "summary": "1",
                "page": 1,
                "page_size": 24,
                "sort_type": "score",
                "sort_order": "desc",
                "keyword": "Preview",
            },
            timeout=5,
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["code"] == 200
        assert payload["data"]["performance"]["index"] == "sqlite"
        assert [entry["id"] for entry in payload["data"]["items"]] == ["PERF_INDEX_PREVIEW_COMIC"]
    finally:
        save_json(recommendations_path, original)


@pytest.mark.integration
def test_video_recommendation_paginated_list_uses_sqlite_index(integration_runtime):
    base_url = integration_runtime["base_url"]
    meta_dir = integration_runtime["meta_dir"]
    recommendations_path = meta_dir / "video_recommendations_database.json"
    original = load_json(recommendations_path)
    mutated = load_json(recommendations_path)

    item = {
        "id": "PERF_INDEX_PREVIEW_VIDEO",
        "code": "PIV-001",
        "title": "Index Preview Video",
        "creator": "Preview Maker",
        "actors": ["Actor A"],
        "desc": "preview video index contract",
        "cover_path": "/static/cover/JAVDB/900001.png",
        "cover_path_local": "",
        "thumbnail_images": [],
        "thumbnail_images_local": [],
        "total_units": 1,
        "current_unit": 1,
        "score": 10,
        "tag_ids": ["tag_video"],
        "list_ids": [],
        "create_time": "2026-09-01T00:00:00",
        "last_access_time": "2026-09-01T00:00:00",
        "date": "2026-09-01",
        "is_deleted": False,
    }
    mutated["video_recommendations"] = [item]
    mutated["total_video_recommendations"] = 1

    try:
        save_json(recommendations_path, mutated)
        response = requests.get(
            f"{base_url}/api/v1/video/recommendation/list",
            params={
                "paginate": "1",
                "summary": "1",
                "page": 1,
                "page_size": 24,
                "sort_type": "score",
                "sort_order": "desc",
                "keyword": "Preview",
            },
            timeout=5,
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["code"] == 200
        assert payload["data"]["performance"]["index"] == "sqlite"
        assert [entry["id"] for entry in payload["data"]["items"]] == ["PERF_INDEX_PREVIEW_VIDEO"]
    finally:
        save_json(recommendations_path, original)


@pytest.mark.integration
def test_catalog_index_status_and_rebuild_routes(integration_runtime):
    base_url = integration_runtime["base_url"]

    rebuild_response = requests.post(
        f"{base_url}/api/v1/performance/catalog-index/rebuild",
        timeout=5,
    )
    assert rebuild_response.status_code == 200
    rebuild_payload = rebuild_response.json()
    assert rebuild_payload["code"] == 200
    assert rebuild_payload["data"]["indexed_count"] >= 1

    status_response = requests.get(
        f"{base_url}/api/v1/performance/catalog-index/status",
        timeout=5,
    )
    assert status_response.status_code == 200
    status_payload = status_response.json()
    assert status_payload["code"] == 200
    assert status_payload["data"]["enabled"] is True
    assert status_payload["data"]["stale"] is False
    assert any(item["media_type"] == "comic" for item in status_payload["data"]["counts"])


@pytest.mark.integration
def test_versioned_cover_routes_use_long_cache(integration_runtime):
    base_url = integration_runtime["base_url"]

    response = requests.get(
        f"{base_url}/static/cover/JM/100001.png",
        params={"v": "unit-test"},
        timeout=5,
    )

    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "public, max-age=31536000, immutable"
