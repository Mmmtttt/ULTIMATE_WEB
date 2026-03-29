from __future__ import annotations

import base64
from pathlib import Path

import pytest
import requests

from tests.shared.runtime_data import load_json, save_json


JPEG_1X1 = base64.b64decode(
    "/9j/4AAQSkZJRgABAQAAAQABAAD/2wCEAAkGBxISEhUTEhIVFhUVFRUVFRUVFRUVFRUVFRUXFhUV"
    "FRUYHSggGBolGxUVITEhJSkrLi4uFx8zODMtNygtLisBCgoKDg0OFQ8PFS0dFR0tLS0tLS0tLS0tLS0t"
    "LS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLf/AABEIAAEAAQMBIgACEQEDEQH/xAAXAAEB"
    "AQEAAAAAAAAAAAAAAAAAAQID/8QAFhEBAQEAAAAAAAAAAAAAAAAAAAER/9oADAMBAAIQAxAAAAG8gP/"
    "EABgQAQEAAwAAAAAAAAAAAAAAAAERAAIx/9oACAEBAAEFAjJkWf/EABYRAQEBAAAAAAAAAAAAAAAAAAAB"
    "Ef/aAAgBAwEBPwGn/8QAFhEBAQEAAAAAAAAAAAAAAAAAABEh/9oACAECAQE/Acf/xAAaEAADAQEBAQAAAA"
    "AAAAAAAAABAhEAITFB/9oACAEBAAY/Aq4mV6P/xAAbEAACAgMBAAAAAAAAAAAAAAABEQAhMUFhcf/aAAgB"
    "AQABPyFq2hQ6dYF2jP/Z"
)


def _append_cached_recommendation(meta_dir: Path, data_dir: Path, recommendation_id: str) -> None:
    recommendation_path = meta_dir / "recommendations_database.json"
    payload = load_json(recommendation_path)
    recommendations = payload.setdefault("recommendations", [])

    recommendations.append(
        {
            "id": recommendation_id,
            "title": "E2E Preview Cached Comic",
            "title_jp": "",
            "author": "Preview Author",
            "desc": "cached preview entry",
            "cover_path": "",
            "total_page": 1,
            "current_page": 1,
            "score": 9.2,
            "tag_ids": ["tag_action"],
            "list_ids": [],
            "create_time": "2026-03-29T00:00:00",
            "last_read_time": "2026-03-29T00:00:00",
            "is_deleted": False,
            "preview_image_urls": [],
            "preview_pages": [1],
        }
    )
    payload["total_recommendations"] = len(recommendations)
    save_json(recommendation_path, payload)

    original_id = recommendation_id.replace("JM", "", 1)
    cache_dir = data_dir / "recommendation_cache" / "comic" / "JM" / original_id
    cache_dir.mkdir(parents=True, exist_ok=True)
    (cache_dir / "001.jpg").write_bytes(JPEG_1X1)


def _append_cached_video_recommendation(meta_dir: Path, data_dir: Path, video_id: str) -> None:
    recommendation_path = meta_dir / "video_recommendations_database.json"
    payload = load_json(recommendation_path)
    recommendations = payload.setdefault("video_recommendations", [])

    cover_path_local = f"/media/recommendation_cache/video/JAVDB/{video_id.replace('JAVDB', '', 1)}/cover.jpg"
    recommendations.append(
        {
            "id": video_id,
            "title": "E2E Preview Cached Video",
            "creator": "Preview Video Creator",
            "desc": "cached preview video entry",
            "cover_path": "",
            "cover_path_local": cover_path_local,
            "thumbnail_images": [],
            "thumbnail_images_local": [],
            "preview_video": "",
            "preview_video_local": "",
            "total_units": 1,
            "current_unit": 1,
            "score": 9.4,
            "tag_ids": ["tag_video"],
            "list_ids": [],
            "create_time": "2026-03-29T00:00:00",
            "last_access_time": "2026-03-29T00:00:00",
            "is_deleted": False,
            "actors": ["Actor Preview"],
        }
    )
    payload["total_video_recommendations"] = len(recommendations)
    save_json(recommendation_path, payload)

    asset_path = data_dir / "recommendation_cache" / "video" / "JAVDB" / video_id.replace("JAVDB", "", 1) / "cover.jpg"
    asset_path.parent.mkdir(parents=True, exist_ok=True)
    asset_path.write_bytes(JPEG_1X1)


