from __future__ import annotations

from pathlib import Path

import pytest
import requests

from tests.shared.runtime_data import find_by_id, load_json, save_json


@pytest.mark.integration
def test_organize_options_returns_mode_specific_actions(integration_runtime):
    base_url = integration_runtime["base_url"]

    comic_resp = requests.get(
        f"{base_url}/api/v1/organize/options",
        params={"mode": "comic"},
        timeout=30,
    )
    assert comic_resp.status_code == 200
    comic_payload = comic_resp.json()
    assert comic_payload["code"] == 200
    comic_data = comic_payload["data"] or {}
    assert comic_data.get("mode") == "comic"

    action_map = {item.get("action"): item for item in (comic_data.get("options") or [])}
    assert {"repair_cover", "deduplicate_by_title", "enrich_local_metadata"}.issubset(set(action_map))
    assert action_map["repair_cover"]["implemented"] is True
    assert action_map["deduplicate_by_title"]["implemented"] is True
    assert action_map["enrich_local_metadata"]["implemented"] is True

    video_resp = requests.get(
        f"{base_url}/api/v1/organize/options",
        params={"mode": "video"},
        timeout=30,
    )
    assert video_resp.status_code == 200
    video_payload = video_resp.json()
    assert video_payload["code"] == 200
    video_data = video_payload["data"] or {}
    assert video_data.get("mode") == "video"
    video_actions = video_data.get("options") or []
    assert len(video_actions) >= 1
    assert any(item.get("implemented") is False for item in video_actions)


@pytest.mark.integration
def test_deduplicate_by_title_keeps_different_chapter_records(integration_runtime):
    base_url = integration_runtime["base_url"]
    meta_dir: Path = integration_runtime["meta_dir"]

    home_path = meta_dir / "comics_database.json"
    recommendation_path = meta_dir / "recommendations_database.json"

    original_home = load_json(home_path)
    original_recommendation = load_json(recommendation_path)

    try:
        home_data = {
            "collection_name": "Test Comics",
            "user": "test-user",
            "total_comics": 3,
            "last_updated": "2026-04-01",
            "comics": [
                {"id": "LOCAL_A", "title": "银河战士 [机翻] 第1话", "is_deleted": False},
                {"id": "LOCAL_B", "title": "银河战士【重置版】第1话", "is_deleted": False},
                {"id": "LOCAL_C", "title": "银河战士 第2话", "is_deleted": False},
            ],
        }
        recommendation_data = {
            "collection_name": "Test Comic Recommendations",
            "user": "test-user",
            "total_recommendations": 3,
            "last_updated": "2026-04-01",
            "recommendations": [
                {"id": "JM900001", "title": "预览样本 第1卷", "is_deleted": False},
                {"id": "JM900002", "title": "预览样本【修订】第1卷", "is_deleted": False},
                {"id": "JM900003", "title": "预览样本 第2卷", "is_deleted": False},
            ],
        }
        save_json(home_path, home_data)
        save_json(recommendation_path, recommendation_data)

        run_resp = requests.post(
            f"{base_url}/api/v1/organize/run",
            json={"mode": "comic", "action": "deduplicate_by_title"},
            timeout=60,
        )
        assert run_resp.status_code == 200
        run_payload = run_resp.json()
        assert run_payload["code"] == 200
        result = run_payload["data"] or {}
        assert (result.get("home") or {}).get("moved_to_trash") == 1
        assert (result.get("recommendation") or {}).get("moved_to_trash") == 1

        refreshed_home = load_json(home_path)
        refreshed_recommendation = load_json(recommendation_path)

        home_comics = refreshed_home.get("comics") or []
        recommendation_comics = refreshed_recommendation.get("recommendations") or []

        assert find_by_id(home_comics, "LOCAL_A")["is_deleted"] is False
        assert find_by_id(home_comics, "LOCAL_B")["is_deleted"] is True
        assert find_by_id(home_comics, "LOCAL_C")["is_deleted"] is False

        assert find_by_id(recommendation_comics, "JM900001")["is_deleted"] is False
        assert find_by_id(recommendation_comics, "JM900002")["is_deleted"] is True
        assert find_by_id(recommendation_comics, "JM900003")["is_deleted"] is False
    finally:
        save_json(home_path, original_home)
        save_json(recommendation_path, original_recommendation)
