from __future__ import annotations

import pytest
import requests


@pytest.mark.integration
def test_backup_info_returns_all_targets(integration_runtime):
    """
    用例描述:
    - 用例目的: 验证备份信息接口返回所有目标的备份状态。
    - 测试步骤:
      1. 调用 GET /api/v1/backup/info。
      2. 检查返回数据包含所有备份目标。
    - 预期结果:
      1. HTTP 200，业务 code=200。
      2. 返回数据包含备份信息。
    - 历史变更:
      - 2026-03-25: 初始创建，覆盖备份信息查询主链路。
    """
    base_url = integration_runtime["base_url"]

    response = requests.get(
        f"{base_url}/api/v1/backup/info",
        timeout=5,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 200
    data = payload["data"]
    assert isinstance(data, dict)


@pytest.mark.integration
def test_backup_trigger_creates_backup(integration_runtime):
    """
    用例描述:
    - 用例目的: 验证手动触发备份接口能正确创建备份。
    - 测试步骤:
      1. 调用 POST /api/v1/backup/trigger 触发备份。
      2. 检查返回状态。
    - 预期结果:
      1. HTTP 200，业务 code=200。
      2. 返回数据包含备份信息。
    - 历史变更:
      - 2026-03-25: 初始创建，覆盖手动触发备份主链路。
    """
    base_url = integration_runtime["base_url"]

    response = requests.post(
        f"{base_url}/api/v1/backup/trigger",
        json={"target": "home"},
        timeout=10,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 200
    data = payload["data"]
    assert "home" in data


@pytest.mark.integration
def test_backup_trigger_all_targets(integration_runtime):
    """
    用例描述:
    - 用例目的: 验证触发所有目标备份接口能正确执行。
    - 测试步骤:
      1. 调用 POST /api/v1/backup/trigger 不指定 target。
      2. 检查返回状态。
    - 预期结果:
      1. HTTP 200，业务 code=200。
      2. 返回数据包含所有目标备份信息。
    - 历史变更:
      - 2026-03-25: 初始创建，覆盖全量备份触发。
    """
    base_url = integration_runtime["base_url"]

    response = requests.post(
        f"{base_url}/api/v1/backup/trigger",
        json={"target": "all"},
        timeout=15,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 200
    data = payload["data"]
    assert "home" in data
    assert "recommendation" in data
    assert "video" in data
    assert "video_recommendation" in data


@pytest.mark.integration
def test_backup_restore_from_tier(integration_runtime):
    """
    用例描述:
    - 用例目的: 验证从指定层级恢复备份接口能正确执行。
    - 测试步骤:
      1. 先触发备份。
      2. 调用 POST /api/v1/backup/restore 从 tier 1 恢复。
      3. 检查返回状态。
    - 预期结果:
      1. HTTP 200，业务 code=200。
      2. 返回数据表明恢复成功。
    - 历史变更:
      - 2026-03-25: 初始创建，覆盖备份恢复主链路。
    """
    base_url = integration_runtime["base_url"]

    requests.post(
        f"{base_url}/api/v1/backup/trigger",
        json={"target": "home"},
        timeout=10,
    )

    response = requests.post(
        f"{base_url}/api/v1/backup/restore",
        json={"target": "home", "tier": 1},
        timeout=10,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 200
    data = payload["data"]
    assert data.get("restored") is True


@pytest.mark.integration
def test_backup_restore_rejects_invalid_target(integration_runtime):
    """
    用例描述:
    - 用例目的: 验证备份恢复接口校验目标参数。
    - 测试步骤:
      1. 调用 POST /api/v1/backup/restore 使用无效 target。
      2. 检查返回错误码。
    - 预期结果:
      1. HTTP 200，业务 code=400。
    - 历史变更:
      - 2026-03-25: 初始创建，覆盖备份恢复参数校验。
    """
    base_url = integration_runtime["base_url"]

    response = requests.post(
        f"{base_url}/api/v1/backup/restore",
        json={"target": "invalid_target", "tier": 1},
        timeout=5,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 400


@pytest.mark.integration
def test_backup_restore_rejects_invalid_tier(integration_runtime):
    """
    用例描述:
    - 用例目的: 验证备份恢复接口校验层级参数。
    - 测试步骤:
      1. 调用 POST /api/v1/backup/restore 使用无效 tier。
      2. 检查返回错误码。
    - 预期结果:
      1. HTTP 200，业务 code=400。
    - 历史变更:
      - 2026-03-25: 初始创建，覆盖备份恢复层级校验。
    """
    base_url = integration_runtime["base_url"]

    response = requests.post(
        f"{base_url}/api/v1/backup/restore",
        json={"target": "home", "tier": 5},
        timeout=5,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 400
