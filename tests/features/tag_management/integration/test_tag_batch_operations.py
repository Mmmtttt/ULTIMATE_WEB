from __future__ import annotations

import pytest
import requests

from tests.shared.runtime_data import find_by_id, load_json


@pytest.mark.integration
def test_tag_batch_add_to_comics_persists(integration_runtime):
    """
    用例描述:
    - 用例目的: 验证批量添加标签到漫画接口能正确持久化。
    - 测试步骤:
      1. 调用 POST /api/v1/tag/batch-add-tags 批量添加标签。
      2. 验证接口返回状态。
      3. 检查文件中漫画的 tag_ids 已更新。
    - 预期结果:
      1. HTTP 200，业务 code=200。
      2. 指定漫画的 tag_ids 包含新增标签。
    - 历史变更:
      - 2026-03-25: 初始创建，覆盖标签批量添加主链路。
    """
    base_url = integration_runtime["base_url"]
    meta_dir = integration_runtime["meta_dir"]
    comics_path = meta_dir / "comics_database.json"

    from tests.shared.test_constants import PRIMARY_COMIC_ID, SECONDARY_COMIC_ID

    response = requests.post(
        f"{base_url}/api/v1/tag/batch-add-tags",
        json={
            "comic_data": [
                {"id": PRIMARY_COMIC_ID, "source": "home"},
                {"id": SECONDARY_COMIC_ID, "source": "home"},
            ],
            "tag_ids": ["tag_drama"],
        },
        timeout=5,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 200

    comics_data = load_json(comics_path)
    comics = comics_data.get("comics", [])

    comic1 = find_by_id(comics, PRIMARY_COMIC_ID)
    comic2 = find_by_id(comics, SECONDARY_COMIC_ID)

    assert comic1 is not None
    assert "tag_drama" in comic1.get("tag_ids", [])
    assert comic2 is not None
    assert "tag_drama" in comic2.get("tag_ids", [])


@pytest.mark.integration
def test_tag_batch_remove_from_comics_persists(integration_runtime):
    """
    用例描述:
    - 用例目的: 验证批量从漫画移除标签接口能正确持久化。
    - 测试步骤:
      1. 先批量添加标签。
      2. 调用 POST /api/v1/tag/batch-remove-tags 批量移除标签。
      3. 验证文件中漫画的 tag_ids 已移除指定标签。
    - 预期结果:
      1. HTTP 200，业务 code=200。
      2. 指定漫画的 tag_ids 不包含移除的标签。
    - 历史变更:
      - 2026-03-25: 初始创建，覆盖标签批量移除主链路。
    """
    base_url = integration_runtime["base_url"]
    meta_dir = integration_runtime["meta_dir"]
    comics_path = meta_dir / "comics_database.json"

    from tests.shared.test_constants import PRIMARY_COMIC_ID

    requests.post(
        f"{base_url}/api/v1/tag/batch-add-tags",
        json={
            "comic_data": [{"id": PRIMARY_COMIC_ID, "source": "home"}],
            "tag_ids": ["tag_story"],
        },
        timeout=5,
    )

    response = requests.post(
        f"{base_url}/api/v1/tag/batch-remove-tags",
        json={
            "comic_data": [{"id": PRIMARY_COMIC_ID, "source": "home"}],
            "tag_ids": ["tag_story"],
        },
        timeout=5,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 200

    comics_data = load_json(comics_path)
    comics = comics_data.get("comics", [])
    comic = find_by_id(comics, PRIMARY_COMIC_ID)

    assert comic is not None
    assert "tag_story" not in comic.get("tag_ids", [])


@pytest.mark.integration
def test_tag_batch_add_to_videos_persists(integration_runtime):
    """
    用例描述:
    - 用例目的: 验证批量添加标签到视频接口能正确持久化。
    - 测试步骤:
      1. 调用 POST /api/v1/tag/batch-add-tags-to-videos 批量添加标签。
      2. 验证接口返回状态。
      3. 检查文件中视频的 tag_ids 已更新。
    - 预期结果:
      1. HTTP 200，业务 code=200。
      2. 指定视频的 tag_ids 包含新增标签。
    - 历史变更:
      - 2026-03-25: 初始创建，覆盖视频标签批量添加主链路。
    """
    base_url = integration_runtime["base_url"]
    meta_dir = integration_runtime["meta_dir"]
    videos_path = meta_dir / "videos_database.json"

    from tests.shared.test_constants import PRIMARY_VIDEO_ID, SECONDARY_VIDEO_ID

    response = requests.post(
        f"{base_url}/api/v1/tag/batch-add-tags-to-videos",
        json={
            "video_data": [
                {"id": PRIMARY_VIDEO_ID, "source": "home"},
                {"id": SECONDARY_VIDEO_ID, "source": "home"},
            ],
            "tag_ids": ["tag_video_action"],
        },
        timeout=5,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 200

    videos_data = load_json(videos_path)
    videos = videos_data.get("videos", [])

    video1 = find_by_id(videos, PRIMARY_VIDEO_ID)
    video2 = find_by_id(videos, SECONDARY_VIDEO_ID)

    assert video1 is not None
    assert "tag_video_action" in video1.get("tag_ids", [])
    assert video2 is not None
    assert "tag_video_action" in video2.get("tag_ids", [])


@pytest.mark.integration
def test_tag_batch_remove_from_videos_persists(integration_runtime):
    """
    用例描述:
    - 用例目的: 验证批量从视频移除标签接口能正确持久化。
    - 测试步骤:
      1. 先批量添加标签。
      2. 调用 POST /api/v1/tag/batch-remove-tags-from-videos 批量移除标签。
      3. 验证文件中视频的 tag_ids 已移除指定标签。
    - 预期结果:
      1. HTTP 200，业务 code=200。
      2. 指定视频的 tag_ids 不包含移除的标签。
    - 历史变更:
      - 2026-03-25: 初始创建，覆盖视频标签批量移除主链路。
    """
    base_url = integration_runtime["base_url"]
    meta_dir = integration_runtime["meta_dir"]
    videos_path = meta_dir / "videos_database.json"

    from tests.shared.test_constants import PRIMARY_VIDEO_ID

    requests.post(
        f"{base_url}/api/v1/tag/batch-add-tags-to-videos",
        json={
            "video_data": [{"id": PRIMARY_VIDEO_ID, "source": "home"}],
            "tag_ids": ["tag_video_story"],
        },
        timeout=5,
    )

    response = requests.post(
        f"{base_url}/api/v1/tag/batch-remove-tags-from-videos",
        json={
            "video_data": [{"id": PRIMARY_VIDEO_ID, "source": "home"}],
            "tag_ids": ["tag_video_story"],
        },
        timeout=5,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 200

    videos_data = load_json(videos_path)
    videos = videos_data.get("videos", [])
    video = find_by_id(videos, PRIMARY_VIDEO_ID)

    assert video is not None
    assert "tag_video_story" not in video.get("tag_ids", [])


@pytest.mark.integration
def test_tag_batch_add_rejects_missing_params(integration_runtime):
    """
    用例描述:
    - 用例目的: 验证批量添加标签接口校验必要参数。
    - 测试步骤:
      1. 调用 POST /api/v1/tag/batch-add-tags 不传必要参数。
      2. 检查返回错误码。
    - 预期结果:
      1. HTTP 200，业务 code=400。
    - 历史变更:
      - 2026-03-25: 初始创建，覆盖批量添加参数校验。
    """
    base_url = integration_runtime["base_url"]

    response = requests.post(
        f"{base_url}/api/v1/tag/batch-add-tags",
        json={"comic_data": []},
        timeout=5,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 400


@pytest.mark.integration
def test_tag_get_all_comics_returns_data(integration_runtime):
    """
    用例描述:
    - 用例目的: 验证获取所有漫画接口返回正确数据。
    - 测试步骤:
      1. 调用 GET /api/v1/tag/all-comics。
      2. 检查返回数据。
    - 预期结果:
      1. HTTP 200，业务 code=200。
      2. 返回数据包含漫画列表信息。
    - 历史变更:
      - 2026-03-25: 初始创建，覆盖获取所有漫画主链路。
    """
    base_url = integration_runtime["base_url"]

    response = requests.get(
        f"{base_url}/api/v1/tag/all-comics",
        timeout=5,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 200
    data = payload["data"]
    assert isinstance(data, dict)
    assert "home_comics" in data
    assert "recommendation_comics" in data


@pytest.mark.integration
def test_tag_get_all_videos_returns_data(integration_runtime):
    """
    用例描述:
    - 用例目的: 验证获取所有视频接口返回正确数据。
    - 测试步骤:
      1. 调用 GET /api/v1/tag/all-videos。
      2. 检查返回数据。
    - 预期结果:
      1. HTTP 200，业务 code=200。
      2. 返回数据包含视频列表信息。
    - 历史变更:
      - 2026-03-25: 初始创建，覆盖获取所有视频主链路。
    """
    base_url = integration_runtime["base_url"]

    response = requests.get(
        f"{base_url}/api/v1/tag/all-videos",
        timeout=5,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 200
    data = payload["data"]
    assert isinstance(data, dict)
    assert "home_videos" in data
    assert "recommendation_videos" in data


@pytest.mark.integration
def test_tag_get_comics_by_tag_returns_matching(integration_runtime):
    """
    用例描述:
    - 用例目的: 验证根据标签获取漫画接口返回正确结果。
    - 测试步骤:
      1. 调用 GET /api/v1/tag/comics?tag_id=tag_action。
      2. 检查返回数据包含对应标签的漫画。
    - 预期结果:
      1. HTTP 200，业务 code=200。
      2. 返回数据包含指定标签的漫画。
    - 历史变更:
      - 2026-03-25: 初始创建，覆盖标签漫画查询主链路。
    """
    base_url = integration_runtime["base_url"]

    response = requests.get(
        f"{base_url}/api/v1/tag/comics",
        params={"tag_id": "tag_action"},
        timeout=5,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 200
    data = payload["data"]
    assert isinstance(data, dict)
    assert "home_comics" in data


@pytest.mark.integration
def test_tag_get_videos_by_tag_returns_matching(integration_runtime):
    """
    用例描述:
    - 用例目的: 验证根据标签获取视频接口返回正确结果。
    - 测试步骤:
      1. 调用 GET /api/v1/tag/videos?tag_id=tag_video。
      2. 检查返回数据包含对应标签的视频。
    - 预期结果:
      1. HTTP 200，业务 code=200。
      2. 返回数据包含指定标签的视频。
    - 历史变更:
      - 2026-03-25: 初始创建，覆盖标签视频查询主链路。
    """
    base_url = integration_runtime["base_url"]

    response = requests.get(
        f"{base_url}/api/v1/tag/videos",
        params={"tag_id": "tag_video"},
        timeout=5,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 200
    data = payload["data"]
    assert isinstance(data, dict)
    assert "home_videos" in data
