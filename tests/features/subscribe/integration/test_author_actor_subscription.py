from __future__ import annotations

from uuid import uuid4

import pytest
import requests

from tests.shared.runtime_data import find_by_id, load_json


@pytest.mark.integration
def test_author_subscribe_creates_subscription(integration_runtime):
    """
    用例描述:
    - 用例目的: 验证作者订阅接口能正确创建订阅记录。
    - 测试步骤:
      1. 调用 POST /api/v1/author/subscribe 订阅作者。
      2. 检查返回状态和数据。
      3. 验证文件中新增订阅记录。
    - 预期结果:
      1. HTTP 200，业务 code=200。
      2. 返回数据包含作者信息。
      3. authors_database.json 中新增记录。
    - 历史变更:
      - 2026-03-25: 初始创建，覆盖作者订阅主链路。
    """
    base_url = integration_runtime["base_url"]
    meta_dir = integration_runtime["meta_dir"]
    authors_path = meta_dir / "authors_database.json"

    author_name = f"Test Author {uuid4().hex[:8]}"

    response = requests.post(
        f"{base_url}/api/v1/author/subscribe",
        json={"name": author_name},
        timeout=5,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 200
    assert payload["data"]["name"] == author_name

    authors_data = load_json(authors_path)
    authors = authors_data.get("authors", [])
    created = next((a for a in authors if a.get("name") == author_name), None)
    assert created is not None


@pytest.mark.integration
def test_author_subscribe_rejects_missing_name(integration_runtime):
    """
    用例描述:
    - 用例目的: 验证作者订阅接口校验必要参数。
    - 测试步骤:
      1. 调用 POST /api/v1/author/subscribe 不传 name。
      2. 检查返回错误码。
    - 预期结果:
      1. HTTP 200，业务 code=400。
    - 历史变更:
      - 2026-03-25: 初始创建，覆盖作者订阅参数校验。
    """
    base_url = integration_runtime["base_url"]

    response = requests.post(
        f"{base_url}/api/v1/author/subscribe",
        json={},
        timeout=5,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 400


@pytest.mark.integration
def test_author_unsubscribe_removes_subscription(integration_runtime):
    """
    用例描述:
    - 用例目的: 验证取消作者订阅接口能正确移除订阅记录。
    - 测试步骤:
      1. 先订阅作者。
      2. 调用 DELETE /api/v1/author/unsubscribe 取消订阅。
      3. 验证文件中记录已移除。
    - 预期结果:
      1. HTTP 200，业务 code=200。
      2. 记录从 authors_database.json 中移除。
    - 历史变更:
      - 2026-03-25: 初始创建，覆盖取消作者订阅主链路。
    """
    base_url = integration_runtime["base_url"]
    meta_dir = integration_runtime["meta_dir"]
    authors_path = meta_dir / "authors_database.json"

    author_name = f"Unsub Author {uuid4().hex[:8]}"

    subscribe_resp = requests.post(
        f"{base_url}/api/v1/author/subscribe",
        json={"name": author_name},
        timeout=5,
    )
    author_id = subscribe_resp.json()["data"]["id"]

    response = requests.delete(
        f"{base_url}/api/v1/author/unsubscribe",
        json={"author_id": author_id},
        timeout=5,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 200

    authors_data = load_json(authors_path)
    authors = authors_data.get("authors", [])
    assert find_by_id(authors, author_id) is None


@pytest.mark.integration
def test_author_list_returns_subscriptions(integration_runtime):
    """
    用例描述:
    - 用例目的: 验证获取作者订阅列表接口返回正确数据。
    - 测试步骤:
      1. 先订阅作者。
      2. 调用 GET /api/v1/author/list。
      3. 检查返回数据包含订阅的作者。
    - 预期结果:
      1. HTTP 200，业务 code=200。
      2. 返回列表包含订阅的作者。
    - 历史变更:
      - 2026-03-25: 初始创建，覆盖作者订阅列表查询。
    """
    base_url = integration_runtime["base_url"]

    author_name = f"List Author {uuid4().hex[:8]}"
    requests.post(
        f"{base_url}/api/v1/author/subscribe",
        json={"name": author_name},
        timeout=5,
    )

    response = requests.get(
        f"{base_url}/api/v1/author/list",
        timeout=5,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 200
    assert isinstance(payload["data"], list)
    assert any(a.get("name") == author_name for a in payload["data"])


@pytest.mark.integration
def test_author_all_returns_all_authors(integration_runtime):
    """
    用例描述:
    - 用例目的: 验证获取所有作者接口返回正确数据。
    - 测试步骤:
      1. 调用 GET /api/v1/author/all。
      2. 检查返回数据。
    - 预期结果:
      1. HTTP 200，业务 code=200。
      2. 返回作者列表。
    - 历史变更:
      - 2026-03-25: 初始创建，覆盖获取所有作者主链路。
    """
    base_url = integration_runtime["base_url"]

    response = requests.get(
        f"{base_url}/api/v1/author/all",
        timeout=5,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 200
    assert isinstance(payload["data"], list)


@pytest.mark.integration
def test_actor_subscribe_creates_subscription(integration_runtime):
    """
    用例描述:
    - 用例目的: 验证演员订阅接口能正确创建订阅记录。
    - 测试步骤:
      1. 调用 POST /api/v1/actor/subscribe 订阅演员。
      2. 检查返回状态和数据。
      3. 验证文件中新增订阅记录。
    - 预期结果:
      1. HTTP 200，业务 code=200。
      2. 返回数据包含演员信息。
      3. actors_database.json 中新增记录。
    - 历史变更:
      - 2026-03-25: 初始创建，覆盖演员订阅主链路。
    """
    base_url = integration_runtime["base_url"]
    meta_dir = integration_runtime["meta_dir"]
    actors_path = meta_dir / "actors_database.json"

    actor_name = f"Test Actor {uuid4().hex[:8]}"

    response = requests.post(
        f"{base_url}/api/v1/actor/subscribe",
        json={"name": actor_name},
        timeout=5,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 200
    assert payload["data"]["name"] == actor_name

    actors_data = load_json(actors_path)
    actors = actors_data.get("actors", [])
    created = next((a for a in actors if a.get("name") == actor_name), None)
    assert created is not None


@pytest.mark.integration
def test_actor_subscribe_rejects_missing_name(integration_runtime):
    """
    用例描述:
    - 用例目的: 验证演员订阅接口校验必要参数。
    - 测试步骤:
      1. 调用 POST /api/v1/actor/subscribe 不传 name。
      2. 检查返回错误码。
    - 预期结果:
      1. HTTP 200，业务 code=400。
    - 历史变更:
      - 2026-03-25: 初始创建，覆盖演员订阅参数校验。
    """
    base_url = integration_runtime["base_url"]

    response = requests.post(
        f"{base_url}/api/v1/actor/subscribe",
        json={},
        timeout=5,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 400


@pytest.mark.integration
def test_actor_unsubscribe_removes_subscription(integration_runtime):
    """
    用例描述:
    - 用例目的: 验证取消演员订阅接口能正确移除订阅记录。
    - 测试步骤:
      1. 先订阅演员。
      2. 调用 DELETE /api/v1/actor/unsubscribe 取消订阅。
      3. 验证文件中记录已移除。
    - 预期结果:
      1. HTTP 200，业务 code=200。
      2. 记录从 actors_database.json 中移除。
    - 历史变更:
      - 2026-03-25: 初始创建，覆盖取消演员订阅主链路。
    """
    base_url = integration_runtime["base_url"]
    meta_dir = integration_runtime["meta_dir"]
    actors_path = meta_dir / "actors_database.json"

    actor_name = f"Unsub Actor {uuid4().hex[:8]}"

    subscribe_resp = requests.post(
        f"{base_url}/api/v1/actor/subscribe",
        json={"name": actor_name},
        timeout=5,
    )
    actor_id = subscribe_resp.json()["data"]["id"]

    response = requests.delete(
        f"{base_url}/api/v1/actor/unsubscribe",
        json={"actor_id": actor_id},
        timeout=5,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 200

    actors_data = load_json(actors_path)
    actors = actors_data.get("actors", [])
    assert find_by_id(actors, actor_id) is None


@pytest.mark.integration
def test_actor_list_returns_subscriptions(integration_runtime):
    """
    用例描述:
    - 用例目的: 验证获取演员订阅列表接口返回正确数据。
    - 测试步骤:
      1. 先订阅演员。
      2. 调用 GET /api/v1/actor/list。
      3. 检查返回数据包含订阅的演员。
    - 预期结果:
      1. HTTP 200，业务 code=200。
      2. 返回列表包含订阅的演员。
    - 历史变更:
      - 2026-03-25: 初始创建，覆盖演员订阅列表查询。
    """
    base_url = integration_runtime["base_url"]

    actor_name = f"List Actor {uuid4().hex[:8]}"
    requests.post(
        f"{base_url}/api/v1/actor/subscribe",
        json={"name": actor_name},
        timeout=5,
    )

    response = requests.get(
        f"{base_url}/api/v1/actor/list",
        timeout=5,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 200
    assert isinstance(payload["data"], list)
    assert any(a.get("name") == actor_name for a in payload["data"])


@pytest.mark.integration
def test_actor_all_returns_all_actors(integration_runtime):
    """
    用例描述:
    - 用例目的: 验证获取所有演员接口返回正确数据。
    - 测试步骤:
      1. 调用 GET /api/v1/actor/all。
      2. 检查返回数据。
    - 预期结果:
      1. HTTP 200，业务 code=200。
      2. 返回演员列表。
    - 历史变更:
      - 2026-03-25: 初始创建，覆盖获取所有演员主链路。
    """
    base_url = integration_runtime["base_url"]

    response = requests.get(
        f"{base_url}/api/v1/actor/all",
        timeout=5,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 200
    assert isinstance(payload["data"], list)


@pytest.mark.integration
def test_actor_clear_new_count(integration_runtime):
    """
    用例描述:
    - 用例目的: 验证清除演员新作品计数接口能正确执行。
    - 测试步骤:
      1. 先订阅演员。
      2. 调用 POST /api/v1/actor/clear-new-count/<actor_id>。
      3. 检查返回状态。
    - 预期结果:
      1. HTTP 200，业务 code=200。
    - 历史变更:
      - 2026-03-25: 初始创建，覆盖清除新作品计数主链路。
    """
    base_url = integration_runtime["base_url"]

    actor_name = f"Clear Count Actor {uuid4().hex[:8]}"
    subscribe_resp = requests.post(
        f"{base_url}/api/v1/actor/subscribe",
        json={"name": actor_name},
        timeout=5,
    )
    actor_id = subscribe_resp.json()["data"]["id"]

    response = requests.post(
        f"{base_url}/api/v1/actor/clear-new-count/{actor_id}",
        timeout=5,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 200
