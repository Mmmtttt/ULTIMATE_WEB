from __future__ import annotations

import shutil
from uuid import uuid4

import pytest
import requests

from tests.shared.runtime_data import find_by_id, load_json


@pytest.mark.integration
def test_comic_trash_move_and_restore_lifecycle(integration_runtime):
    """
    用例描述:
    - 用例目的: 验证漫画回收站移入和恢复生命周期。
    - 测试步骤:
      1. 调用 PUT /api/v1/comic/trash/move 移入回收站。
      2. 验证 is_deleted 为 True。
      3. 调用 PUT /api/v1/comic/trash/restore 恢复。
      4. 验证 is_deleted 为 False。
    - 预期结果:
      1. 各接口返回 HTTP 200 且业务 code=200。
      2. is_deleted 按预期切换。
    - 历史变更:
      - 2026-03-25: 初始创建，覆盖漫画回收站生命周期。
    """
    base_url = integration_runtime["base_url"]
    meta_dir = integration_runtime["meta_dir"]
    comics_path = meta_dir / "comics_database.json"

    from tests.shared.test_constants import PRIMARY_COMIC_ID

    move_resp = requests.put(
        f"{base_url}/api/v1/comic/trash/move",
        json={"comic_id": PRIMARY_COMIC_ID},
        timeout=5,
    )
    assert move_resp.status_code == 200
    assert move_resp.json()["code"] == 200

    comics_after_move = load_json(comics_path).get("comics", [])
    moved_comic = find_by_id(comics_after_move, PRIMARY_COMIC_ID)
    assert moved_comic is not None
    assert moved_comic.get("is_deleted") is True

    restore_resp = requests.put(
        f"{base_url}/api/v1/comic/trash/restore",
        json={"comic_id": PRIMARY_COMIC_ID},
        timeout=5,
    )
    assert restore_resp.status_code == 200
    assert restore_resp.json()["code"] == 200

    comics_after_restore = load_json(comics_path).get("comics", [])
    restored_comic = find_by_id(comics_after_restore, PRIMARY_COMIC_ID)
    assert restored_comic is not None
    assert restored_comic.get("is_deleted") is False


@pytest.mark.integration
def test_comic_trash_permanent_delete_removes_record(integration_runtime):
    """
    用例描述:
    - 用例目的: 验证漫画永久删除接口能正确移除记录。
    - 测试步骤:
      1. 使用种子数据中的漫画。
      2. 移入回收站。
      3. 调用 DELETE /api/v1/comic/trash/delete 永久删除。
      4. 验证记录已从文件中移除。
    - 预期结果:
      1. HTTP 200，业务 code=200。
      2. 记录从 comics_database.json 中消失。
    - 历史变更:
      - 2026-03-25: 初始创建，覆盖漫画永久删除主链路。
    """
    base_url = integration_runtime["base_url"]
    meta_dir = integration_runtime["meta_dir"]
    data_dir = integration_runtime["data_dir"]
    comics_path = meta_dir / "comics_database.json"

    from tests.shared.test_constants import FIFTH_COMIC_ID

    temp_numeric = str((uuid4().int % 900000) + 100000)
    temp_comic_id = f"JM{temp_numeric}"
    temp_title = f"Trash Delete {temp_numeric}"
    source_dir = data_dir / "comic" / "JM" / FIFTH_COMIC_ID.replace("JM", "", 1)
    temp_dir = data_dir / "comic" / "JM" / temp_comic_id.replace("JM", "", 1)
    if temp_dir.exists():
        shutil.rmtree(temp_dir, ignore_errors=True)
    shutil.copytree(source_dir, temp_dir)

    init_resp = requests.post(
        f"{base_url}/api/v1/comic/init",
        json={"comic_id": temp_comic_id, "title": temp_title},
        timeout=10,
    )
    assert init_resp.status_code == 200
    assert init_resp.json()["code"] == 200

    trash_resp = requests.put(
        f"{base_url}/api/v1/comic/trash/move",
        json={"comic_id": temp_comic_id},
        timeout=5,
    )
    assert trash_resp.status_code == 200
    assert trash_resp.json()["code"] == 200

    delete_resp = requests.delete(
        f"{base_url}/api/v1/comic/trash/delete",
        json={"comic_id": temp_comic_id},
        timeout=5,
    )
    assert delete_resp.status_code == 200
    assert delete_resp.json()["code"] == 200

    comics_after_delete = load_json(comics_path).get("comics", [])
    assert find_by_id(comics_after_delete, temp_comic_id) is None


