from __future__ import annotations

import pytest
import requests

from tests.shared.runtime_data import find_by_id, load_json
from tests.shared.test_constants import PRIMARY_COMIC_ID


@pytest.mark.integration
def test_save_progress_updates_filesystem_and_response(integration_runtime):
    """
    用例描述:
    - 用例目的: 验证漫画阅读进度更新后，接口响应与 JSON 持久化保持一致。
    - 测试步骤:
      1. 读取 comics_database.json，确认初始 current_page。
      2. 调用 PUT /api/v1/comic/progress 更新进度。
      3. 校验 HTTP 响应与业务字段。
      4. 再次读取文件，确认 current_page 已落盘更新。
    - 预期结果:
      1. 接口返回 200 且业务 code=200。
      2. 响应体 current_page 与请求值一致。
      3. 文件系统中目标漫画 current_page 同步更新。
    - 历史变更:
      - 2026-03-23: 初始创建并纳入门禁。
      - 2026-03-23: 补充统一用例描述模板并复用共享 JSON 工具。
    """
    base_url = integration_runtime["base_url"]
    meta_dir = integration_runtime["meta_dir"]
    comics_path = meta_dir / "comics_database.json"

    comics_before = load_json(comics_path).get("comics", [])
    detail_before = find_by_id(comics_before, PRIMARY_COMIC_ID)

    assert detail_before is not None
    assert detail_before["current_page"] == 1

    response = requests.put(
        f"{base_url}/api/v1/comic/progress",
        json={"comic_id": PRIMARY_COMIC_ID, "current_page": 2},
        timeout=5,
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 200
    assert payload["data"]["comic_id"] == PRIMARY_COMIC_ID
    assert payload["data"]["current_page"] == 2

    comics_after = load_json(comics_path).get("comics", [])
    comic_after = find_by_id(comics_after, PRIMARY_COMIC_ID)
    assert comic_after is not None
    assert comic_after["current_page"] == 2
