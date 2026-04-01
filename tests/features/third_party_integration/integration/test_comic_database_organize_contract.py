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
                    return {"albums": [{"album_id": "pk_2", "title": "神秘岛 第2话"}]}
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
                            "title": "神秘岛 第2话",
                            "author": "作者PK",
                            "tags": ["悬疑"],
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
                "total_comics": 6,
                "last_updated": "2026-04-01",
                "comics": [
                    {"id": "LOCAL1001", "title": "少女冒险【汉化】第1话", "author": "", "tag_ids": [], "is_deleted": False},
                    {"id": "LOCAL1002", "title": "神秘岛 第2话", "author": "", "tag_ids": [], "is_deleted": False},
                    {"id": "LOCAL1003", "title": "少女冒险 第1话", "author": "", "tag_ids": [], "is_deleted": False, "local_metadata_enriched": True},
                    {"id": "LOCAL1004", "title": "无结果作品 第1话", "author": "", "tag_ids": [], "is_deleted": False},
                    {"id": "LOCAL1005", "title": "少女冒险（修订）第1话", "author": "", "tag_ids": [], "is_deleted": False},
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
        assert first_data["matched_on_jm"] == 2
        assert first_data["matched_on_pk"] == 1
        assert first_data["updated_records"] == 3
        assert first_data["updated_authors"] == 3
        assert first_data["created_tags"] == 2
        assert first_data["updated_tag_bindings"] == 5
        assert first_data["skipped_no_match"] == 1
        assert first_data["skipped_already_enriched"] == 1

        first_run_calls = list(calls)
        assert ("search", "JM", "神秘岛第2话", True) in first_run_calls
        assert ("search", "PK", "神秘岛第2话", True) in first_run_calls
        assert all(item[3] is True for item in first_run_calls if item[0] == "search")
        assert sum(1 for item in first_run_calls if item == ("search", "JM", "少女冒险第1话", True)) == 1

        refreshed_comics = load_json(comics_path).get("comics") or []
        refreshed_tags = load_json(tags_path).get("tags") or []
        refreshed_tag_names = [str(item.get("name") or "") for item in refreshed_tags]

        local_1001 = find_by_id(refreshed_comics, "LOCAL1001")
        local_1002 = find_by_id(refreshed_comics, "LOCAL1002")
        local_1004 = find_by_id(refreshed_comics, "LOCAL1004")
        local_1005 = find_by_id(refreshed_comics, "LOCAL1005")
        assert local_1001 is not None
        assert local_1002 is not None
        assert local_1004 is not None
        assert local_1005 is not None

        assert local_1001["author"] == "作者JM"
        assert local_1002["author"] == "作者PK"
        assert local_1005["author"] == "作者JM"
        assert local_1001["local_metadata_enriched"] is True
        assert local_1002["local_metadata_enriched"] is True
        assert local_1005["local_metadata_enriched"] is True
        assert bool(local_1004.get("local_metadata_enriched", False)) is False

        assert refreshed_tag_names.count("冒险") == 1
        assert "奇幻" in refreshed_tag_names
        assert "悬疑" in refreshed_tag_names

        second_resp = client.post(
            "/api/v1/organize/run",
            json={"mode": "comic", "action": "enrich_local_metadata"},
        )
        second_payload = second_resp.get_json()
        assert second_resp.status_code == 200
        assert second_payload["code"] == 200
        second_data = second_payload["data"] or {}
        assert second_data["updated_records"] == 0
        assert second_data["skipped_already_enriched"] >= 4
    finally:
        save_json(comics_path, original_comics)
        save_json(tags_path, original_tags)