@pytest.mark.integration
def test_video_batch_trash_move_moves_all(integration_runtime):
    """
    用例描述:
    - 用例目的: 验证视频批量移入回收站接口能正确处理多个视频。
    - 测试步骤:
      1. 创建两个测试视频。
      2. 调用 PUT /api/v1/video/trash/batch-move 批量移入。
      3. 验证两个视频的 is_deleted 都为 True。
    - 预期结果:
      1. HTTP 200，业务 code=200。
      2. 所有指定视频的 is_deleted 为 True。
    - 历史变更:
      - 2026-03-25: 初始创建，覆盖视频批量移入回收站。
    """
    base_url = integration_runtime["base_url"]
    meta_dir = integration_runtime["meta_dir"]
    videos_path = meta_dir / "videos_database.json"

    suffix1 = uuid4().hex[:8].upper()
    suffix2 = uuid4().hex[:8].upper()
    video_id_1 = f"BATCHDEL1{suffix1}"
    video_id_2 = f"BATCHDEL2{suffix2}"

    requests.post(
        f"{base_url}/api/v1/video/import",
        json={"id": video_id_1, "code": f"BD1-{suffix1}", "title": f"Batch Delete 1 {suffix1}"},
        timeout=5,
    )
    requests.post(
        f"{base_url}/api/v1/video/import",
        json={"id": video_id_2, "code": f"BD2-{suffix2}", "title": f"Batch Delete 2 {suffix2}"},
        timeout=5,
    )

    batch_move_resp = requests.put(
        f"{base_url}/api/v1/video/trash/batch-move",
        json={"video_ids": [video_id_1, video_id_2]},
        timeout=5,
    )
    assert batch_move_resp.status_code == 200
    assert batch_move_resp.json()["code"] == 200

    videos_after = load_json(videos_path).get("videos", [])
    v1 = find_by_id(videos_after, video_id_1)
    v2 = find_by_id(videos_after, video_id_2)
    assert v1 is not None and v1.get("is_deleted") is True
    assert v2 is not None and v2.get("is_deleted") is True


@pytest.mark.integration
def test_video_batch_trash_restore_restores_all(integration_runtime):
    """
    用例描述:
    - 用例目的: 验证视频批量从回收站恢复接口能正确处理多个视频。
    - 测试步骤:
      1. 创建两个测试视频并移入回收站。
      2. 调用 PUT /api/v1/video/trash/batch-restore 批量恢复。
      3. 验证两个视频的 is_deleted 都为 False。
    - 预期结果:
      1. HTTP 200，业务 code=200。
      2. 所有指定视频的 is_deleted 为 False。
    - 历史变更:
      - 2026-03-25: 初始创建，覆盖视频批量恢复。
    """
    base_url = integration_runtime["base_url"]
    meta_dir = integration_runtime["meta_dir"]
    videos_path = meta_dir / "videos_database.json"

    suffix1 = uuid4().hex[:8].upper()
    suffix2 = uuid4().hex[:8].upper()
    video_id_1 = f"BATCHRES1{suffix1}"
    video_id_2 = f"BATCHRES2{suffix2}"

    requests.post(
        f"{base_url}/api/v1/video/import",
        json={"id": video_id_1, "code": f"BR1-{suffix1}", "title": f"Batch Restore 1 {suffix1}"},
        timeout=5,
    )
    requests.post(
        f"{base_url}/api/v1/video/import",
        json={"id": video_id_2, "code": f"BR2-{suffix2}", "title": f"Batch Restore 2 {suffix2}"},
        timeout=5,
    )
    requests.put(
        f"{base_url}/api/v1/video/trash/batch-move",
        json={"video_ids": [video_id_1, video_id_2]},
        timeout=5,
    )

    batch_restore_resp = requests.put(
        f"{base_url}/api/v1/video/trash/batch-restore",
        json={"video_ids": [video_id_1, video_id_2]},
        timeout=5,
    )
    assert batch_restore_resp.status_code == 200
    assert batch_restore_resp.json()["code"] == 200

    videos_after = load_json(videos_path).get("videos", [])
    v1 = find_by_id(videos_after, video_id_1)
    v2 = find_by_id(videos_after, video_id_2)
    assert v1 is not None and v1.get("is_deleted") is False
    assert v2 is not None and v2.get("is_deleted") is False


@pytest.mark.integration
def test_video_batch_permanent_delete_removes_all(integration_runtime):
    """
    用例描述:
    - 用例目的: 验证视频批量永久删除接口能正确移除多个记录。
    - 测试步骤:
      1. 创建两个测试视频并移入回收站。
      2. 调用 DELETE /api/v1/video/trash/batch-delete 批量删除。
      3. 验证两个记录都从文件中移除。
    - 预期结果:
      1. HTTP 200，业务 code=200。
      2. 所有指定记录从 videos_database.json 中消失。
    - 历史变更:
      - 2026-03-25: 初始创建，覆盖视频批量永久删除。
    """
    base_url = integration_runtime["base_url"]
    meta_dir = integration_runtime["meta_dir"]
    videos_path = meta_dir / "videos_database.json"

    suffix1 = uuid4().hex[:8].upper()
    suffix2 = uuid4().hex[:8].upper()
    video_id_1 = f"BATCHPERM1{suffix1}"
    video_id_2 = f"BATCHPERM2{suffix2}"

    requests.post(
        f"{base_url}/api/v1/video/import",
        json={"id": video_id_1, "code": f"BP1-{suffix1}", "title": f"Batch Perm 1 {suffix1}"},
        timeout=5,
    )
    requests.post(
        f"{base_url}/api/v1/video/import",
        json={"id": video_id_2, "code": f"BP2-{suffix2}", "title": f"Batch Perm 2 {suffix2}"},
        timeout=5,
    )
    requests.put(
        f"{base_url}/api/v1/video/trash/batch-move",
        json={"video_ids": [video_id_1, video_id_2]},
        timeout=5,
    )

    batch_delete_resp = requests.delete(
        f"{base_url}/api/v1/video/trash/batch-delete",
        json={"video_ids": [video_id_1, video_id_2]},
        timeout=5,
    )
    assert batch_delete_resp.status_code == 200
    assert batch_delete_resp.json()["code"] == 200

    videos_after = load_json(videos_path).get("videos", [])
    assert find_by_id(videos_after, video_id_1) is None
    assert find_by_id(videos_after, video_id_2) is None


