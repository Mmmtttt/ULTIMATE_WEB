from __future__ import annotations

import importlib
from pathlib import Path

import pytest


@pytest.mark.integration
def test_system_config_update_invokes_third_party_storage_path_rebase_hook(third_party_client, monkeypatch):
    """
    Case Description:
    - Purpose: Guard `PUT /api/v1/config/system` third-party hook contract so `data_dir` updates always trigger
      `_update_third_party_storage_paths(old_data_dir, new_data_dir)`.
    - Steps:
      1. Read current runtime `data_dir` from `/api/v1/config/system`.
      2. Mock `_update_third_party_storage_paths` and `_restart_backend_later`.
      3. Update system config with a new isolated target dir, `migrate_data=false`, `restart_now=false`.
      4. Verify hook call arguments and response payload.
    - Expected:
      1. HTTP 200 with business `code=200`.
      2. Hook is called exactly once with previous and new absolute data paths.
      3. No restart is scheduled when `restart_now=false`.
    - History:
      - 2026-03-23: Added third-party storage-path hook contract test for system config update.
    """
    client = third_party_client["client"]
    runtime_root = Path(third_party_client["runtime_root"])
    config_api = importlib.import_module("api.v1.config")
    captured = {"path_hook": [], "restart": 0}

    get_resp = client.get("/api/v1/config/system")
    get_payload = get_resp.get_json()
    assert get_resp.status_code == 200
    assert get_payload["code"] == 200
    old_runtime_dir = str(get_payload["data"]["current_runtime_data_dir"])

    new_data_dir = (runtime_root / "data_rebased").resolve()

    monkeypatch.setattr(
        config_api,
        "_update_third_party_storage_paths",
        lambda old_data_dir, new_data_dir_value: captured["path_hook"].append(
            (str(old_data_dir), str(new_data_dir_value))
        ),
    )
    monkeypatch.setattr(
        config_api,
        "_restart_backend_later",
        lambda delay_seconds=1.0: captured.__setitem__("restart", captured["restart"] + 1),
    )

    put_resp = client.put(
        "/api/v1/config/system",
        json={
            "data_dir": str(new_data_dir),
            "migrate_data": False,
            "restart_now": False,
        },
    )
    put_payload = put_resp.get_json()

    assert put_resp.status_code == 200
    assert put_payload["code"] == 200
    assert put_payload["data"]["resolved_data_dir"] == str(new_data_dir)
    assert put_payload["data"]["restart_scheduled"] is False
    assert put_payload["data"]["requires_restart"] is True
    assert captured["restart"] == 0
    assert captured["path_hook"] == [(old_runtime_dir, str(new_data_dir))]
