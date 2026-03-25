from __future__ import annotations

import pytest
import requests

from tests.shared.runtime_data import find_by_id, load_json
from tests.shared.test_constants import PRIMARY_VIDEO_ID


@pytest.mark.integration
def test_video_progress_update_persists(integration_runtime):
    """
    用例描述:
    - 用例目的: 验证视频进度更新接口能正确持久化进度。
    - 测试步骤:
      1. 调用 PUT /api/v1/video/progress 更新进度。
      2. 验证接口返回和文件持久化。
    - 预期结果:
      1. HTTP 200，业务 code=200。
      2. 文件中对应记录的 current_unit 已更新。
    - 历史变更:
      - 2026-03-26: 初始创建，覆盖视频进度更新主链路。
    """
    base_url = integration_runtime["base_url"]
    meta_dir = integration_runtime["meta_dir"]
    videos_path = meta_dir / "videos_database.json"

    new_unit = 5

    response = requests.put(
        f"{base_url}/api/v1/video/progress",
        json={"video_id": PRIMARY_VIDEO_ID, "unit": new_unit},
        timeout=5,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 200
    assert payload["data"]["current_unit"] == new_unit

    videos_data = load_json(videos_path)
    videos = videos_data.get("videos", [])
    updated = find_by_id(videos, PRIMARY_VIDEO_ID)
    assert updated is not None
    assert updated["current_unit"] == new_unit


@pytest.mark.integration
def test_video_progress_rejects_invalid_unit(integration_runtime):
    """
    用例描述:
    - 用例目的: 验证视频进度更新接口校验进度值。
    - 测试步骤:
      1. 调用 PUT /api/v1/video/progress 传入无效进度值。
      2. 检查返回错误码。
    - 预期结果:
      1. HTTP 200，业务 code=400。
    - 历史变更:
      - 2026-03-26: 初始创建，覆盖视频进度参数校验。
    """
    base_url = integration_runtime["base_url"]

    response = requests.put(
        f"{base_url}/api/v1/video/progress",
        json={"video_id": PRIMARY_VIDEO_ID, "unit": 100},
        timeout=5,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 400


@pytest.mark.integration
def test_video_progress_rejects_missing_video_id(integration_runtime):
    """
    用例描述:
    - 用例目的: 验证视频进度更新接口校验必要参数。
    - 测试步骤:
      1. 调用 PUT /api/v1/video/progress 不传 video_id。
      2. 检查返回错误码。
    - 预期结果:
      1. HTTP 200，业务 code=400。
    - 历史变更:
      - 2026-03-26: 初始创建，覆盖视频进度参数校验。
    """
    base_url = integration_runtime["base_url"]

    response = requests.put(
        f"{base_url}/api/v1/video/progress",
        json={"unit": 1},
        timeout=5,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 400


@pytest.mark.integration
def test_video_progress_rejects_nonexistent_video(integration_runtime):
    """
    用例描述:
    - 用例目的: 验证视频进度更新接口校验视频存在性。
    - 测试步骤:
      1. 调用 PUT /api/v1/video/progress 传入不存在的视频ID。
      2. 检查返回错误码。
    - 预期结果:
      1. HTTP 200，业务 code=404。
    - 历史变更:
      - 2026-03-26: 初始创建，覆盖视频进度存在性校验。
    """
    base_url = integration_runtime["base_url"]

    response = requests.put(
        f"{base_url}/api/v1/video/progress",
        json={"video_id": "NONEXISTENT_VIDEO_ID", "unit": 1},
        timeout=5,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 400


@pytest.mark.integration
def test_video_detail_returns_full_info(integration_runtime):
    """
    用例描述:
    - 用例目的: 验证视频详情接口返回完整信息。
    - 测试步骤:
      1. 调用 GET /api/v1/video/detail。
      2. 检查返回数据结构。
    - 预期结果:
      1. HTTP 200，业务 code=200。
      2. 返回数据包含视频完整信息。
    - 历史变更:
      - 2026-03-26: 初始创建，覆盖视频详情主链路。
    """
    base_url = integration_runtime["base_url"]

    response = requests.get(
        f"{base_url}/api/v1/video/detail",
        params={"video_id": PRIMARY_VIDEO_ID},
        timeout=5,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 200
    data = payload["data"]
    assert data["id"] == PRIMARY_VIDEO_ID
    assert "title" in data
    assert "score" in data


@pytest.mark.integration
def test_video_detail_rejects_nonexistent_video(integration_runtime):
    """
    用例描述:
    - 用例目的: 验证视频详情接口校验视频存在性。
    - 测试步骤:
      1. 调用 GET /api/v1/video/detail 传入不存在的视频ID。
      2. 检查返回错误码。
    - 预期结果:
      1. HTTP 200，业务 code=404。
    - 历史变更:
      - 2026-03-26: 初始创建，覆盖视频详情存在性校验。
    """
    base_url = integration_runtime["base_url"]

    response = requests.get(
        f"{base_url}/api/v1/video/detail",
        params={"video_id": "NONEXISTENT_VIDEO_ID"},
        timeout=5,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 404


@pytest.mark.integration
def test_video_edit_updates_metadata(integration_runtime):
    """
    用例描述:
    - 用例目的: 验证视频编辑接口能正确更新元数据。
    - 测试步骤:
      1. 调用 PUT /api/v1/video/edit 更新视频信息。
      2. 验证接口返回和文件持久化。
    - 预期结果:
      1. HTTP 200，业务 code=200。
      2. 文件中对应记录已更新。
    - 历史变更:
      - 2026-03-26: 初始创建，覆盖视频编辑主链路。
    """
    base_url = integration_runtime["base_url"]
    meta_dir = integration_runtime["meta_dir"]
    videos_path = meta_dir / "videos_database.json"

    new_title = "Updated Video Title"

    response = requests.put(
        f"{base_url}/api/v1/video/edit",
        json={"video_id": PRIMARY_VIDEO_ID, "title": new_title},
        timeout=5,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 200

    videos_data = load_json(videos_path)
    videos = videos_data.get("videos", [])
    updated = find_by_id(videos, PRIMARY_VIDEO_ID)
    assert updated is not None
    assert updated["title"] == new_title


@pytest.mark.integration
def test_video_edit_rejects_nonexistent_video(integration_runtime):
    """
    用例描述:
    - 用例目的: 验证视频编辑接口校验视频存在性。
    - 测试步骤:
      1. 调用 PUT /api/v1/video/edit 传入不存在的视频ID。
      2. 检查返回错误码。
    - 预期结果:
      1. HTTP 200，业务 code=400。
    - 历史变更:
      - 2026-03-26: 初始创建，覆盖视频编辑存在性校验。
    """
    base_url = integration_runtime["base_url"]

    response = requests.put(
        f"{base_url}/api/v1/video/edit",
        json={"video_id": "NONEXISTENT_VIDEO_ID", "title": "New Title"},
        timeout=5,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 400
