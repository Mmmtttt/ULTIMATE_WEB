from __future__ import annotations

import pytest
import requests

from tests.shared.runtime_data import load_json, save_json


@pytest.mark.integration
def test_video_recommendation_list_exposes_protocol_display_metadata(integration_runtime):
    base_url = integration_runtime["base_url"]
    meta_dir = integration_runtime["meta_dir"]
    db_path = meta_dir / "video_recommendations_database.json"

    original_payload = load_json(db_path)

    try:
        payload = {
            "collection_name": "Test Video Recommendations",
            "user": "test-user",
            "total_video_recommendations": 2,
            "last_updated": "2026-04-23",
            "video_recommendations": [
                {
                    "id": "JAVDBPREVIEW900001",
                    "code": "PRE-900001",
                    "title": "Preview Javdb Video",
                    "creator": "Preview Creator A",
                    "actors": ["Actor A"],
                    "cover_path": "/static/cover/JAVDB/900001.jpg",
                    "preview_video": "https://media.example/javdb-preview-900001.mp4",
                    "thumbnail_images": [],
                    "tag_ids": [],
                    "list_ids": [],
                    "create_time": "2026-04-23T12:00:00",
                    "last_read_time": "2026-04-23T12:00:00",
                    "is_deleted": False,
                },
                {
                    "id": "JAVBUSPREVIEWABP123",
                    "code": "ABP-123",
                    "title": "Preview Javbus Video",
                    "creator": "Preview Creator B",
                    "actors": ["Actor B"],
                    "cover_path": "/static/cover/JAVBUS/ABP123.jpg",
                    "preview_video": "",
                    "thumbnail_images": [],
                    "tag_ids": [],
                    "list_ids": [],
                    "create_time": "2026-04-23T12:01:00",
                    "last_read_time": "2026-04-23T12:01:00",
                    "is_deleted": False,
                },
            ],
        }
        save_json(db_path, payload)

        response = requests.get(
            f"{base_url}/api/v1/video/recommendation/list",
            timeout=5,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200

        items = {item["id"]: item for item in (data["data"] or [])}
        assert items["JAVDBPREVIEW900001"]["plugin_id"] == "video.javdb"
        assert ((((items["JAVDBPREVIEW900001"].get("display") or {}).get("cover") or {}).get("aspect_ratio")) == "16 / 9")
        assert items["JAVBUSPREVIEWABP123"]["plugin_id"] == "video.javbus"
        assert ((((items["JAVBUSPREVIEWABP123"].get("display") or {}).get("cover") or {}).get("aspect_ratio")) == "2 / 3")
    finally:
        save_json(db_path, original_payload)


@pytest.mark.integration
def test_video_recommendation_detail_exposes_local_and_remote_preview_assets(integration_runtime):
    base_url = integration_runtime["base_url"]
    data_dir = integration_runtime["data_dir"]
    meta_dir = integration_runtime["meta_dir"]
    db_path = meta_dir / "video_recommendations_database.json"

    original_payload = load_json(db_path)
    preview_relative_path = "video/JAVDB/JAVDBDETAILLOCAL900003/hls/index.m3u8"
    preview_abs_path = data_dir / "video" / "JAVDB" / "JAVDBDETAILLOCAL900003" / "hls" / "index.m3u8"
    preview_abs_path.parent.mkdir(parents=True, exist_ok=True)
    preview_abs_path.write_text("#EXTM3U\n", encoding="utf-8")

    try:
        payload = {
            "collection_name": "Test Video Recommendations",
            "user": "test-user",
            "total_video_recommendations": 1,
            "last_updated": "2026-04-23",
            "video_recommendations": [
                {
                    "id": "JAVDBDETAILLOCAL900003",
                    "code": "PRE-900003",
                    "title": "Preview Detail Javdb Local Video",
                    "creator": "Preview Creator Local Detail",
                    "actors": ["Actor Local Detail"],
                    "cover_path": "/static/cover/JAVDB/900003.jpg",
                    "preview_video": "https://media.example/javdb-preview-900003.m3u8",
                    "preview_video_local": preview_relative_path,
                    "thumbnail_images": [],
                    "tag_ids": [],
                    "list_ids": [],
                    "create_time": "2026-04-23T12:03:00",
                    "last_read_time": "2026-04-23T12:03:00",
                    "is_deleted": False,
                },
            ],
        }
        save_json(db_path, payload)

        response = requests.get(
            f"{base_url}/api/v1/video/recommendation/detail",
            params={"video_id": "JAVDBDETAILLOCAL900003"},
            timeout=5,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        detail = data["data"] or {}
        preview = (detail.get("playback") or {}).get("preview") or {}
        assets = preview.get("assets") or []
        assert preview.get("available") is True
        assert preview.get("default_asset_key") == "preview_local"
        assert [asset.get("key") for asset in assets] == ["preview_local", "preview_remote"]
        assert assets[0]["url"] == "/media/video/JAVDB/JAVDBDETAILLOCAL900003/hls/index.m3u8"
        assert assets[1]["url"] == "https://media.example/javdb-preview-900003.m3u8"
    finally:
        save_json(db_path, original_payload)


@pytest.mark.integration
def test_video_recommendation_detail_exposes_protocol_display_metadata(integration_runtime):
    base_url = integration_runtime["base_url"]
    meta_dir = integration_runtime["meta_dir"]
    db_path = meta_dir / "video_recommendations_database.json"

    original_payload = load_json(db_path)

    try:
        payload = {
            "collection_name": "Test Video Recommendations",
            "user": "test-user",
            "total_video_recommendations": 1,
            "last_updated": "2026-04-23",
            "video_recommendations": [
                {
                    "id": "JAVDBDETAIL900002",
                    "code": "PRE-900002",
                    "title": "Preview Detail Javdb Video",
                    "creator": "Preview Creator Detail",
                    "actors": ["Actor Detail"],
                    "cover_path": "/static/cover/JAVDB/900002.jpg",
                    "preview_video": "https://media.example/javdb-preview-900002.mp4",
                    "thumbnail_images": [],
                    "tag_ids": [],
                    "list_ids": [],
                    "create_time": "2026-04-23T12:02:00",
                    "last_read_time": "2026-04-23T12:02:00",
                    "is_deleted": False,
                },
            ],
        }
        save_json(db_path, payload)

        response = requests.get(
            f"{base_url}/api/v1/video/recommendation/detail",
            params={"video_id": "JAVDBDETAIL900002"},
            timeout=5,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        detail = data["data"]
        assert detail["id"] == "JAVDBDETAIL900002"
        assert detail["plugin_id"] == "video.javdb"
        assert detail["source"] == "preview"
        assert ((((detail.get("display") or {}).get("cover") or {}).get("aspect_ratio")) == "16 / 9")
        playback = detail.get("playback") or {}
        primary = playback.get("primary") or {}
        preview = playback.get("preview") or {}
        assert playback.get("bucket") == "candidate"
        assert primary.get("mode") == "online"
        assert primary.get("supports_play_session") is True
        assert preview.get("available") is True
        assets = preview.get("assets") or []
        assert len(assets) == 1
        assert assets[0]["key"] == "preview_remote"
        assert assets[0]["url"] == "https://media.example/javdb-preview-900002.mp4"
    finally:
        save_json(db_path, original_payload)
