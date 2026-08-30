"""Aria2 插件协议测试。

覆盖：
- manifest 能被真实 third_party 目录扫描发现，且声明了下载能力
- provider 能被 ProviderManager 动态加载
- normalize_config / serialize_public_config（secret 脱敏）
- get_query_status 配置就绪判断
- download.magnet.add 构造正确的 aria2.addUri RPC 载荷
- download.task.status / list / remove 的结果转换与分发
- Aria2 错误响应与未启用插件的行为
"""
import json
import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import requests

from protocol.provider_manager import ProviderManager
from protocol.registry import PluginRegistry

ARIA2_PLUGIN_ID = "download.aria2"
THIRD_PARTY_ROOT = BACKEND_ROOT / "third_party"


class FakeResponse:
    def __init__(self, result=None, error=None, status_code=200, text=""):
        self.status_code = status_code
        self._result = result
        self._error = error
        self.text = text or json.dumps(self._to_body())

    def _to_body(self):
        body = {"jsonrpc": "2.0", "id": "x"}
        if self._error is not None:
            body["error"] = self._error
        else:
            body["result"] = self._result
        return body

    def json(self):
        return self._to_body()


class FakeAria2Rpc:
    """按 method 分发响应的 Aria2 JSON-RPC 桩。"""

    def __init__(self):
        self.calls: list[dict] = []
        self.results: dict = {}

    def register(self, method, result=None, error=None):
        self.results[method] = {"result": result, "error": error}

    def __call__(self, url, json=None, timeout=None):
        body = dict(json or {})
        self.calls.append(body)
        method = body.get("method", "")
        spec = self.results.get(method, {})
        if spec.get("error") is not None:
            return FakeResponse(error=spec["error"])
        return FakeResponse(result=spec.get("result"))


def _make_provider():
    registry = PluginRegistry(search_root=str(THIRD_PARTY_ROOT))
    manager = ProviderManager(registry=registry)
    return manager.get_provider(ARIA2_PLUGIN_ID)


def _base_config(**overrides) -> dict:
    config = {
        "enabled": True,
        "rpc_url": "http://127.0.0.1:6800/jsonrpc",
        "secret": "s3cret",
        "dir": "",
        "timeout_seconds": 30,
    }
    config.update(overrides)
    return config


def test_aria2_plugin_discovered_and_loaded():
    registry = PluginRegistry(search_root=str(THIRD_PARTY_ROOT))
    manifest = registry.get_manifest(ARIA2_PLUGIN_ID)
    assert manifest is not None
    keys = set(manifest.capability_keys)
    assert {"download.magnet.add", "download.task.status", "download.task.list", "download.task.pause", "download.task.resume", "download.task.remove", "health.query.status"} <= keys

    provider = _make_provider()
    assert provider is not None


def test_normalize_config_defaults_and_secret_masking():
    provider = _make_provider()
    normalized = provider.normalize_config({})
    assert normalized["enabled"] is True
    assert normalized["rpc_url"] == "http://127.0.0.1:6800/jsonrpc"
    assert normalized["timeout_seconds"] == 30

    public = provider.serialize_public_config(_base_config())
    assert public["secret"] == ""
    assert public["secret_configured"] is True


def test_get_query_status():
    provider = _make_provider()
    assert provider.get_query_status(_base_config())["configured"] is True
    # rpc_url 留空时回退到默认本地端点（127.0.0.1:6800），仍视为已配置
    assert provider.get_query_status(_base_config(rpc_url=""))["configured"] is True
    # 未启用时视为未配置
    disabled = provider.get_query_status(_base_config(enabled=False))
    assert disabled["configured"] is False


def test_add_magnet_builds_rpc_payload(monkeypatch):
    rpc = FakeAria2Rpc()
    rpc.register("aria2.addUri", result="gid-001")
    monkeypatch.setattr(requests, "post", rpc)

    provider = _make_provider()
    config = _base_config(dir="D:\\downloads")
    result = provider.execute(
        "download.magnet.add",
        {"magnet": "magnet:?xt=urn:btih:abc123"},
        {},
        config,
    )
    assert result == {"gid": "gid-001", "added": True, "magnet": "magnet:?xt=urn:btih:abc123", "options": {"dir": "D:\\downloads"}}

    call = rpc.calls[0]
    assert call["method"] == "aria2.addUri"
    params = call["params"]
    # token 必须是第一个参数
    assert params[0] == "token:s3cret"
    assert params[1] == ["magnet:?xt=urn:btih:abc123"]
    assert params[2] == {"dir": "D:\\downloads"}


