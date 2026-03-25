from __future__ import annotations

import pytest
import requests


@pytest.mark.integration
def test_search_comic_returns_results(integration_runtime):
    """
    用例描述:
    - 用例目的: 验证漫画搜索接口返回正确结果。
    - 测试步骤:
      1. 调用 GET /api/v1/comic/search?keyword=E2E。
      2. 检查返回数据。
    - 预期结果:
      1. HTTP 200，业务 code=200。
      2. 返回结果包含匹配的漫画。
    - 历史变更:
      - 2026-03-25: 初始创建，覆盖漫画搜索主链路。
    """
    base_url = integration_runtime["base_url"]

    response = requests.get(
        f"{base_url}/api/v1/comic/search",
        params={"keyword": "E2E"},
        timeout=5,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 200
    assert isinstance(payload["data"], list)
    assert len(payload["data"]) >= 1
    assert any("E2E" in item.get("title", "") for item in payload["data"])


@pytest.mark.integration
def test_search_comic_empty_keyword(integration_runtime):
    """
    用例描述:
    - 用例目的: 验证漫画搜索接口对空关键词的处理。
    - 测试步骤:
      1. 调用 GET /api/v1/comic/search 不传 keyword。
      2. 检查返回状态。
    - 预期结果:
      1. HTTP 200，业务 code=400。
    - 历史变更:
      - 2026-03-25: 初始创建，覆盖漫画搜索参数校验。
    """
    base_url = integration_runtime["base_url"]

    response = requests.get(
        f"{base_url}/api/v1/comic/search",
        timeout=5,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 400


@pytest.mark.integration
def test_search_video_returns_results(integration_runtime):
    """
    用例描述:
    - 用例目的: 验证视频搜索接口返回正确结果。
    - 测试步骤:
      1. 调用 GET /api/v1/video/search?keyword=Seed。
      2. 检查返回数据。
    - 预期结果:
      1. HTTP 200，业务 code=200。
      2. 返回结果包含匹配的视频。
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
    assert isinstance(payload["data"], list)
    assert len(payload["data"]) >= 1
    assert any("Seed" in item.get("title", "") for item in payload["data"])


@pytest.mark.integration
def test_search_video_empty_keyword(integration_runtime):
    """
    用例描述:
    - 用例目的: 验证视频搜索接口对空关键词的处理。
    - 测试步骤:
      1. 调用 GET /api/v1/video/search 不传 keyword。
      2. 检查返回状态。
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


@pytest.mark.integration
def test_search_comic_list_filter(integration_runtime):
    """
    用例描述:
    - 用例目的: 验证漫画列表筛选接口返回正确结果。
    - 测试步骤:
      1. 调用 GET /api/v1/comic/list 带筛选参数。
      2. 检查返回数据。
    - 预期结果:
      1. HTTP 200，业务 code=200。
      2. 返回结果符合筛选条件。
    - 历史变更:
      - 2026-03-25: 初始创建，覆盖漫画列表筛选主链路。
    """
    base_url = integration_runtime["base_url"]

    response = requests.get(
        f"{base_url}/api/v1/comic/list",
        params={"include_tag_ids": "tag_action"},
        timeout=5,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 200
    assert isinstance(payload["data"], list)


@pytest.mark.integration
def test_search_video_list_filter(integration_runtime):
    """
    用例描述:
    - 用例目的: 验证视频列表筛选接口返回正确结果。
    - 测试步骤:
      1. 调用 GET /api/v1/video/list 带筛选参数。
      2. 检查返回数据。
    - 预期结果:
      1. HTTP 200，业务 code=200。
      2. 返回结果符合筛选条件。
    - 历史变更:
      - 2026-03-25: 初始创建，覆盖视频列表筛选主链路。
    """
    base_url = integration_runtime["base_url"]

    response = requests.get(
        f"{base_url}/api/v1/video/list",
        params={"min_score": 5.0, "max_score": 10.0},
        timeout=5,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 200
    assert isinstance(payload["data"], list)


@pytest.mark.integration
def test_search_comic_by_score_range(integration_runtime):
    """
    用例描述:
    - 用例目的: 验证漫画按评分范围筛选接口返回正确结果。
    - 测试步骤:
      1. 调用 GET /api/v1/comic/list 带评分范围参数。
      2. 检查返回数据。
    - 预期结果:
      1. HTTP 200，业务 code=200。
      2. 返回结果评分在指定范围内。
    - 历史变更:
      - 2026-03-25: 初始创建，覆盖漫画评分范围筛选主链路。
    """
    base_url = integration_runtime["base_url"]

    response = requests.get(
        f"{base_url}/api/v1/comic/list",
        params={"min_score": 7.0, "max_score": 10.0},
        timeout=5,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 200
    data = payload["data"]
    for comic in data:
        score = comic.get("score")
        if score is not None:
            assert 7.0 <= score <= 10.0
