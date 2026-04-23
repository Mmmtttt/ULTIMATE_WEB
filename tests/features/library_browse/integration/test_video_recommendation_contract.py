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
    finally:
        save_json(db_path, original_payload)