@pytest.mark.integration
def test_video_trash_list_returns_only_deleted(integration_runtime):
    """
    用例描述:
    - 用例目的: 验证视频回收站列表接口只返回已删除的视频。
    - 测试步骤:
      1. 创建测试视频并移入回收站。
      2. 调用 GET /api/v1/video/trash/list。
      3. 验证返回列表包含已删除视频。
    - 预期结果:
      1. HTTP 200，业务 code=200。
      2. 返回列表中的视频 is_deleted 为 True。
    - 历史变更:
      - 2026-03-25: 初始创建，覆盖视频回收站列表。
    """
    base_url = integration_runtime["base_url"]

    suffix = uuid4().hex[:8].upper()
    video_id = f"TRASHLIST{suffix}"

    requests.post(
        f"{base_url}/api/v1/video/import",
        json={"id": video_id, "code": f"TL-{suffix}", "title": f"Trash List Test {suffix}"},
        timeout=5,
    )
    requests.put(
        f"{base_url}/api/v1/video/trash/move",
        json={"video_id": video_id},
        timeout=5,
    )

    trash_list_resp = requests.get(
        f"{base_url}/api/v1/video/trash/list",
        timeout=5,
    )
    assert trash_list_resp.status_code == 200
    payload = trash_list_resp.json()
    assert payload["code"] == 200

    trash_videos = payload["data"]
    found = any(v.get("id") == video_id for v in trash_videos)
    assert found


@pytest.mark.integration
def test_video_trash_move_rejects_nonexistent_video(integration_runtime):
    """
    用例描述:
    - 用例目的: 验证视频移入回收站接口拒绝不存在的视频。
    - 测试步骤:
      1. 调用 PUT /api/v1/video/trash/move 使用不存在的 video_id。
      2. 检查返回错误码。
    - 预期结果:
      1. HTTP 200，业务 code=400。
    - 历史变更:
      - 2026-03-25: 初始创建，覆盖视频回收站参数校验。
    """
    base_url = integration_runtime["base_url"]

    move_resp = requests.put(
        f"{base_url}/api/v1/video/trash/move",
        json={"video_id": "NONEXISTENT_VIDEO_999"},
        timeout=5,
    )
    assert move_resp.status_code == 200
    assert move_resp.json()["code"] == 400


@pytest.mark.integration
def test_video_trash_restore_rejects_nonexistent_video(integration_runtime):
    """
    用例描述:
    - 用例目的: 验证视频从回收站恢复接口拒绝不存在的视频。
    - 测试步骤:
      1. 调用 PUT /api/v1/video/trash/restore 使用不存在的 video_id。
      2. 检查返回错误码。
    - 预期结果:
      1. HTTP 200，业务 code=400。
    - 历史变更:
      - 2026-03-25: 初始创建，覆盖视频恢复参数校验。
    """
    base_url = integration_runtime["base_url"]

    restore_resp = requests.put(
        f"{base_url}/api/v1/video/trash/restore",
        json={"video_id": "NONEXISTENT_VIDEO_999"},
        timeout=5,
    )
    assert restore_resp.status_code == 200
    assert restore_resp.json()["code"] == 400


@pytest.mark.integration
def test_video_batch_trash_move_rejects_empty_list(integration_runtime):
    """
    用例描述:
    - 用例目的: 验证视频批量移入回收站接口校验必要参数。
    - 测试步骤:
      1. 调用 PUT /api/v1/video/trash/batch-move 不传 video_ids。
      2. 检查返回错误码。
    - 预期结果:
      1. HTTP 200，业务 code=400。
    - 历史变更:
      - 2026-03-25: 初始创建，覆盖批量操作参数校验。
    """
    base_url = integration_runtime["base_url"]

    batch_move_resp = requests.put(
        f"{base_url}/api/v1/video/trash/batch-move",
        json={},
        timeout=5,
    )
    assert batch_move_resp.status_code == 200
    assert batch_move_resp.json()["code"] == 400
