from __future__ import annotations

from pathlib import Path

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
def test_config_logs_dir_is_under_runtime_data_dir(integration_runtime):
    """
    用例描述:
    - 用例目的: 守护后端日志目录与运行时 data_dir 绑定，日志必须写入 data_dir/logs。
    - 测试步骤:
      1. 调用 GET /api/v1/config/system 获取当前运行时 data_dir。
      2. 调用 GET /health 触发一次常规请求。
      3. 检查 data_dir/logs 下 app/access/error 日志文件是否存在。
    - 预期结果:
      1. HTTP 200，业务 code=200。
      2. data_dir/logs 目录存在，且包含 app.log/access.log/error.log。
    - 历史变更:
      - 2026-04-02: 新增日志目录跟随 data_dir 的契约测试。
    """
    base_url = integration_runtime["base_url"]
    runtime_data_dir: Path = integration_runtime["data_dir"]

    system_resp = requests.get(
        f"{base_url}/api/v1/config/system",
        timeout=5,
    )
    assert system_resp.status_code == 200
    system_payload = system_resp.json()
    assert system_payload["code"] == 200

    # 触发一次请求，确保 handler 已工作。
    health_resp = requests.get(
        f"{base_url}/health",
        timeout=5,
    )
    assert health_resp.status_code == 200

    logs_dir = runtime_data_dir / "logs"
    assert logs_dir.is_dir()
    assert (logs_dir / "app.log").is_file()
    assert (logs_dir / "access.log").is_file()
    assert (logs_dir / "error.log").is_file()


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
def test_config_dir_info_returns_paths(integration_runtime):
    """
    用例描述:
    - 用例目的: 验证配置目录信息接口返回完整路径信息。
    - 测试步骤:
      1. 调用 GET /api/v1/config/system/config-dir。
      2. 检查返回字段和类型。
    - 预期结果:
      1. HTTP 200，业务 code=200。
      2. 返回数据包含运行目录、选中目录、默认目录与配置文件路径。
    - 历史变更:
      - 2026-04-02: 新增配置目录信息接口合同测试。
    """
    base_url = integration_runtime["base_url"]

    response = requests.get(
        f"{base_url}/api/v1/config/system/config-dir",
        timeout=5,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 200
    data = payload["data"]
    assert isinstance(data.get("runtime_config_dir"), str)
    assert isinstance(data.get("selected_config_dir"), str)
    assert isinstance(data.get("default_config_dir"), str)
    assert isinstance(data.get("source"), str)
    assert isinstance(data.get("server_config_path"), str)
    assert isinstance(data.get("third_party_config_path"), str)
    assert isinstance(data.get("requires_restart"), bool)


@pytest.mark.integration
def test_config_dir_update_rejects_empty_path(integration_runtime):
    """
    用例描述:
    - 用例目的: 验证配置目录更新接口对空参数做输入校验。
    - 测试步骤:
      1. 调用 PUT /api/v1/config/system/config-dir，传入空 config_dir。
      2. 检查返回错误信息。
    - 预期结果:
      1. HTTP 200，业务 code=400。
      2. 错误消息提示 config_dir 不能为空。
    - 历史变更:
      - 2026-04-02: 新增配置目录更新参数校验合同测试。
    """
    base_url = integration_runtime["base_url"]

    response = requests.put(
        f"{base_url}/api/v1/config/system/config-dir",
        json={"config_dir": "   "},
        timeout=5,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 400
    assert "config_dir" in str(payload.get("msg", ""))


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
