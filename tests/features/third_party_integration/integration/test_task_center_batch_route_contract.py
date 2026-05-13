from __future__ import annotations

import pytest


@pytest.mark.integration
def test_batch_local_comic_metadata_route_creates_task(third_party_client, monkeypatch):
    client = third_party_client["client"]
    captured = {}

    def fake_create_batch_task(**kwargs):
        captured.update(kwargs)
        return "task-comic-batch"

    task_manager_module = __import__("infrastructure.task_manager", fromlist=["task_manager"])
    monkeypatch.setattr(task_manager_module.task_manager, "create_batch_task", fake_create_batch_task)

    response = client.post(
        "/api/v1/comic/local-metadata/refresh/batch",
        json={"comic_ids": ["LOCALA001", "LOCALA002"]},
    )
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["code"] == 200
    assert payload["data"]["task_id"] == "task-comic-batch"
    assert captured == {
        "task_type": task_manager_module.task_manager.TASK_TYPE_COMIC_LOCAL_METADATA_REFRESH,
        "content_type": "comic",
        "item_ids": ["LOCALA001", "LOCALA002"],
        "title": "批量补全本地漫画信息（2 项）",
    }


@pytest.mark.integration
def test_batch_local_video_metadata_route_creates_task(third_party_client, monkeypatch):
    client = third_party_client["client"]
    captured = {}

    def fake_create_batch_task(**kwargs):
        captured.update(kwargs)
        return "task-video-meta"

    task_manager_module = __import__("infrastructure.task_manager", fromlist=["task_manager"])
    monkeypatch.setattr(task_manager_module.task_manager, "create_batch_task", fake_create_batch_task)

    response = client.post(
        "/api/v1/video/local-metadata/refresh/batch",
        json={"video_ids": ["LOCALV001", "LOCALV002", "LOCALV003"]},
    )
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["code"] == 200
    assert payload["data"]["task_id"] == "task-video-meta"
    assert captured == {
        "task_type": task_manager_module.task_manager.TASK_TYPE_VIDEO_LOCAL_METADATA_REFRESH,
        "content_type": "video",
        "item_ids": ["LOCALV001", "LOCALV002", "LOCALV003"],
        "title": "批量补全本地视频信息（3 项）",
    }


@pytest.mark.integration
def test_batch_local_video_thumbnail_route_creates_task(third_party_client, monkeypatch):
    client = third_party_client["client"]
    captured = {}

    def fake_create_batch_task(**kwargs):
        captured.update(kwargs)
        return "task-video-thumbs"

    task_manager_module = __import__("infrastructure.task_manager", fromlist=["task_manager"])
    monkeypatch.setattr(task_manager_module.task_manager, "create_batch_task", fake_create_batch_task)

    response = client.post(
        "/api/v1/video/local-thumbnails/generate/batch",
        json={"video_ids": ["LOCALV100", "LOCALV101"]},
    )
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["code"] == 200
    assert payload["data"]["task_id"] == "task-video-thumbs"
    assert captured == {
        "task_type": task_manager_module.task_manager.TASK_TYPE_VIDEO_LOCAL_THUMBNAIL_GENERATE,
        "content_type": "video",
        "item_ids": ["LOCALV100", "LOCALV101"],
        "title": "批量生成视频缩略图（2 项）",
    }
