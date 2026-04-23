from __future__ import annotations

import importlib
from pathlib import Path

import pytest

from tests.shared.runtime_data import find_by_id, load_json, save_json


@pytest.mark.integration
def test_comic_organize_enrich_local_metadata_prefers_jm_then_fallback_pk_and_is_idempotent(third_party_client, monkeypatch):
    client = third_party_client["client"]
    meta_dir: Path = third_party_client["meta_dir"]
    platform_service_module = importlib.import_module("third_party.platform_service")

    comics_path = meta_dir / "comics_database.json"
    tags_path = meta_dir / "tags_database.json"
    original_comics = load_json(comics_path)
    original_tags = load_json(tags_path)

    calls = []

    class FakePlatformService:
        def search_albums(self, platform, keyword, max_pages=1, fast_mode=False):
            platform_name = str(getattr(platform, "value", platform))
            calls.append(("search", platform_name, str(keyword), bool(fast_mode)))

            if keyword == "少女冒险第1话":
                if platform_name == "JM":
                    return {"albums": [{"album_id": "jm_1", "title": "少女冒险 第1话"}]}
                return {"albums": []}

            if keyword == "神秘岛第2话":
                if platform_name == "JM":
                    return {"albums": []}
                if platform_name == "PK":
                    return {"albums": [{"album_id": "pk_2", "title": "完全不同标题"}]}
                return {"albums": []}

            if keyword == "回退测试第1话":
                if platform_name == "JM":
                    raise RuntimeError("jm search temporary error")
                if platform_name == "PK":
                    return {"albums": [{"album_id": "pk_4", "title": "回退测试 第1话"}]}
                return {"albums": []}

            return {"albums": []}

        def get_album_by_id(self, platform, album_id):
            platform_name = str(getattr(platform, "value", platform))
            calls.append(("detail", platform_name, str(album_id)))

            if str(album_id) == "jm_1":
                return {
                    "albums": [
                        {
                            "album_id": "jm_1",
                            "title": "少女冒险 第1话",
                            "author": "作者JM",
                            "tags": ["冒险", "奇幻", "冒险"],
                        }
                    ]
                }
            if str(album_id) == "pk_2":
                return {
                    "albums": [
                        {
                            "album_id": "pk_2",
                            "title": "完全不同标题",
                            "author": "作者PK",
                            "tags": ["悬疑"],
                        }
                    ]
                }
            if str(album_id) == "pk_4":
                return {
                    "albums": [
                        {
                            "album_id": "pk_4",
                            "title": "回退测试 第1话",
                            "author": "作者PK回退",
                            "tags": ["科幻"],
                        }
                    ]
                }
            return {"albums": []}

    monkeypatch.setattr(platform_service_module, "get_platform_service", lambda: FakePlatformService())

    try:
        save_json(
            comics_path,
            {
                "collection_name": "Test Comics",
                "user": "test-user",
                "total_comics": 7,
                "last_updated": "2026-04-01",
                "comics": [
                    {"id": "LOCAL1001", "title": "少女冒险【汉化】第1话", "author": "", "tag_ids": [], "is_deleted": False},
                    {"id": "LOCAL1002", "title": "神秘岛 第2话", "author": "", "tag_ids": [], "is_deleted": False},
                    {"id": "LOCAL1003", "title": "少女冒险 第1话", "author": "", "tag_ids": [], "is_deleted": False, "local_metadata_enriched": True},
                    {"id": "LOCAL1004", "title": "回退测试 第1话", "author": "", "tag_ids": [], "is_deleted": False},
                    {"id": "LOCAL1005", "title": "少女冒险（修订）第1话", "author": "", "tag_ids": [], "is_deleted": False},
                    {"id": "LOCAL1006", "title": "无结果作品 第1话", "author": "", "tag_ids": [], "is_deleted": False},
                    {"id": "JM100001", "title": "普通在线漫画", "author": "A", "tag_ids": [], "is_deleted": False},
                ],
            },
        )
        save_json(
            tags_path,
            {
                "collection_name": "Test Tags",
                "user": "test-user",
                "last_updated": "2026-04-01",
                "tags": [
                    {"id": "tag_001", "name": "冒险", "content_type": "comic", "create_time": "2026-04-01T00:00:00"},
                    {"id": "tag_video", "name": "视频Tag", "content_type": "video", "create_time": "2026-04-01T00:00:00"},
                ],
            },
        )

        first_resp = client.post(
            "/api/v1/organize/run",
            json={"mode": "comic", "action": "enrich_local_metadata"},
        )
        first_payload = first_resp.get_json()
        assert first_resp.status_code == 200
        assert first_payload["code"] == 200

        first_data = first_payload["data"] or {}
        assert first_data["matched_by_platform"]["JM"] == 2
        assert first_data["matched_by_platform"]["PK"] == 2
        assert first_data["search_platform_order"][:2] == ["JM", "PK"]
        assert first_data["updated_records"] == 4
        assert first_data["updated_authors"] == 4
        assert first_data["created_tags"] == 3
        assert first_data["updated_tag_bindings"] == 6
        assert first_data["skipped_no_match"] == 1
        assert first_data["skipped_already_enriched"] == 1

        first_run_calls = list(calls)
        assert ("search", "JM", "神秘岛第2话", True) in first_run_calls
        assert ("search", "PK", "神秘岛第2话", True) in first_run_calls
        assert ("search", "JM", "回退测试第1话", True) in first_run_calls
        assert ("search", "PK", "回退测试第1话", True) in first_run_calls
        assert all(item[3] is True for item in first_run_calls if item[0] == "search")
        assert sum(1 for item in first_run_calls if item == ("search", "JM", "少女冒险第1话", True)) == 1

        refreshed_comics = load_json(comics_path).get("comics") or []
        refreshed_tags = load_json(tags_path).get("tags") or []
        refreshed_tag_names = [str(item.get("name") or "") for item in refreshed_tags]

        local_1001 = find_by_id(refreshed_comics, "LOCAL1001")
        local_1002 = find_by_id(refreshed_comics, "LOCAL1002")
        local_1004 = find_by_id(refreshed_comics, "LOCAL1004")
        local_1005 = find_by_id(refreshed_comics, "LOCAL1005")
        local_1006 = find_by_id(refreshed_comics, "LOCAL1006")
        assert local_1001 is not None
        assert local_1002 is not None
        assert local_1004 is not None
        assert local_1005 is not None
        assert local_1006 is not None

        assert local_1001["author"] == "作者JM"
        assert local_1002["author"] == "作者PK"
        assert local_1004["author"] == "作者PK回退"
        assert local_1005["author"] == "作者JM"
        assert local_1001["local_metadata_enriched"] is True
        assert local_1002["local_metadata_enriched"] is True
        assert local_1004["local_metadata_enriched"] is True
        assert local_1005["local_metadata_enriched"] is True
        assert bool(local_1006.get("local_metadata_enriched", False)) is False

        assert refreshed_tag_names.count("冒险") == 1
        assert "奇幻" in refreshed_tag_names
        assert "悬疑" in refreshed_tag_names
        assert "科幻" in refreshed_tag_names

        second_resp = client.post(
            "/api/v1/organize/run",
            json={"mode": "comic", "action": "enrich_local_metadata"},
        )
        second_payload = second_resp.get_json()
        assert second_resp.status_code == 200
        assert second_payload["code"] == 200
        second_data = second_payload["data"] or {}
        assert second_data["updated_records"] == 0
        assert second_data["skipped_already_enriched"] >= 5
    finally:
        save_json(comics_path, original_comics)
        save_json(tags_path, original_tags)