def test_add_magnet_without_secret_omits_token(monkeypatch):
    rpc = FakeAria2Rpc()
    rpc.register("aria2.addUri", result="gid-002")
    monkeypatch.setattr(requests, "post", rpc)

    provider = _make_provider()
    provider.execute(
        "download.magnet.add",
        {"uris": ["https://example.com/a.torrent", "magnet:?xt=urn:btih:xyz"]},
        {},
        _base_config(secret=""),
    )
    params = rpc.calls[0]["params"]
    assert params[0] == ["https://example.com/a.torrent", "magnet:?xt=urn:btih:xyz"]


def test_add_magnet_requires_magnet():
    provider = _make_provider()
    with pytest.raises(ValueError):
        provider.execute("download.magnet.add", {}, {}, _base_config())


def test_task_status_normalization(monkeypatch):
    raw = {
        "gid": "gid-001",
        "status": "active",
        "totalLength": "1000",
        "completedLength": "250",
        "downloadSpeed": "1024",
        "uploadSpeed": "512",
        "errorCode": "0",
        "errorMessage": "",
        "dir": "/downloads",
        "bittorrent": {"info": {"name": "sample-video.mkv"}},
        "files": [{"path": "/downloads/sample-video.mkv", "length": "1000", "completedLength": "250"}],
    }
    rpc = FakeAria2Rpc()
    rpc.register("aria2.tellStatus", result=raw)
    monkeypatch.setattr(requests, "post", rpc)

    provider = _make_provider()
    task = provider.execute("download.task.status", {"gid": "gid-001"}, {}, _base_config())
    assert task["gid"] == "gid-001"
    assert task["status"] == "active"
    assert task["name"] == "sample-video.mkv"
    assert task["progress"] == pytest.approx(0.25)
    assert task["download_speed"] == 1024


def test_task_status_falls_back_to_file_name(monkeypatch):
    raw = {
        "gid": "gid-003",
        "status": "waiting",
        "totalLength": "0",
        "completedLength": "0",
        "files": [{"path": "/downloads/foo/bar.mp4", "length": "0", "completedLength": "0"}],
    }
    rpc = FakeAria2Rpc()
    rpc.register("aria2.tellStatus", result=raw)
    monkeypatch.setattr(requests, "post", rpc)

    provider = _make_provider()
    task = provider.execute("download.task.status", {"gid": "gid-003"}, {}, _base_config())
    assert task["name"] == "bar.mp4"
    assert task["progress"] == 0.0


def test_task_list_merges_active_waiting_stopped(monkeypatch):
    rpc = FakeAria2Rpc()
    rpc.register("aria2.tellActive", result=[{"gid": "a1", "status": "active", "files": []}])
    rpc.register("aria2.tellWaiting", result=[{"gid": "w1", "status": "waiting", "files": []}])
    rpc.register("aria2.tellStopped", result=[{"gid": "s1", "status": "complete", "files": []}])
    monkeypatch.setattr(requests, "post", rpc)

    provider = _make_provider()
    result = provider.execute("download.task.list", {}, {}, _base_config())
    assert result["count"] == 3
    assert {task["gid"] for task in result["tasks"]} == {"a1", "w1", "s1"}
    methods = {call["method"] for call in rpc.calls}
    assert methods == {"aria2.tellActive", "aria2.tellWaiting", "aria2.tellStopped"}


def test_task_remove_uses_force_remove_for_active_task(monkeypatch):
    rpc = FakeAria2Rpc()
    rpc.register("aria2.tellStatus", result={"gid": "gid-001", "status": "active"})
    rpc.register("aria2.forceRemove", result="OK")
    rpc.register("aria2.remove", result="OK")
    monkeypatch.setattr(requests, "post", rpc)

    provider = _make_provider()
    result = provider.execute("download.task.remove", {"gid": "gid-001"}, {}, _base_config())
    assert result["removed"] is True
    assert rpc.calls[-1]["method"] == "aria2.forceRemove"

    rpc.calls.clear()
    provider.execute("download.task.remove", {"gid": "gid-001", "force": False}, {}, _base_config())
    assert rpc.calls[-1]["method"] == "aria2.remove"


