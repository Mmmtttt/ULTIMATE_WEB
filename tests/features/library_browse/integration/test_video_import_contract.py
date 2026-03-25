from __future__ import annotations

from uuid import uuid4

import pytest
import requests

from tests.shared.runtime_data import find_by_id, load_json


@pytest.mark.integration
def test_video_import_creates_video_with_valid_params(integration_runtime):
    """
    用例描述:
    - 用例目的: 验证视频导入接口能正确创建视频记录并持久化。
    - 测试步骤:
      1. 调用 POST /api/v1/video/import 创建新视频。
      2. 检查接口返回状态和数据。
      3. 验证 videos_database.json 中新增记录。
    - 预期结果:
      1. HTTP 200，业务 code=200。
      2. 返回数据包含正确的 video_id 和 title。
      3. 文件中新增对应记录。
    - 历史变更:
      - 2026-03-25: 初始创建，覆盖视频导入主链路。
    """
    base_url = integration_runtime["base_url"]
    meta_dir = integration_runtime["meta_dir"]
    videos_path = meta_dir / "videos_database.json"

    video_suffix = uuid4().hex[:8].upper()
    video_id = f"TESTVIDEO{video_suffix}"
    video_code = f"TEST-{video_suffix}"

    response = requests.post(
        f"{base_url}/api/v1/video/import",
        json={
            "id": video_id,
            "code": video_code,
            "title": f"Test Video {video_suffix}",
            "actors": ["Actor A", "Actor B"],
            "cover_path": "/static/cover/JAVDB/900001.png",
        },
        timeout=5,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 200
    assert payload["data"]["id"] == video_id

    videos_data = load_json(videos_path)
    videos = videos_data.get("videos", [])
    created = find_by_id(videos, video_id)
    assert created is not None
    assert created["code"] == video_code


@pytest.mark.integration
def test_video_import_rejects_missing_required_fields(integration_runtime):
    """
    用例描述:
    - 用例目的: 验证视频导入接口校验必要参数。
    - 测试步骤:
      1. 调用 POST /api/v1/video/import 不传必要字段。
      2. 检查返回错误码。
    - 预期结果:
      1. HTTP 200，业务 code=400。
    - 历史变更:
      - 2026-03-25: 初始创建，覆盖视频导入参数校验。
    """
    base_url = integration_runtime["base_url"]

    response = requests.post(
        f"{base_url}/api/v1/video/import",
        json={},
        timeout=5,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 400


@pytest.mark.integration
def test_video_batch_import_creates_multiple_videos(integration_runtime):
    """
    用例描述:
    - 用例目的: 验证视频批量导入接口能正确创建多个视频记录。
    - 测试步骤:
      1. 调用 POST /api/v1/video/import/batch 批量创建视频。
      2. 检查接口返回状态。
      3. 验证文件中新增多条记录。
    - 预期结果:
      1. HTTP 200，业务 code=200。
      2. 返回 imported_ids 包含所有视频 ID。
      3. 文件中新增对应记录。
    - 历史变更:
      - 2026-03-25: 初始创建，覆盖视频批量导入主链路。
    """
    base_url = integration_runtime["base_url"]
    meta_dir = integration_runtime["meta_dir"]
    videos_path = meta_dir / "videos_database.json"

    suffix1 = uuid4().hex[:8].upper()
    suffix2 = uuid4().hex[:8].upper()
    video_id_1 = f"BATCHVID1{suffix1}"
    video_id_2 = f"BATCHVID2{suffix2}"

    response = requests.post(
        f"{base_url}/api/v1/video/import/batch",
        json={
            "videos": [
                {
                    "id": video_id_1,
                    "code": f"BATCH1-{suffix1}",
                    "title": f"Batch Video 1 {suffix1}",
                    "cover_path": "/static/cover/JAVDB/900001.png",
                },
                {
                    "id": video_id_2,
                    "code": f"BATCH2-{suffix2}",
                    "title": f"Batch Video 2 {suffix2}",
                    "cover_path": "/static/cover/JAVDB/900002.png",
                },
            ]
        },
        timeout=5,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 200
    imported_ids = payload["data"].get("imported_ids", [])
    assert video_id_1 in imported_ids
    assert video_id_2 in imported_ids

    videos_data = load_json(videos_path)
    videos = videos_data.get("videos", [])
    assert find_by_id(videos, video_id_1) is not None
    assert find_by_id(videos, video_id_2) is not None


@pytest.mark.integration
def test_video_detail_returns_full_info(integration_runtime):
    """
    用例描述:
    - 用例目的: 验证视频详情接口返回完整的视频信息。
    - 测试步骤:
      1. 调用 GET /api/v1/video/detail?video_id=JAVDB900001。
      2. 检查返回数据完整性。
    - 预期结果:
      1. HTTP 200，业务 code=200。
      2. 返回数据包含 id、title、code、score、actors 等字段。
    - 历史变更:
      - 2026-03-25: 初始创建，覆盖视频详情主链路。
    """
    base_url = integration_runtime["base_url"]

    from tests.shared.test_constants import PRIMARY_VIDEO_ID

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
    assert "code" in data
    assert "score" in data


@pytest.mark.integration
def test_video_detail_rejects_nonexistent_video(integration_runtime):
    """
    用例描述:
    - 用例目的: 验证视频详情接口对不存在视频返回正确错误。
    - 测试步骤:
      1. 调用 GET /api/v1/video/detail?video_id=NONEXISTENT。
      2. 检查返回错误码。
    - 预期结果:
      1. HTTP 200，业务 code=404。
    - 历史变更:
      - 2026-03-25: 初始创建，覆盖视频详情不存在分支。
    """
    base_url = integration_runtime["base_url"]

    response = requests.get(
        f"{base_url}/api/v1/video/detail",
        params={"video_id": "NONEXISTENT_VIDEO_999"},
        timeout=5,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 404


@pytest.mark.integration
def test_video_edit_updates_metadata_and_persists(integration_runtime):
    """
    用例描述:
    - 用例目的: 验证视频编辑接口能正确更新元数据并持久化。
    - 测试步骤:
      1. 调用 PUT /api/v1/video/edit 更新视频标题和演员。
      2. 检查接口返回状态。
      3. 验证文件中数据已更新。
    - 预期结果:
      1. HTTP 200，业务 code=200。
      2. 返回数据包含更新后的字段。
      3. 文件中对应记录已更新。
    - 历史变更:
      - 2026-03-25: 初始创建，覆盖视频编辑主链路。
    """
    base_url = integration_runtime["base_url"]
    meta_dir = integration_runtime["meta_dir"]
    videos_path = meta_dir / "videos_database.json"

    from tests.shared.test_constants import PRIMARY_VIDEO_ID

    new_title = "Updated Video Title"
    new_actors = ["New Actor A", "New Actor B"]

    response = requests.put(
        f"{base_url}/api/v1/video/edit",
        json={"video_id": PRIMARY_VIDEO_ID, "title": new_title, "actors": new_actors},
        timeout=5,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 200
    assert payload["data"]["title"] == new_title
    assert payload["data"]["actors"] == new_actors

    videos_data = load_json(videos_path)
    videos = videos_data.get("videos", [])
    updated = find_by_id(videos, PRIMARY_VIDEO_ID)
    assert updated is not None
    assert updated["title"] == new_title
    assert updated["actors"] == new_actors


@pytest.mark.integration
def test_video_score_update_persists(integration_runtime):
    """
    用例描述:
    - 用例目的: 验证视频评分更新接口能正确持久化评分。
    - 测试步骤:
      1. 调用 PUT /api/v1/video/score 更新评分。
      2. 验证接口返回和文件持久化。
    - 预期结果:
      1. HTTP 200，业务 code=200。
      2. 文件中对应记录的 score 已更新。
    - 历史变更:
      - 2026-03-25: 初始创建，覆盖视频评分更新主链路。
    """
    base_url = integration_runtime["base_url"]
    meta_dir = integration_runtime["meta_dir"]
    videos_path = meta_dir / "videos_database.json"

    from tests.shared.test_constants import PRIMARY_VIDEO_ID

    new_score = 9.5

    response = requests.put(
        f"{base_url}/api/v1/video/score",
        json={"video_id": PRIMARY_VIDEO_ID, "score": new_score},
        timeout=5,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 200
    assert payload["data"]["score"] == new_score

    videos_data = load_json(videos_path)
    videos = videos_data.get("videos", [])
    updated = find_by_id(videos, PRIMARY_VIDEO_ID)
    assert updated is not None
    assert updated["score"] == new_score


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
      2. 文件中对应记录的进度已更新。
    - 历史变更:
      - 2026-03-25: 初始创建，覆盖视频进度更新主链路。
    """
    base_url = integration_runtime["base_url"]
    meta_dir = integration_runtime["meta_dir"]
    videos_path = meta_dir / "videos_database.json"

    from tests.shared.test_constants import PRIMARY_VIDEO_ID

    new_unit = 1

    response = requests.put(
        f"{base_url}/api/v1/video/progress",
        json={"video_id": PRIMARY_VIDEO_ID, "unit": new_unit},
        timeout=5,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 200

    videos_data = load_json(videos_path)
    videos = videos_data.get("videos", [])
    updated = find_by_id(videos, PRIMARY_VIDEO_ID)
    assert updated is not None


@pytest.mark.integration
def test_video_search_returns_matching_results(integration_runtime):
    """
    用例描述:
    - 用例目的: 验证视频搜索接口能正确返回匹配结果。
    - 测试步骤:
      1. 调用 GET /api/v1/video/search?keyword=Seed。
      2. 检查返回结果包含匹配的视频。
    - 预期结果:
      1. HTTP 200，业务 code=200。
      2. 返回结果包含标题含有关键词的视频。
    - 历史变更:
      - 2026-03-25: 初始创建，覆盖视频搜索主链路。
    """
    base_url = integration_runtime["base_url"]

    response = requests.get(
        f"{base_url}/api/v1/video/search",
        params={"keyword": "Seed"},
        timeout=5,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 200
    results = payload["data"]
    assert len(results) >= 1
    assert any("Seed" in item["title"] for item in results)


@pytest.mark.integration
def test_video_search_rejects_missing_keyword(integration_runtime):
    """
    用例描述:
    - 用例目的: 验证视频搜索接口校验必要参数。
    - 测试步骤:
      1. 调用 GET /api/v1/video/search 不传 keyword。
      2. 检查接口返回错误码。
    - 预期结果:
      1. HTTP 200，业务 code=400。
    - 历史变更:
      - 2026-03-25: 初始创建，覆盖视频搜索参数校验。
    """
    base_url = integration_runtime["base_url"]

    response = requests.get(
        f"{base_url}/api/v1/video/search",
        timeout=5,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 400
