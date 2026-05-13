from __future__ import annotations

from pathlib import Path

import pytest
import requests

from tests.shared.runtime_data import load_json


@pytest.mark.integration
def test_ui_state_save_get_and_delete_persists_by_client_and_scope(integration_runtime):
    """
    用例描述:
    - 用例目的: 强看护 UI 状态接口会把“最后一次筛选/排序/搜索条件”固化到元数据文件，并在清空时移除。
    - 测试步骤:
      1. 保存同一 client 的两个 scope 状态。
      2. 读取 `ui_state_database.json` 验证按 `client_id + scope` 落盘。
      3. 删除其中一个 scope，确认另一 scope 仍保留。
      4. 删除最后一个 scope，确认文件中该 client 被清理。
    - 预期结果:
      1. `GET/PUT/DELETE /api/v1/ui-state` 都返回成功。
      2. 状态文件内容与接口语义一致。
      3. 清空条件后不会残留空 scope 或空 client。
    - 历史变更:
      - 2026-05-14: 新增，覆盖 UI 条件持久化门禁。
    """
    base_url = integration_runtime["base_url"]
    meta_dir: Path = integration_runtime["meta_dir"]
    state_path = meta_dir / "ui_state_database.json"

    client_id = "ui-test-device-a"
    library_scope = "library_state_comic"
    search_scope = "global_search_comic"
    library_state = {
        "selectedAuthors": ["Tester C"],
        "includeTags": ["tag_action"],
        "sortField": "score",
        "sortOrder": "asc",
    }
    search_state = {
        "keyword": "seed",
        "activeTab": "preview",
    }

    put_library = requests.put(
        f"{base_url}/api/v1/ui-state",
        json={"client_id": client_id, "scope": library_scope, "state": library_state},
        timeout=5,
    )
    assert put_library.status_code == 200
    put_library_payload = put_library.json()
    assert put_library_payload["code"] == 200
    assert put_library_payload["data"]["deleted"] is False

    put_search = requests.put(
        f"{base_url}/api/v1/ui-state",
        json={"client_id": client_id, "scope": search_scope, "state": search_state},
        timeout=5,
    )
    assert put_search.status_code == 200
    put_search_payload = put_search.json()
    assert put_search_payload["code"] == 200

    stored_payload = load_json(state_path)
    assert stored_payload["version"] == 1
    assert stored_payload["last_updated"]
    assert stored_payload["clients"][client_id]["scopes"][library_scope] == library_state
    assert stored_payload["clients"][client_id]["scopes"][search_scope] == search_state

    get_library = requests.get(
        f"{base_url}/api/v1/ui-state",
        params={"client_id": client_id, "scope": library_scope},
        timeout=5,
    )
    assert get_library.status_code == 200
    get_library_payload = get_library.json()
    assert get_library_payload["code"] == 200
    assert get_library_payload["data"]["exists"] is True
    assert get_library_payload["data"]["state"] == library_state

    delete_library = requests.delete(
        f"{base_url}/api/v1/ui-state",
        json={"client_id": client_id, "scope": library_scope},
        timeout=5,
    )
    assert delete_library.status_code == 200
    delete_library_payload = delete_library.json()
    assert delete_library_payload["code"] == 200
    assert delete_library_payload["data"]["deleted"] is True

    payload_after_first_delete = load_json(state_path)
    assert library_scope not in payload_after_first_delete["clients"][client_id]["scopes"]
    assert payload_after_first_delete["clients"][client_id]["scopes"][search_scope] == search_state

    delete_search = requests.delete(
        f"{base_url}/api/v1/ui-state",
        json={"client_id": client_id, "scope": search_scope},
        timeout=5,
    )
    assert delete_search.status_code == 200
    delete_search_payload = delete_search.json()
    assert delete_search_payload["code"] == 200
    assert delete_search_payload["data"]["deleted"] is True

    payload_after_second_delete = load_json(state_path)
    assert payload_after_second_delete["clients"] == {}

    get_deleted = requests.get(
        f"{base_url}/api/v1/ui-state",
        params={"client_id": client_id, "scope": search_scope},
        timeout=5,
    )
    assert get_deleted.status_code == 200
    get_deleted_payload = get_deleted.json()
    assert get_deleted_payload["code"] == 200
    assert get_deleted_payload["data"]["exists"] is False
    assert get_deleted_payload["data"]["state"] is None
