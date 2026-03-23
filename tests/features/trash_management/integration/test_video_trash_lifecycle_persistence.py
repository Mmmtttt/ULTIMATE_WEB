from __future__ import annotations

from uuid import uuid4

import pytest
import requests

from tests.shared.runtime_data import find_by_id, load_json


@pytest.mark.integration
def test_video_trash_lifecycle_persistence(integration_runtime):
    """
    用例描述:
    - 用例目的: 验证视频回收站生命周期（移入/恢复/永久删除）在接口与落盘文件层面一致。
    - 测试步骤:
      1. 通过 /api/v1/video/import 创建测试视频。
      2. 调用 /api/v1/video/trash/move 移入回收站并校验 is_deleted。
      3. 调用 /api/v1/video/trash/restore 恢复并校验 is_deleted。
      4. 再次移入回收站后调用 /api/v1/video/trash/delete 永久删除。
      5. 检查 videos_database.json 中对应记录状态。
    - 预期结果:
      1. 各接口返回 HTTP 200 且业务 code=200。
      2. is_deleted 按预期切换。
      3. 永久删除后记录从 videos_database.json 消失。
    - 历史变更:
      - 2026-03-23: 初始创建，覆盖视频回收站后端生命周期。
    """
    base_url = integration_runtime["base_url"]
    meta_dir = integration_runtime["meta_dir"]
    videos_path = meta_dir / "videos_database.json"

    video_suffix = uuid4().hex[:8].upper()
    video_id = f"TMPVIDEO{video_suffix}"
    video_code = f"TMP-{video_suffix}"

    import_resp = requests.post(
        f"{base_url}/api/v1/video/import",
        json={
            "id": video_id,
            "code": video_code,
            "title": f"Temporary Video {video_suffix}",
            "actors": ["Integration Actor"],
            "cover_path": "/static/cover/JAVDB/900001.png",
        },
        timeout=5,
    )
    assert import_resp.status_code == 200
    import_payload = import_resp.json()
    assert import_payload["code"] == 200
    assert import_payload["data"]["id"] == video_id

    videos_after_import = load_json(videos_path).get("videos", [])
    created_video = find_by_id(videos_after_import, video_id)
    assert created_video is not None
    assert created_video.get("is_deleted") is False

    move_resp = requests.put(
        f"{base_url}/api/v1/video/trash/move",
        json={"video_id": video_id},
        timeout=5,
    )
    assert move_resp.status_code == 200
    move_payload = move_resp.json()
    assert move_payload["code"] == 200

    videos_after_move = load_json(videos_path).get("videos", [])
    moved_video = find_by_id(videos_after_move, video_id)
    assert moved_video is not None
    assert moved_video.get("is_deleted") is True

    restore_resp = requests.put(
        f"{base_url}/api/v1/video/trash/restore",
        json={"video_id": video_id},
        timeout=5,
    )
    assert restore_resp.status_code == 200
    restore_payload = restore_resp.json()
    assert restore_payload["code"] == 200

    videos_after_restore = load_json(videos_path).get("videos", [])
    restored_video = find_by_id(videos_after_restore, video_id)
    assert restored_video is not None
    assert restored_video.get("is_deleted") is False

    move_again_resp = requests.put(
        f"{base_url}/api/v1/video/trash/move",
        json={"video_id": video_id},
        timeout=5,
    )
    assert move_again_resp.status_code == 200
    move_again_payload = move_again_resp.json()
    assert move_again_payload["code"] == 200

    delete_resp = requests.delete(
        f"{base_url}/api/v1/video/trash/delete",
        params={"video_id": video_id},
        timeout=5,
    )
    assert delete_resp.status_code == 200
    delete_payload = delete_resp.json()
    assert delete_payload["code"] == 200

    videos_after_delete = load_json(videos_path).get("videos", [])
    assert find_by_id(videos_after_delete, video_id) is None
