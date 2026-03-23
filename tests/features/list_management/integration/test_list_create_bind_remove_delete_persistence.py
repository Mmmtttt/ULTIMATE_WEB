from __future__ import annotations

from uuid import uuid4

import pytest
import requests

from tests.shared.runtime_data import find_by_id, load_json
from tests.shared.test_constants import PRIMARY_COMIC_ID


@pytest.mark.integration
def test_list_create_bind_remove_delete_persistence(integration_runtime):
    """
    用例描述:
    - 用例目的: 验证清单的创建、绑定漫画、移除漫画、删除清单在接口与落盘文件层面一致。
    - 测试步骤:
      1. 调用 /api/v1/list/add 创建漫画清单。
      2. 调用 /api/v1/list/comic/bind 将目标漫画加入该清单。
      3. 调用 /api/v1/list/comic/remove 将目标漫画移出该清单。
      4. 调用 /api/v1/list/delete 删除该清单。
      5. 每步后检查 lists/comics 元数据文件。
    - 预期结果:
      1. 每个接口返回 HTTP 200 且业务 code=200。
      2. list 记录与 comic.list_ids 状态按步骤变化。
      3. 删除后清单从 lists_database.json 中消失。
    - 历史变更:
      - 2026-03-23: 初始创建，覆盖清单后端核心生命周期。
    """
    base_url = integration_runtime["base_url"]
    meta_dir = integration_runtime["meta_dir"]
    lists_path = meta_dir / "lists_database.json"
    comics_path = meta_dir / "comics_database.json"

    list_name = f"Integration List {uuid4().hex[:8]}"
    create_resp = requests.post(
        f"{base_url}/api/v1/list/add",
        json={"list_name": list_name, "desc": "integration test", "content_type": "comic"},
        timeout=5,
    )
    assert create_resp.status_code == 200
    create_payload = create_resp.json()
    assert create_payload["code"] == 200
    created_list_id = create_payload["data"]["id"]

    lists_after_create = load_json(lists_path).get("lists", [])
    created_list = find_by_id(lists_after_create, created_list_id)
    assert created_list is not None
    assert created_list["name"] == list_name

    bind_resp = requests.put(
        f"{base_url}/api/v1/list/comic/bind",
        json={
            "list_id": created_list_id,
            "comic_id_list": [PRIMARY_COMIC_ID],
            "source": "local",
        },
        timeout=5,
    )
    assert bind_resp.status_code == 200
    bind_payload = bind_resp.json()
    assert bind_payload["code"] == 200
    assert bind_payload["data"]["updated_count"] == 1

    comics_after_bind = load_json(comics_path).get("comics", [])
    primary_after_bind = find_by_id(comics_after_bind, PRIMARY_COMIC_ID)
    assert primary_after_bind is not None
    assert created_list_id in (primary_after_bind.get("list_ids") or [])

    remove_resp = requests.delete(
        f"{base_url}/api/v1/list/comic/remove",
        params={
            "list_id": created_list_id,
            "comic_id_list": PRIMARY_COMIC_ID,
            "source": "local",
        },
        timeout=5,
    )
    assert remove_resp.status_code == 200
    remove_payload = remove_resp.json()
    assert remove_payload["code"] == 200
    assert remove_payload["data"]["updated_count"] == 1

    comics_after_remove = load_json(comics_path).get("comics", [])
    primary_after_remove = find_by_id(comics_after_remove, PRIMARY_COMIC_ID)
    assert primary_after_remove is not None
    assert created_list_id not in (primary_after_remove.get("list_ids") or [])

    delete_resp = requests.delete(
        f"{base_url}/api/v1/list/delete",
        params={"list_id": created_list_id},
        timeout=5,
    )
    assert delete_resp.status_code == 200
    delete_payload = delete_resp.json()
    assert delete_payload["code"] == 200

    lists_after_delete = load_json(lists_path).get("lists", [])
    assert find_by_id(lists_after_delete, created_list_id) is None
