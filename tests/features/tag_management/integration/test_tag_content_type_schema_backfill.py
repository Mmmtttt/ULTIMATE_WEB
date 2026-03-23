from __future__ import annotations

import pytest
import requests

from tests.shared.runtime_data import find_by_id, load_json, save_json


@pytest.mark.integration
def test_tag_missing_content_type_is_backfilled_to_comic(integration_runtime):
    """
    用例描述:
    - 用例目的: 看护 tags_database.json 中缺失 content_type 的历史标签会被自动回填，避免标签类型语义漂移。
    - 测试步骤:
      1. 人工移除一个漫画标签的 content_type 字段。
      2. 调用 /api/v1/tag/list?content_type=comic 触发标签仓库读取。
      3. 重新读取 tags_database.json 校验该标签被回填为 comic，且视频标签不受影响。
    - 预期结果:
      1. 接口返回 HTTP 200 且业务 code=200。
      2. 缺失字段的标签被写回 content_type=comic。
      3. 既有视频标签仍保持 content_type=video。
    - 历史变更:
      - 2026-03-24: 初始创建，覆盖 tag content_type 回填场景。
    """
    base_url = integration_runtime["base_url"]
    tags_path = integration_runtime["meta_dir"] / "tags_database.json"

    tags_payload = load_json(tags_path)
    tags = tags_payload.get("tags", [])

    comic_tag = find_by_id(tags, "tag_action")
    video_tag = find_by_id(tags, "tag_video")
    assert comic_tag is not None
    assert video_tag is not None
    assert comic_tag.get("content_type") == "comic"
    assert video_tag.get("content_type") == "video"

    comic_tag.pop("content_type", None)
    save_json(tags_path, tags_payload)

    response = requests.get(
        f"{base_url}/api/v1/tag/list",
        params={"content_type": "comic"},
        timeout=8,
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload.get("code") == 200

    repaired_payload = load_json(tags_path)
    repaired_tags = repaired_payload.get("tags", [])
    repaired_comic_tag = find_by_id(repaired_tags, "tag_action")
    repaired_video_tag = find_by_id(repaired_tags, "tag_video")
    assert repaired_comic_tag is not None
    assert repaired_comic_tag.get("content_type") == "comic"
    assert repaired_video_tag is not None
    assert repaired_video_tag.get("content_type") == "video"

