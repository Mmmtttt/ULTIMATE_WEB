from __future__ import annotations

import pytest
import requests


@pytest.mark.integration
def test_cache_stats_returns_valid_structure(integration_runtime):
    """
    用例描述:
    - 用例目的: 验证缓存统计接口返回正确的数据结构。
    - 测试步骤:
      1. 调用 GET /api/v1/config/cache/stats。
      2. 检查返回数据结构。
    - 预期结果:
      1. HTTP 200，业务 code=200。
      2. 返回数据包含缓存统计信息。
    - 历史变更:
      - 2026-03-26: 初始创建，覆盖缓存统计主链路。
    """
    base_url = integration_runtime["base_url"]

    response = requests.get(
        f"{base_url}/api/v1/config/cache/stats",
        timeout=5,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 200
    data = payload["data"]
    assert isinstance(data, dict)


@pytest.mark.integration
def test_cache_clear_returns_valid_structure(integration_runtime):
    """
    用例描述:
    - 用例目的: 验证缓存清理接口返回正确的数据结构。
    - 测试步骤:
      1. 调用 DELETE /api/v1/config/cache/clear。
      2. 检查返回数据结构。
    - 预期结果:
      1. HTTP 200，业务 code=200。
      2. 返回数据包含清理统计信息。
    - 历史变更:
      - 2026-03-26: 初始创建，覆盖缓存清理主链路。
    """
    base_url = integration_runtime["base_url"]

    response = requests.delete(
        f"{base_url}/api/v1/config/cache/clear",
        timeout=5,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 200
    data = payload["data"]
    assert isinstance(data, dict)
    assert "deleted_count" in data
    assert "freed_size_bytes" in data
    assert "freed_size_mb" in data


@pytest.mark.integration
def test_cache_clean_orphan_returns_valid_structure(integration_runtime):
    """
    用例描述:
    - 用例目的: 验证孤立缓存清理接口返回正确的数据结构。
    - 测试步骤:
      1. 调用 DELETE /api/v1/config/cache/clean-orphan。
      2. 检查返回数据结构。
    - 预期结果:
      1. HTTP 200，业务 code=200。
      2. 返回数据包含清理统计信息。
    - 历史变更:
      - 2026-03-26: 初始创建，覆盖孤立缓存清理主链路。
    """
    base_url = integration_runtime["base_url"]

    response = requests.delete(
        f"{base_url}/api/v1/config/cache/orphan",
        timeout=5,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 200
    data = payload["data"]
    assert isinstance(data, dict)
    assert "deleted_count" in data


@pytest.mark.integration
def test_config_get_returns_user_config(integration_runtime):
    """
    用例描述:
    - 用例目的: 验证获取配置接口返回正确的用户配置。
    - 测试步骤:
      1. 调用 GET /api/v1/config。
      2. 检查返回数据结构。
    - 预期结果:
      1. HTTP 200，业务 code=200。
      2. 返回数据包含用户配置信息。
    - 历史变更:
      - 2026-03-26: 初始创建，覆盖获取配置主链路。
    """
    base_url = integration_runtime["base_url"]

    response = requests.get(
        f"{base_url}/api/v1/config",
        timeout=5,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 200
    data = payload["data"]
    assert isinstance(data, dict)


@pytest.mark.integration
def test_config_update_validates_background_value(integration_runtime):
    """
    用例描述:
    - 用例目的: 验证配置更新接口校验背景值。
    - 测试步骤:
      1. 调用 PUT /api/v1/config 传入无效背景值。
      2. 检查返回错误码。
    - 预期结果:
      1. HTTP 200，业务 code=400。
    - 历史变更:
      - 2026-03-26: 初始创建，覆盖配置参数校验。
    """
    base_url = integration_runtime["base_url"]

    response = requests.put(
        f"{base_url}/api/v1/config",
        json={
            "default_page_mode": "left_right",
            "default_background": "invalid_color",
        },
        timeout=5,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 400


@pytest.mark.integration
def test_config_update_validates_page_mode_value(integration_runtime):
    """
    用例描述:
    - 用例目的: 验证配置更新接口校验翻页模式值。
    - 测试步骤:
      1. 调用 PUT /api/v1/config 传入无效翻页模式值。
      2. 检查返回错误码。
    - 预期结果:
      1. HTTP 200，业务 code=400。
    - 历史变更:
      - 2026-03-26: 初始创建，覆盖配置参数校验。
    """
    base_url = integration_runtime["base_url"]

    response = requests.put(
        f"{base_url}/api/v1/config",
        json={
            "default_page_mode": "invalid_mode",
            "default_background": "white",
        },
        timeout=5,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 400


@pytest.mark.integration
def test_config_data_path_returns_valid_structure(integration_runtime):
    """
    用例描述:
    - 用例目的: 验证获取缓存信息接口返回正确的数据结构。
    - 测试步骤:
      1. 调用 GET /api/v1/config/cache/info。
      2. 检查返回数据结构。
    - 预期结果:
      1. HTTP 200，业务 code=200。
      2. 返回数据包含缓存信息。
    - 历史变更:
      - 2026-03-26: 初始创建，覆盖获取缓存信息主链路。
    """
    base_url = integration_runtime["base_url"]

    response = requests.get(
        f"{base_url}/api/v1/config/cache/info",
        timeout=5,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 200
    data = payload["data"]
    assert isinstance(data, dict)


@pytest.mark.integration
def test_config_storage_info_returns_valid_structure(integration_runtime):
    """
    用例描述:
    - 用例目的: 验证获取系统信息接口返回正确的数据结构。
    - 测试步骤:
      1. 调用 GET /api/v1/config/system。
      2. 检查返回数据结构。
    - 预期结果:
      1. HTTP 200，业务 code=200。
      2. 返回数据包含系统信息。
    - 历史变更:
      - 2026-03-26: 初始创建，覆盖获取系统信息主链路。
    """
    base_url = integration_runtime["base_url"]

    response = requests.get(
        f"{base_url}/api/v1/config/system",
        timeout=5,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 200
    data = payload["data"]
    assert isinstance(data, dict)
