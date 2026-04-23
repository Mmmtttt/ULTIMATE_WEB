from __future__ import annotations

from pathlib import Path

import pytest

from tests.shared.runtime_data import find_by_id, load_json, save_json


@pytest.mark.integration
def test_video_organize_enrich_local_metadata_prefers_javdb_then_fallback_javbus_and_uses_first_result(
    third_party_client,
    monkeypatch,
):
    client = third_party_client["client"]
    meta_dir: Path = third_party_client["meta_dir"]
    video_service_module = third_party_client["video_service_module"]

    videos_path = meta_dir / "videos_database.json"
    tags_path = meta_dir / "tags_database.json"
    original_videos = load_json(videos_path)
    original_tags = load_json(tags_path)

    calls = []

    class FakeAdapter:
        def __init__(self, platform_name: str):
            self.platform_name = platform_name

        def search_videos(self, keyword, page=1, max_pages=1):
            calls.append(("search", self.platform_name, str(keyword), int(page), int(max_pages)))
            code = str(keyword or "").strip().upper()

            if self.platform_name == "javdb":
                if code == "ABP-111":
                    return {
                        "videos": [
                            {"video_id": "JAVDB_111_FIRST", "title": "First On JavDB"},
                            {"video_id": "JAVDB_111_SECOND", "title": "Second On JavDB"},
                        ]
                    }
                return {"videos": []}

            if self.platform_name == "javbus":
                if code == "BUS-222":
                    return {
                        "videos": [
                            {"video_id": "JAVBUS_222_FIRST", "title": "First On JavBus"},
                            {"video_id": "JAVBUS_222_SECOND", "title": "Second On JavBus"},
                        ]
                    }
                return {"videos": []}

            return {"videos": []}

        def get_video_detail(self, video_id, movie_type=None):
            calls.append(("detail", self.platform_name, str(video_id)))
            normalized_id = str(video_id or "").strip().upper()
            if normalized_id == "JAVDB_111_FIRST":
                return {
                    "video_id": "JAVDB_111_FIRST",
                    "code": "ABP-111",
                    "title": "JAVDB 标题",
                    "date": "2025-01-01",
                    "series": "JAVDB 系列",
                    "actors": ["演员A"],
                    "tags": ["标签甲", "标签乙"],
                    "cover_url": "https://example.com/javdb-cover.jpg",
                    "thumbnail_images": ["https://example.com/javdb-thumb-1.jpg"],
                    "preview_video": "https://example.com/javdb-preview.mp4",
                }
            if normalized_id == "JAVBUS_222_FIRST":
                return {
                    "video_id": "JAVBUS_222_FIRST",
                    "code": "BUS-222",
                    "title": "JAVBUS 首条标题",
                    "date": "2024-12-12",
                    "series": "JAVBUS 系列",
                    "actors": ["演员B"],
                    "tags": ["标签乙", "标签丙"],
                    "cover_url": "https://example.com/javbus-cover.jpg",
                    "thumbnail_images": ["https://example.com/javbus-thumb-1.jpg"],
                    "preview_video": "https://example.com/javbus-preview.mp4",
                }
            return {}

    fake_javdb = FakeAdapter("javdb")
    fake_javbus = FakeAdapter("javbus")

    monkeypatch.setattr(
        video_service_module.VideoAppService,
        "_build_video_metadata_adapters",
        lambda self: {"javdb": fake_javdb, "javbus": fake_javbus},
    )
    monkeypatch.setattr(video_service_module.VideoAppService, "cache_cover_to_static_async", lambda *args, **kwargs: None)
    monkeypatch.setattr(video_service_module.VideoAppService, "cache_thumbnail_images_async", lambda *args, **kwargs: None)
    monkeypatch.setattr(video_service_module.VideoAppService, "cache_preview_video_async", lambda *args, **kwargs: None)

    try:
        save_json(
            videos_path,
            {
                "collection_name": "Test Videos",
                "user": "test-user",
                "total_videos": 4,
                "last_updated": "2026-04-01",
                "videos": [
                    {"id": "LOCALV_A", "code": "ABP-111", "title": "原始A", "creator": "", "actors": [], "tag_ids": [], "is_deleted": False},
                    {"id": "LOCALV_B", "code": "BUS-222", "title": "原始B", "creator": "", "actors": [], "tag_ids": [], "is_deleted": False},
                    {"id": "LOCALV_C", "code": "NOMATCH-333", "title": "原始C", "creator": "", "actors": [], "tag_ids": [], "is_deleted": False},
                    {"id": "JAVDB_REMOTE", "code": "REMOTE-1", "title": "非LOCAL", "creator": "", "actors": [], "tag_ids": [], "is_deleted": False},
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
                    {"id": "tag_video_001", "name": "标签乙", "content_type": "video", "create_time": "2026-04-01T00:00:00"},
                ],
            },
        )

        resp = client.post(
            "/api/v1/organize/run",
            json={"mode": "video", "action": "enrich_local_metadata"},
        )
        payload = resp.get_json()
        assert resp.status_code == 200
        assert payload["code"] == 200

        data = payload["data"] or {}
        assert data["search_platform_order"] == ["javdb", "javbus"]
        assert data["matched_by_platform"] == {"javdb": 1, "javbus": 1}
        assert "matched_on_javdb" not in data
        assert "matched_on_javbus" not in data
        assert data["updated_records"] == 2
        assert data["skipped_no_match"] == 1
        assert data["skipped_already_enriched"] == 0
        assert data["created_tags"] >= 2

        assert ("search", "javdb", "ABP-111", 1, 1) in calls
        assert ("search", "javdb", "BUS-222", 1, 1) in calls
        assert ("search", "javbus", "BUS-222", 1, 1) in calls
        assert ("detail", "javbus", "JAVBUS_222_FIRST") in calls

        refreshed_videos = load_json(videos_path).get("videos") or []
        refreshed_tags = load_json(tags_path).get("tags") or []
        tag_names = {str(tag.get("name") or "") for tag in refreshed_tags}

        local_a = find_by_id(refreshed_videos, "LOCALV_A")
        local_b = find_by_id(refreshed_videos, "LOCALV_B")
        local_c = find_by_id(refreshed_videos, "LOCALV_C")
        assert local_a is not None
        assert local_b is not None
        assert local_c is not None

        assert local_a["title"] == "JAVDB 标题"
        assert local_a["creator"] == "演员A"
        assert local_a["local_metadata_enriched"] is True

        assert local_b["title"] == "JAVBUS 首条标题"
        assert local_b["creator"] == "演员B"
        assert local_b["local_metadata_enriched"] is True

        assert bool(local_c.get("local_metadata_enriched", False)) is False

        assert "标签甲" in tag_names
        assert "标签乙" in tag_names
        assert "标签丙" in tag_names
    finally:
        save_json(videos_path, original_videos)
        save_json(tags_path, original_tags)