@pytest.mark.integration
def test_comic_local_metadata_refresh_updates_author_and_tags_without_overwriting_title(
    third_party_client,
    monkeypatch,
):
    client = third_party_client["client"]
    meta_dir: Path = third_party_client["meta_dir"]
    platform_service_module = importlib.import_module("third_party.platform_service")

    comics_path = meta_dir / "comics_database.json"
    tags_path = meta_dir / "tags_database.json"
    original_comics = load_json(comics_path)
    original_tags = load_json(tags_path)

    class FakePlatformService:
        def search_albums(self, platform, keyword, max_pages=1, fast_mode=False):
            platform_name = str(getattr(platform, "value", platform))
            normalized_keyword = str(keyword or "").strip().lower()
            if platform_name == "JM" and normalized_keyword.replace(" ", "") in {"mylocalcomicchapter1", "mylocalcomic"}:
                return {"albums": [{"album_id": "jm_1", "title": "Remote changed title"}]}
            return {"albums": []}

        def get_album_by_id(self, platform, album_id):
            if str(album_id or "").strip() != "jm_1":
                return {"albums": []}
            return {
                "albums": [
                    {
                        "album_id": "jm_1",
                        "title": "Remote changed title",
                        "author": "Remote Author",
                        "tags": ["ManualComicTag", "NewComicTag"],
                    }
                ]
            }

    monkeypatch.setattr(platform_service_module, "get_platform_service", lambda: FakePlatformService())

    try:
        save_json(
            comics_path,
            {
                "collection_name": "Test Comics",
                "user": "test-user",
                "total_comics": 2,
                "last_updated": "2026-04-01",
                "comics": [
                    {
                        "id": "LOCAL2001",
                        "title": "My Local Comic Chapter 1",
                        "author": "",
                        "tag_ids": ["tag_comic_manual"],
                        "is_deleted": False,
                    },
                    {
                        "id": "LOCAL2002",
                        "title": "Another Local Comic",
                        "author": "",
                        "tag_ids": [],
                        "is_deleted": False,
                    },
                ],
            },
        )
        save_json(
            tags_path,
            {
                "collection_name": "Test Tags",
                "user": "test-user",
                "last_updated": "2026-04-01",
                "tags": [
                    {"id": "tag_comic_manual", "name": "ManualComicTag", "content_type": "comic", "create_time": "2026-04-01T00:00:00"},
                ],
            },
        )

        resp = client.post(
            "/api/v1/comic/local-metadata/refresh",
            json={"comic_id": "LOCAL2001"},
        )
        payload = resp.get_json()
        assert resp.status_code == 200
        assert payload["code"] == 200

        data = payload["data"] or {}
        assert data["id"] == "LOCAL2001"
        assert data["title"] == "My Local Comic Chapter 1"
        assert data["author"] == "Remote Author"
        assert data["metadata_refresh"]["matched_platform"] == "JM"
        assert data["metadata_refresh"]["bound_tags"] >= 1

        refreshed_comics = load_json(comics_path).get("comics") or []
        refreshed_tags = load_json(tags_path).get("tags") or []
        tag_names = {str(tag.get("name") or "") for tag in refreshed_tags}

        local_2001 = find_by_id(refreshed_comics, "LOCAL2001")
        local_2002 = find_by_id(refreshed_comics, "LOCAL2002")
        assert local_2001 is not None
        assert local_2002 is not None
        assert local_2001["title"] == "My Local Comic Chapter 1"
        assert local_2001["author"] == "Remote Author"
        assert local_2001["local_metadata_enriched"] is True
        assert "tag_comic_manual" in (local_2001.get("tag_ids") or [])
        assert "NewComicTag" in tag_names
        assert local_2002["title"] == "Another Local Comic"
    finally:
        save_json(comics_path, original_comics)
        save_json(tags_path, original_tags)


