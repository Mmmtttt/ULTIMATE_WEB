from __future__ import annotations

from uuid import uuid4

import pytest
import requests

from tests.shared.runtime_data import find_by_id, load_json
from tests.shared.test_constants import PRIMARY_COMIC_ID


@pytest.mark.integration
def test_tag_add_edit_bind_delete_persistence(integration_runtime):
    """
    用例描述:
    - 用例目的: 验证标签新增、编辑、绑定漫画、删除后数据在接口与落盘文件中一致。
    - 测试步骤:
      1. 调用 /api/v1/tag/add 新增漫画标签。
      2. 调用 /api/v1/tag/edit 修改标签名称。
      3. 调用 /api/v1/comic/tag/bind 绑定标签到目标漫画。
      4. 调用 /api/v1/tag/delete 删除该标签。
      5. 检查 tags/comics 元数据文件变化。
    - 预期结果:
      1. 各接口返回 HTTP 200 且业务 code=200。
      2. 标签名称更新成功，漫画 tag_ids 包含新增标签。
      3. 删除后标签从 tags_database.json 与漫画 tag_ids 中清除。
    - 历史变更:
      - 2026-03-23: 初始创建，覆盖标签后端主生命周期。
    """
    base_url = integration_runtime["base_url"]
    meta_dir = integration_runtime["meta_dir"]
    tags_path = meta_dir / "tags_database.json"
    comics_path = meta_dir / "comics_database.json"

    tag_name = f"it_tag_{uuid4().hex[:6]}"
    add_resp = requests.post(
        f"{base_url}/api/v1/tag/add",
        json={"tag_name": tag_name, "content_type": "comic"},
        timeout=5,
    )
    assert add_resp.status_code == 200
    add_payload = add_resp.json()
    assert add_payload["code"] == 200
    tag_id = add_payload["data"]["id"]

    tags_after_add = load_json(tags_path).get("tags", [])
    created_tag = find_by_id(tags_after_add, tag_id)
    assert created_tag is not None
    assert created_tag["name"] == tag_name

    edited_name = f"{tag_name}_edited"
    edit_resp = requests.put(
        f"{base_url}/api/v1/tag/edit",
        json={"tag_id": tag_id, "tag_name": edited_name},
        timeout=5,
    )
    assert edit_resp.status_code == 200
    edit_payload = edit_resp.json()
    assert edit_payload["code"] == 200

    tags_after_edit = load_json(tags_path).get("tags", [])
    edited_tag = find_by_id(tags_after_edit, tag_id)
    assert edited_tag is not None
    assert edited_tag["name"] == edited_name

    comics_before_bind = load_json(comics_path).get("comics", [])
    primary_before_bind = find_by_id(comics_before_bind, PRIMARY_COMIC_ID)
    assert primary_before_bind is not None
    existing_tag_ids = list(primary_before_bind.get("tag_ids") or [])
    bind_tag_ids = sorted(set(existing_tag_ids + [tag_id]))

    bind_resp = requests.put(
        f"{base_url}/api/v1/comic/tag/bind",
        json={"comic_id": PRIMARY_COMIC_ID, "tag_id_list": bind_tag_ids},
        timeout=5,
    )
    assert bind_resp.status_code == 200
    bind_payload = bind_resp.json()
    assert bind_payload["code"] == 200

    comics_after_bind = load_json(comics_path).get("comics", [])
    primary_after_bind = find_by_id(comics_after_bind, PRIMARY_COMIC_ID)
    assert primary_after_bind is not None
    assert tag_id in (primary_after_bind.get("tag_ids") or [])

    unbind_resp = requests.put(
        f"{base_url}/api/v1/comic/tag/bind",
        json={"comic_id": PRIMARY_COMIC_ID, "tag_id_list": existing_tag_ids},
        timeout=5,
    )
    assert unbind_resp.status_code == 200
    unbind_payload = unbind_resp.json()
    assert unbind_payload["code"] == 200

    comics_after_unbind = load_json(comics_path).get("comics", [])
    primary_after_unbind = find_by_id(comics_after_unbind, PRIMARY_COMIC_ID)
    assert primary_after_unbind is not None
    assert tag_id not in (primary_after_unbind.get("tag_ids") or [])

    delete_resp = requests.delete(
        f"{base_url}/api/v1/tag/delete",
        json={"tag_id": tag_id},
        timeout=5,
    )
    assert delete_resp.status_code == 200
    delete_payload = delete_resp.json()
    assert delete_payload["code"] == 200

    tags_after_delete = load_json(tags_path).get("tags", [])
    assert find_by_id(tags_after_delete, tag_id) is None

    comics_after_delete = load_json(comics_path).get("comics", [])
    primary_after_delete = find_by_id(comics_after_delete, PRIMARY_COMIC_ID)
    assert primary_after_delete is not None
    assert tag_id not in (primary_after_delete.get("tag_ids") or [])
