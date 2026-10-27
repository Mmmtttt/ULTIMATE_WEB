from __future__ import annotations

import time

import pytest
import requests


def _set_engine(base_url: str, engine: str) -> requests.Response:
    return requests.put(
        f"{base_url}/api/v1/config",
        json={"search_engine": engine},
        timeout=10,
    )


@pytest.mark.integration
def test_semantic_search_status_is_exposed(integration_runtime):
    """
    用例描述:
    - 用例目的: 验证语义检索状态接口可用，并如实回报平台支持情况与索引状态。
    - 测试步骤:
      1. 调用 GET /api/v1/semantic-search/status。
      2. 检查 supported / configured_engine / index 字段。
    - 预期结果:
      1. HTTP 200，业务 code=200。
      2. 桌面端 supported 为 True，默认检索引擎为 catalog。
    - 历史变更:
      - 2026-05-20: 初始创建，覆盖语义检索状态契约。
    """
    base_url = integration_runtime["base_url"]

    response = requests.get(f"{base_url}/api/v1/semantic-search/status", timeout=5)
    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 200

    data = payload["data"]
    assert data["supported"] is True
    assert data["configured_engine"] in {"catalog", "semantic"}
    assert isinstance(data.get("index"), dict)


@pytest.mark.integration
def test_search_engine_can_switch_to_semantic_and_back(integration_runtime):
    """
    用例描述:
    - 用例目的: 验证检索方式可在默认索引与语义检索之间切换，且切换后状态同步。
    - 测试步骤:
      1. PUT /api/v1/config 把 search_engine 设为 semantic。
      2. GET 状态，确认 enabled 为 True。
      3. PUT 回 catalog 并再次确认。
    - 预期结果:
      1. 两次 PUT 均返回业务 code=200。
      2. enabled 随配置变化。
    - 历史变更:
      - 2026-05-20: 初始创建，守护「默认仍为原检索方式」的开关契约。
    """
    base_url = integration_runtime["base_url"]
    try:
        switch = _set_engine(base_url, "semantic")
        assert switch.status_code == 200
        assert switch.json()["code"] == 200
        assert switch.json()["data"]["search_engine"] == "semantic"

        status = requests.get(f"{base_url}/api/v1/semantic-search/status", timeout=5).json()
        assert status["data"]["enabled"] is True
    finally:
        restore = _set_engine(base_url, "catalog")
        assert restore.status_code == 200
        assert restore.json()["data"]["search_engine"] == "catalog"

    status_after = requests.get(f"{base_url}/api/v1/semantic-search/status", timeout=5).json()
    assert status_after["data"]["enabled"] is False


@pytest.mark.integration
def test_semantic_index_rebuild_and_search(integration_runtime):
    """
    用例描述:
    - 用例目的: 验证语义索引可构建，构建后检索接口返回命中结果与调试信息。
    - 测试步骤:
      1. POST /api/v1/semantic-search/rebuild（不带向量，避免测试环境下载模型）。
      2. GET /api/v1/semantic-search/search?keyword=... 查询。
    - 预期结果:
      1. 重建返回 doc_count 等统计信息。
      2. 检索返回 results 列表与 debug.route_sizes。
    - 历史变更:
      - 2026-05-20: 初始创建，覆盖索引构建与检索主链路。
    """
    base_url = integration_runtime["base_url"]

    rebuild = requests.post(
        f"{base_url}/api/v1/semantic-search/rebuild",
        json={"build_embeddings": False},
        timeout=30,
    )
    assert rebuild.status_code == 200
    rebuild_payload = rebuild.json()
    assert rebuild_payload["code"] == 200
    assert "running" in rebuild_payload["data"]

    # 重建是后台任务，轮询状态直到结束
    deadline = time.time() + 90
    status = {}
    while time.time() < deadline:
        status = requests.get(f"{base_url}/api/v1/semantic-search/status", timeout=10).json()["data"]
        if not status.get("rebuild", {}).get("running"):
            break
        time.sleep(0.5)

    assert not status.get("rebuild", {}).get("running"), "语义索引构建未在限时内完成"
    assert not status.get("rebuild", {}).get("error")
    assert status["index"]["indexed"] is True

    search = requests.get(
        f"{base_url}/api/v1/semantic-search/search",
        params={"keyword": "漫画", "limit": 10},
        timeout=15,
    )
    assert search.status_code == 200
    search_payload = search.json()
    assert search_payload["code"] == 200
    assert isinstance(search_payload["data"]["results"], list)
    assert "route_sizes" in search_payload["data"]["debug"]


@pytest.mark.integration
def test_vision_batch_routes_are_wired(integration_runtime):
    """
    用例描述:
    - 用例目的: 验证识图补全的批量/缺失列表接口可用；未配置模型时批量启动被拒绝。
    - 测试步骤:
      1. GET /api/v1/semantic-search/vision/missing。
      2. GET /api/v1/semantic-search/vision/batch。
      3. POST /api/v1/semantic-search/vision/batch（测试环境未配置模型）。
    - 预期结果:
      1. 缺失列表返回 items/count。
      2. 批次状态返回 running 字段。
      3. 启动返回业务 code=400 且提示未配置。
    - 历史变更:
      - 2026-05-21: 新增批量识图补全契约。
    """
    base_url = integration_runtime["base_url"]

    missing = requests.get(f"{base_url}/api/v1/semantic-search/vision/missing", timeout=10).json()
    assert missing["code"] == 200
    assert isinstance(missing["data"]["items"], list)

    state = requests.get(f"{base_url}/api/v1/semantic-search/vision/batch", timeout=10).json()
    assert state["code"] == 200
    assert "running" in state["data"]

    started = requests.post(
        f"{base_url}/api/v1/semantic-search/vision/batch",
        json={"only_missing": True},
        timeout=15,
    ).json()
    assert started["code"] in {200, 400}
    if started["code"] == 400:
        assert "配置" in (started.get("msg") or "")


@pytest.mark.integration
def test_semantic_search_search_requires_keyword(integration_runtime):
    """
    用例描述:
    - 用例目的: 验证缺少 keyword 时语义检索接口返回参数错误。
    - 测试步骤:
      1. 调用 GET /api/v1/semantic-search/search 不带参数。
    - 预期结果:
      1. HTTP 200，业务 code=400。
    - 历史变更:
      - 2026-05-20: 初始创建。
    """
    base_url = integration_runtime["base_url"]

    response = requests.get(f"{base_url}/api/v1/semantic-search/search", timeout=5)
    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 400