@pytest.mark.integration
def test_video_local_metadata_refresh_updates_single_local_record_and_appends_tags(
    third_party_client,
    monkeypatch,
):
    client = third_party_client["client"]
    meta_dir: Path = third_party_client["meta_dir"]
    video_service_module = third_party_client["video_service_module"]

    videos_path = meta_dir / "videos_database.json"
    tags_path = meta_dir / "tags_database.json"
    original_videos = load_json(videos_path)
    original_tags = load_json(tags_path)

    class FakeAdapter:
        def __init__(self, platform_name: str):
            self.platform_name = platform_name

        def search_videos(self, keyword, page=1, max_pages=1):
            code = str(keyword or "").strip().upper()
            if self.platform_name == "javdb" and code == "ABP-111":
                return {"videos": [{"video_id": "JAVDB_111", "title": "Remote title"}]}
            return {"videos": []}

        def get_video_detail(self, video_id, movie_type=None):
            if str(video_id or "").strip().upper() != "JAVDB_111":
                return {}
            return {
                "video_id": "JAVDB_111",
                "code": "ABP-111",
                "title": "Remote Updated Title",
                "date": "2026-01-01",
                "series": "Remote Series",
                "actors": ["Actor Remote"],
                "tags": ["ManualTag", "NewRemoteTag"],
                "cover_url": "https://example.com/remote-cover.jpg",
                "thumbnail_images": ["https://example.com/remote-thumb-1.jpg"],
                "preview_video": "https://example.com/remote-preview.mp4",
            }

    monkeypatch.setattr(
        video_service_module.VideoAppService,
        "_build_video_metadata_adapters",
        lambda self: {"javdb": FakeAdapter("javdb"), "javbus": FakeAdapter("javbus")},
    )
    monkeypatch.setattr(video_service_module.VideoAppService, "cache_cover_to_static_async", lambda *args, **kwargs: None)
    monkeypatch.setattr(video_service_module.VideoAppService, "cache_thumbnail_images_async", lambda *args, **kwargs: None)
    monkeypatch.setattr(video_service_module.VideoAppService, "cache_preview_video_async", lambda *args, **kwargs: None)

    try:
        save_json(
            videos_path,
            {
                "collection_name": "Test Videos",
                "user": "test-user",
                "total_videos": 2,
                "last_updated": "2026-04-01",
                "videos": [
                    {
                        "id": "LOCALV_A",
                        "code": "ABP-111",
                        "title": "Local Original Title",
                        "creator": "",
                        "actors": [],
                        "tag_ids": ["tag_video_manual"],
                        "is_deleted": False,
                    },
                    {
                        "id": "LOCALV_B",
                        "code": "ABP-222",
                        "title": "Other Local",
                        "creator": "",
                        "actors": [],
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
                    {"id": "tag_video_manual", "name": "ManualTag", "content_type": "video", "create_time": "2026-04-01T00:00:00"},
                ],
            },
        )

        resp = client.post(
            "/api/v1/video/local-metadata/refresh",
            json={"video_id": "LOCALV_A"},
        )
        payload = resp.get_json()
        assert resp.status_code == 200
        assert payload["code"] == 200

        data = payload["data"] or {}
        assert data["id"] == "LOCALV_A"
        assert data["title"] == "Remote Updated Title"
        assert data["creator"] == "Actor Remote"
        assert data["metadata_refresh"]["matched_platform"] == "javdb"
        assert data["metadata_refresh"]["search_platform_order"] == ["javdb", "javbus"]
        assert data["metadata_refresh"]["bound_tags"] >= 1

        refreshed_videos = load_json(videos_path).get("videos") or []
        refreshed_tags = load_json(tags_path).get("tags") or []
        tag_names = {str(tag.get("name") or "") for tag in refreshed_tags}

        local_a = find_by_id(refreshed_videos, "LOCALV_A")
        local_b = find_by_id(refreshed_videos, "LOCALV_B")
        assert local_a is not None
        assert local_b is not None
        assert local_a["local_metadata_enriched"] is True
        assert "tag_video_manual" in (local_a.get("tag_ids") or [])
        assert "NewRemoteTag" in tag_names
        assert local_b["title"] == "Other Local"
    finally:
        save_json(videos_path, original_videos)
        save_json(tags_path, original_tags)