def _create_session(base_url: str, mode: str) -> dict:
    response = requests.post(
        f"{base_url}/api/v1/feed/session",
        json={"mode": mode},
        timeout=5,
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 200
    assert payload["data"]["session_id"]
    return payload["data"]


def _fetch_items(base_url: str, session_id: str, limit: int = 24) -> list[dict]:
    response = requests.get(
        f"{base_url}/api/v1/feed/items",
        params={"session_id": session_id, "limit": limit},
        timeout=5,
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 200
    return payload["data"]["items"]


@pytest.mark.integration
def test_random_feed_comic_session_returns_infinite_like_batch(integration_runtime):
    base_url = integration_runtime["base_url"]

    session = _create_session(base_url, "comic")
    assert session["mode"] == "comic"
    assert session["candidate_count"] >= 1

    items = _fetch_items(base_url, session["session_id"], limit=30)
    assert len(items) == 30
    assert all(item["mode"] == "comic" for item in items)
    assert all(item["sequence_index"] >= 1 for item in items)
    assert all("detail_route_name" in item for item in items)


@pytest.mark.integration
def test_random_feed_refresh_resets_cursor(integration_runtime):
    base_url = integration_runtime["base_url"]

    session = _create_session(base_url, "comic")
    items_before = _fetch_items(base_url, session["session_id"], limit=3)
    assert [item["sequence_index"] for item in items_before] == [1, 2, 3]

    refresh_resp = requests.post(
        f"{base_url}/api/v1/feed/session/refresh",
        json={"session_id": session["session_id"]},
        timeout=5,
    )
    assert refresh_resp.status_code == 200
    refresh_payload = refresh_resp.json()
    assert refresh_payload["code"] == 200

    items_after = _fetch_items(base_url, session["session_id"], limit=2)
    assert [item["sequence_index"] for item in items_after] == [1, 2]


@pytest.mark.integration
def test_random_feed_comic_includes_cached_preview_candidates(integration_runtime):
    base_url = integration_runtime["base_url"]
    meta_dir = integration_runtime["meta_dir"]
    data_dir = integration_runtime["data_dir"]
    preview_id = "JM990001"

    _append_cached_recommendation(meta_dir, data_dir, preview_id)

    session = _create_session(base_url, "comic")
    assert session["candidate_count"] >= 2

    items = _fetch_items(base_url, session["session_id"], limit=120)
    preview_items = [item for item in items if item.get("source") == "preview"]
    assert preview_items, "expected cached preview recommendations to appear in random feed"
    assert any(
        f"recommendation_id={preview_id}" in str(item.get("image_url", ""))
        for item in preview_items
    )


@pytest.mark.integration
def test_random_feed_video_includes_local_and_cached_preview_assets(integration_runtime):
    base_url = integration_runtime["base_url"]
    meta_dir = integration_runtime["meta_dir"]
    data_dir = integration_runtime["data_dir"]
    preview_video_id = "JAVDB990001"

    _append_cached_video_recommendation(meta_dir, data_dir, preview_video_id)

    session = _create_session(base_url, "video")
    assert session["mode"] == "video"
    assert session["candidate_count"] >= 2

    items = _fetch_items(base_url, session["session_id"], limit=120)
    assert items
    assert all(item["mode"] == "video" for item in items)
    assert any(item.get("source") == "local" for item in items)
    assert any(item.get("source") == "preview" for item in items)
    assert any(
        f"/media/recommendation_cache/video/JAVDB/{preview_video_id.replace('JAVDB', '', 1)}/cover.jpg"
        in str(item.get("image_url", ""))
        for item in items
    )

