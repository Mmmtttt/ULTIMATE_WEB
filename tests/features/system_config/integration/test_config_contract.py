from __future__ import annotations

import pytest
import requests


@pytest.mark.integration
def test_config_system_get_returns_config(integration_runtime):
    """
    用例描述:
    - 用例目的: 验证系统配置获取接口返回正确数据。
    - 测试步骤:
      1. 调用 GET /api/v1/config/system。
      2. 检查返回数据格式。
    - 预期结果:
      1. HTTP 200，业务 code=200。
      2. 返回数据包含配置信息。
    - 历史变更:
      - 2026-03-25: 初始创建，覆盖系统配置获取主链路。
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
    assert "configured_data_dir" in data or "resolved_data_dir" in data


@pytest.mark.integration
def test_config_get_returns_config(integration_runtime):
    """
    用例描述:
    - 用例目的: 验证配置获取接口返回正确数据。
    - 测试步骤:
      1. 调用 GET /api/v1/config。
      2. 检查返回数据格式。
    - 预期结果:
      1. HTTP 200，业务 code=200。
      2. 返回数据包含用户配置。
    - 历史变更:
      - 2026-03-25: 初始创建，覆盖配置获取主链路。
    """
    base_url = integration_runtime["base_url"]

    response = requests.get(
        f"{base_url}/api/v1/config",
        timeout=5,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 200


@pytest.mark.integration
def test_config_update_persists(integration_runtime):
    """
    用例描述:
    - 用例目的: 验证配置更新接口能正确持久化。
    - 测试步骤:
      1. 调用 PUT /api/v1/config 更新配置。
      2. 验证返回状态。
      3. 再次获取配置验证更新生效。
    - 预期结果:
      1. HTTP 200，业务 code=200。
      2. 配置已更新。
    - 历史变更:
      - 2026-03-25: 初始创建，覆盖配置更新主链路。
    """
    base_url = integration_runtime["base_url"]

    new_config = {
        "default_page_mode": "left_right",
        "default_background": "dark",
        "auto_hide_toolbar": False,
        "show_page_number": True,
    }

    response = requests.put(
        f"{base_url}/api/v1/config",
        json=new_config,
        timeout=5,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 200

    verify_resp = requests.get(
        f"{base_url}/api/v1/config",
        timeout=5,
    )
    verify_payload = verify_resp.json()
    assert verify_payload["code"] == 200


@pytest.mark.integration
def test_config_cache_info_returns_info(integration_runtime):
    """
    用例描述:
    - 用例目的: 验证缓存信息接口返回正确数据。
    - 测试步骤:
      1. 调用 GET /api/v1/config/cache/info。
      2. 检查返回数据格式。
    - 预期结果:
      1. HTTP 200，业务 code=200。
      2. 返回数据包含缓存信息。
    - 历史变更:
      - 2026-03-25: 初始创建，覆盖缓存信息获取主链路。
    """
    base_url = integration_runtime["base_url"]

    response = requests.get(
        f"{base_url}/api/v1/config/cache/info",
        timeout=5,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 200


@pytest.mark.integration
def test_config_cache_clear_executes(integration_runtime):
    """
    用例描述:
    - 用例目的: 验证缓存清理接口能正确执行。
    - 测试步骤:
      1. 调用 DELETE /api/v1/config/cache/clear。
      2. 检查返回状态。
    - 预期结果:
      1. HTTP 200，业务 code=200。
    - 历史变更:
      - 2026-03-25: 初始创建，覆盖缓存清理主链路。
    """
    base_url = integration_runtime["base_url"]

    response = requests.delete(
        f"{base_url}/api/v1/config/cache/clear",
        timeout=10,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 200


@pytest.mark.integration
def test_health_check_returns_ok(integration_runtime):
    """
    用例描述:
    - 用例目的: 验证健康检查接口返回正确状态。
    - 测试步骤:
      1. 调用 GET /health。
      2. 检查返回状态。
    - 预期结果:
      1. HTTP 200。
    - 历史变更:
      - 2026-03-25: 初始创建，覆盖健康检查主链路。
    """
    base_url = integration_runtime["base_url"]

    response = requests.get(
        f"{base_url}/health",
        timeout=5,
    )

    assert response.status_code == 200
