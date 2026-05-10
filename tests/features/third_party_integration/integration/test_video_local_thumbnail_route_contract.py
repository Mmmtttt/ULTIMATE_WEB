from __future__ import annotations

import importlib

import pytest


@pytest.mark.integration
def test_generate_local_thumbnails_route_forwards_video_id_to_service(third_party_client, monkeypatch):
    client = third_party_client["client"]
    video_api = third_party_client["video_api"]
    ServiceResult = importlib.import_module("infrastructure.common.result").ServiceResult
    captured = {}

    def fake_generate(video_id: str):
        captured["video_id"] = video_id
        return ServiceResult.ok(
            {
                "id": video_id,
                "thumbnail_images_local": ["/media/video/LOCAL/demo/thumbs/thumb-0001.jpg"],
                "cover_path_local": "/media/video/LOCAL/demo/cover.jpg",
                "local_cover_thumbnail_index": 0,
                "local_thumbnail_capability": {
                    "supported": True,
                    "can_generate": True,
                    "can_select_cover": True,
                    "generated_count": 1,
                    "target_count": 20,
                    "selected_index": 0,
                    "reason": "",
                },
            },
            "缩略图生成成功",
        )

    monkeypatch.setattr(video_api.video_service, "generate_local_video_thumbnails", fake_generate)

    response = client.post(
        "/api/v1/video/local-thumbnails/generate",
        json={"video_id": "LOCALV_ROUTE001"},
    )
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["code"] == 200
    assert payload["data"]["id"] == "LOCALV_ROUTE001"
    assert captured == {"video_id": "LOCALV_ROUTE001"}


@pytest.mark.integration
def test_select_local_thumbnail_cover_route_forwards_index_to_service(third_party_client, monkeypatch):
    client = third_party_client["client"]
    video_api = third_party_client["video_api"]
    ServiceResult = importlib.import_module("infrastructure.common.result").ServiceResult
    captured = {}

    def fake_select(video_id: str, thumbnail_index: int):
        captured["video_id"] = video_id
        captured["thumbnail_index"] = thumbnail_index
        return ServiceResult.ok(
            {
                "id": video_id,
                "thumbnail_images_local": ["/media/video/LOCAL/demo/thumbs/thumb-0001.jpg"],
                "cover_path_local": "/media/video/LOCAL/demo/cover.jpg",
                "local_cover_thumbnail_index": thumbnail_index,
            },
            "封面已更新",
        )

    monkeypatch.setattr(video_api.video_service, "select_local_thumbnail_as_cover", fake_select)

    response = client.put(
        "/api/v1/video/local-thumbnails/cover",
        json={"video_id": "LOCALV_ROUTE002", "thumbnail_index": 3},
    )
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["code"] == 200
    assert payload["data"]["local_cover_thumbnail_index"] == 3
    assert captured == {"video_id": "LOCALV_ROUTE002", "thumbnail_index": 3}
