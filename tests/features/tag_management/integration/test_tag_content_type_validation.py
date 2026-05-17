from __future__ import annotations

from uuid import uuid4

import pytest
import requests

from tests.shared.runtime_data import find_by_id, load_json
from tests.shared.test_constants import PRIMARY_COMIC_ID, PRIMARY_VIDEO_ID


@pytest.mark.integration
def test_comic_tag_bind_rejects_video_tags(integration_runtime):
    base_url = integration_runtime["base_url"]
    meta_dir = integration_runtime["meta_dir"]
    comics_path = meta_dir / "comics_database.json"

    before = find_by_id(load_json(comics_path).get("comics", []), PRIMARY_COMIC_ID)
    assert before is not None
    original_tag_ids = list(before.get("tag_ids") or [])

    response = requests.put(
        f"{base_url}/api/v1/comic/tag/bind",
        json={"comic_id": PRIMARY_COMIC_ID, "tag_id_list": original_tag_ids + ["tag_video"]},
        timeout=5,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 400
    assert "标签类型不匹配" in payload["msg"]

    after = find_by_id(load_json(comics_path).get("comics", []), PRIMARY_COMIC_ID)
    assert after is not None
    assert after.get("tag_ids") == original_tag_ids


@pytest.mark.integration
def test_video_tag_bind_rejects_comic_tags(integration_runtime):
    base_url = integration_runtime["base_url"]
    meta_dir = integration_runtime["meta_dir"]
    videos_path = meta_dir / "videos_database.json"

    before = find_by_id(load_json(videos_path).get("videos", []), PRIMARY_VIDEO_ID)
    assert before is not None
    original_tag_ids = list(before.get("tag_ids") or [])

    response = requests.put(
        f"{base_url}/api/v1/video/tag/bind",
        json={"video_id": PRIMARY_VIDEO_ID, "tag_id_list": original_tag_ids + ["tag_action"]},
        timeout=5,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 400
    assert "标签类型不匹配" in payload["msg"]

    after = find_by_id(load_json(videos_path).get("videos", []), PRIMARY_VIDEO_ID)
    assert after is not None
    assert after.get("tag_ids") == original_tag_ids


@pytest.mark.integration
def test_recommendation_tag_bind_rejects_video_tags(integration_runtime):
    base_url = integration_runtime["base_url"]
    meta_dir = integration_runtime["meta_dir"]
    rec_path = meta_dir / "recommendations_database.json"

    rec_id = f"RECTYPE{uuid4().hex[:8]}"
    requests.post(
        f"{base_url}/api/v1/recommendation/add",
        json={"id": rec_id, "title": f"Type Guard {rec_id}"},
        timeout=5,
    )

    response = requests.put(
        f"{base_url}/api/v1/recommendation/tag/bind",
        json={"recommendation_id": rec_id, "tag_id_list": ["tag_action", "tag_video"]},
        timeout=5,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 400
    assert "标签类型不匹配" in payload["msg"]

    after = find_by_id(load_json(rec_path).get("recommendations", []), rec_id)
    assert after is not None
    assert after.get("tag_ids") == []


@pytest.mark.integration
def test_batch_tag_add_rejects_cross_content_type_tags(integration_runtime):
    base_url = integration_runtime["base_url"]

    comic_response = requests.post(
        f"{base_url}/api/v1/tag/batch-add-tags",
        json={
            "comic_data": [{"id": PRIMARY_COMIC_ID, "source": "home"}],
            "tag_ids": ["tag_action", "tag_video"],
        },
        timeout=5,
    )
    assert comic_response.status_code == 200
    comic_payload = comic_response.json()
    assert comic_payload["code"] == 400
    assert "标签类型不匹配" in comic_payload["msg"]

    video_response = requests.post(
        f"{base_url}/api/v1/tag/batch-add-tags-to-videos",
        json={
            "video_data": [{"id": PRIMARY_VIDEO_ID, "source": "home"}],
            "tag_ids": ["tag_video", "tag_action"],
        },
        timeout=5,
    )
    assert video_response.status_code == 200
    video_payload = video_response.json()
    assert video_payload["code"] == 400
    assert "标签类型不匹配" in video_payload["msg"]