@pytest.mark.integration
def test_comic_local_metadata_refresh_jm_uses_first_search_payload_without_detail_fanout(
    third_party_client,
    monkeypatch,
):
    client = third_party_client["client"]
    meta_dir: Path = third_party_client["meta_dir"]
    platform_service_module = importlib.import_module("third_party.platform_service")

    comics_path = meta_dir / "comics_database.json"
    tags_path = meta_dir / "tags_database.json"
    original_comics = load_json(comics_path)
    original_tags = load_json(tags_path)
    calls = {"detail": 0}

    class FakePlatformService:
        def search_albums(self, platform, keyword, max_pages=1, fast_mode=False):
            platform_name = str(getattr(platform, "value", platform))
            if platform_name != "JM":
                return {"albums": []}
            return {
                "albums": [
                    {
                        "album_id": "jm_533565",
                        "title": "Remote Title",
                        "author": "Search Author",
                        "tags": ["SearchTagA", "SearchTagB"],
                    }
                ]
            }

        def get_album_by_id(self, platform, album_id):
            calls["detail"] += 1
            return {
                "albums": [
                    {
                        "album_id": str(album_id),
                        "title": "Detail Title",
                        "author": "Detail Author",
                        "tags": ["DetailTag"],
                    }
                ]
            }

    monkeypatch.setattr(platform_service_module, "get_platform_service", lambda: FakePlatformService())

    try:
        save_json(
            comics_path,
            {
                "collection_name": "Test Comics",
                "user": "test-user",
                "total_comics": 1,
                "last_updated": "2026-04-01",
                "comics": [
                    {
                        "id": "LOCAL3001",
                        "title": "Any Comic Title",
                        "author": "",
                        "tag_ids": [],
                        "is_deleted": False,
                    }
                ],
            },
        )
        save_json(
            tags_path,
            {
                "collection_name": "Test Tags",
                "user": "test-user",
                "last_updated": "2026-04-01",
                "tags": [],
            },
        )

        resp = client.post(
            "/api/v1/comic/local-metadata/refresh",
            json={"comic_id": "LOCAL3001"},
        )
        payload = resp.get_json()
        assert resp.status_code == 200
        assert payload["code"] == 200

        data = payload["data"] or {}
        assert data["id"] == "LOCAL3001"
        assert data["author"] == "Search Author"
        assert data["metadata_refresh"]["matched_platform"] == "JM"
        assert calls["detail"] == 0

        refreshed_tags = load_json(tags_path).get("tags") or []
        tag_names = {str(tag.get("name") or "") for tag in refreshed_tags}
        assert "SearchTagA" in tag_names
        assert "SearchTagB" in tag_names
    finally:
        save_json(comics_path, original_comics)
        save_json(tags_path, original_tags)