def test_task_remove_uses_remove_download_result_for_stopped_task(monkeypatch):
    rpc = FakeAria2Rpc()
    rpc.register("aria2.tellStatus", result={"gid": "gid-001", "status": "complete"})
    rpc.register("aria2.removeDownloadResult", result="OK")
    monkeypatch.setattr(requests, "post", rpc)

    provider = _make_provider()
    result = provider.execute("download.task.remove", {"gid": "gid-001"}, {}, _base_config())
    assert result["removed"] is True
    assert rpc.calls[-1]["method"] == "aria2.removeDownloadResult"


def test_task_remove_falls_back_to_force_remove_when_status_unknown(monkeypatch):
    rpc = FakeAria2Rpc()
    rpc.register("aria2.tellStatus", error={"code": 1, "message": "not found"})
    rpc.register("aria2.forceRemove", result="OK")
    monkeypatch.setattr(requests, "post", rpc)

    provider = _make_provider()
    result = provider.execute("download.task.remove", {"gid": "gid-001"}, {}, _base_config())
    assert result["removed"] is True
    assert rpc.calls[-1]["method"] == "aria2.forceRemove"


def test_task_pause_active_task(monkeypatch):
    rpc = FakeAria2Rpc()
    rpc.register("aria2.tellStatus", result={"gid": "gid-001", "status": "active"})
    rpc.register("aria2.pause", result="OK")
    monkeypatch.setattr(requests, "post", rpc)

    provider = _make_provider()
    result = provider.execute("download.task.pause", {"gid": "gid-001"}, {}, _base_config())
    assert result["paused"] is True
    assert result["already"] is False
    assert rpc.calls[-1]["method"] == "aria2.pause"


def test_task_pause_already_paused_is_idempotent(monkeypatch):
    rpc = FakeAria2Rpc()
    rpc.register("aria2.tellStatus", result={"gid": "gid-001", "status": "paused"})
    monkeypatch.setattr(requests, "post", rpc)

    provider = _make_provider()
    result = provider.execute("download.task.pause", {"gid": "gid-001"}, {}, _base_config())
    assert result["paused"] is True
    assert result["already"] is True
    assert all(call["method"] != "aria2.pause" for call in rpc.calls)


def test_task_resume_paused_task(monkeypatch):
    rpc = FakeAria2Rpc()
    rpc.register("aria2.tellStatus", result={"gid": "gid-001", "status": "paused"})
    rpc.register("aria2.unpause", result="OK")
    monkeypatch.setattr(requests, "post", rpc)

    provider = _make_provider()
    result = provider.execute("download.task.resume", {"gid": "gid-001"}, {}, _base_config())
    assert result["resumed"] is True
    assert result["already"] is False
    assert rpc.calls[-1]["method"] == "aria2.unpause"


def test_task_resume_already_active_is_idempotent(monkeypatch):
    rpc = FakeAria2Rpc()
    rpc.register("aria2.tellStatus", result={"gid": "gid-001", "status": "active"})
    monkeypatch.setattr(requests, "post", rpc)

    provider = _make_provider()
    result = provider.execute("download.task.resume", {"gid": "gid-001"}, {}, _base_config())
    assert result["resumed"] is True
    assert result["already"] is True


def test_rpc_error_raises_runtime_error(monkeypatch):
    rpc = FakeAria2Rpc()
    rpc.register("aria2.tellStatus", error={"code": 1, "message": "No such download"})
    monkeypatch.setattr(requests, "post", rpc)

    provider = _make_provider()
    with pytest.raises(RuntimeError, match="No such download"):
        provider.execute("download.task.status", {"gid": "missing"}, {}, _base_config())


def test_disabled_plugin_raises():
    provider = _make_provider()
    with pytest.raises(RuntimeError, match="未启用"):
        provider.execute("download.magnet.add", {"magnet": "magnet:?xt=urn:btih:abc"}, {}, _base_config(enabled=False))


def test_unsupported_capability_raises():
    provider = _make_provider()
    with pytest.raises(ValueError, match="不支持的能力"):
        provider.execute("catalog.search", {}, {}, _base_config())
