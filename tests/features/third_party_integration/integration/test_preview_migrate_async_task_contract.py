from __future__ import annotations

import importlib

import pytest


@pytest.mark.integration
def test_recommendation_migrate_to_local_route_creates_async_task(third_party_client, monkeypatch):
    """
    Case Description:
    - Purpose: Guard preview-comic migrate route contract, ensuring it only creates async import tasks.
    - Steps:
      1. Mock `task_manager.create_task`.
      2. Call `POST /api/v1/recommendation/migrate-to-local` with recommendation IDs.
      3. Assert async task payload contract.
    - Expected:
      1. Route returns `task_id` instead of synchronous migrate stats.
      2. Task uses `import_type=migrate_to_local`, `target=home`, `content_type=comic`.
    """
    client = third_party_client["client"]
    task_manager_module = importlib.import_module("infrastructure.task_manager")
    captured = {}

    def fake_create_task(
        platform,
        import_type,
        target,
        comic_id=None,
        keyword=None,
        comic_ids=None,
        content_type="comic",
        extra_data=None,
    ):
        captured.update(
            {
                "platform": platform,
                "import_type": import_type,
                "target": target,
                "comic_id": comic_id,
                "keyword": keyword,
                "comic_ids": comic_ids,
                "content_type": content_type,
                "extra_data": extra_data,
            }
        )
        return "task-rec-migrate-001"

    monkeypatch.setattr(task_manager_module.task_manager, "create_task", fake_create_task)

    response = client.post(
        "/api/v1/recommendation/migrate-to-local",
        json={"recommendation_ids": ["JM_100001", "PK_200002", ""]},
    )
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["code"] == 200
    assert payload["data"]["task_id"] == "task-rec-migrate-001"
    assert payload["data"]["content_type"] == "comic"

    assert captured["platform"] == "JM"
    assert captured["import_type"] == "migrate_to_local"
    assert captured["target"] == "home"
    assert captured["comic_id"] is None
    assert captured["keyword"] is None
    assert captured["comic_ids"] == ["JM_100001", "PK_200002"]
    assert captured["content_type"] == "comic"
    assert captured["extra_data"] == {
        "source": "preview",
        "entry": "recommendation_migrate_to_local",
    }


@pytest.mark.integration
def test_video_recommendation_migrate_to_local_route_creates_async_task(third_party_client, monkeypatch):
    """
    Case Description:
    - Purpose: Guard preview-video migrate route contract, ensuring it only creates async import tasks.
    - Steps:
      1. Mock `task_manager.create_task`.
      2. Call `POST /api/v1/video/recommendation/migrate-to-local` with video IDs.
      3. Assert async task payload contract.
    - Expected:
      1. Route returns `task_id` instead of synchronous migrate stats.
      2. Task uses `import_type=migrate_to_local`, `target=home`, `content_type=video`.
    """
    client = third_party_client["client"]
    task_manager_module = importlib.import_module("infrastructure.task_manager")
    captured = {}

    def fake_create_task(
        platform,
        import_type,
        target,
        comic_id=None,
        keyword=None,
        comic_ids=None,
        content_type="comic",
        extra_data=None,
    ):
        captured.update(
            {
                "platform": platform,
                "import_type": import_type,
                "target": target,
                "comic_id": comic_id,
                "keyword": keyword,
                "comic_ids": comic_ids,
                "content_type": content_type,
                "extra_data": extra_data,
            }
        )
        return "task-video-migrate-001"

    monkeypatch.setattr(task_manager_module.task_manager, "create_task", fake_create_task)

    response = client.post(
        "/api/v1/video/recommendation/migrate-to-local",
        json={"video_ids": ["JAVDB_wKgxKe", "JAVBUS_VEO777", " "]},
    )
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["code"] == 200
    assert payload["data"]["task_id"] == "task-video-migrate-001"
    assert payload["data"]["content_type"] == "video"

    assert captured["platform"] == "JAVDB"
    assert captured["import_type"] == "migrate_to_local"
    assert captured["target"] == "home"
    assert captured["comic_id"] is None
    assert captured["keyword"] is None
    assert captured["comic_ids"] == ["JAVDB_wKgxKe", "JAVBUS_VEO777"]
    assert captured["content_type"] == "video"
    assert captured["extra_data"] == {
        "source": "preview",
        "entry": "video_recommendation_migrate_to_local",
    }
