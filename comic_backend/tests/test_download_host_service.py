"""下载能力宿主服务测试。

覆盖：
- list_download_engines 能发现声明 download.magnet.add 的插件
- get_download_client 按引擎名 / 默认引擎解析
- execute_download_capability 完整链路（host -> gateway -> provider -> Aria2 RPC）
"""
import json
import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import requests

from protocol.gateway import ProtocolGateway
from protocol.host_service import ProtocolHostService
from protocol.registry import PluginRegistry

ARIA2_PLUGIN_ID = "download.aria2"
THIRD_PARTY_ROOT = BACKEND_ROOT / "third_party"


class FakeResponse:
    def __init__(self, result=None, error=None, status_code=200):
        self.status_code = status_code
        self._result = result
        self._error = error

    def json(self):
        body = {"jsonrpc": "2.0", "id": "x"}
        if self._error is not None:
            body["error"] = self._error
        else:
            body["result"] = self._result
        return body


class FakeAria2Rpc:
    def __init__(self):
        self.calls: list[dict] = []
        self.results: dict = {}

    def register(self, method, result=None, error=None):
        self.results[method] = {"result": result, "error": error}

    def __call__(self, url, json=None, timeout=None):
        body = dict(json or {})
        self.calls.append(body)
        spec = self.results.get(body.get("method", ""), {})
        if spec.get("error") is not None:
            return FakeResponse(error=spec["error"])
        return FakeResponse(result=spec.get("result"))


def _make_host_service() -> ProtocolHostService:
    registry = PluginRegistry(search_root=str(THIRD_PARTY_ROOT))
    gateway = ProtocolGateway(registry=registry)
    return ProtocolHostService(gateway=gateway)


def test_list_download_engines_discovers_aria2():
    host = _make_host_service()
    engines = host.list_download_engines()
    aria2 = next((item for item in engines if item["plugin_id"] == ARIA2_PLUGIN_ID), None)
    assert aria2 is not None
    assert aria2["name"] == "Aria2"
    assert "download.magnet.add" in aria2["capabilities"]
    assert "download.task.list" in aria2["capabilities"]
    assert aria2["status"].get("configured") is True


def test_get_download_client_by_name_and_default():
    host = _make_host_service()
    by_name = host.get_download_client("aria2")
    assert by_name.plugin_id == ARIA2_PLUGIN_ID

    by_alias = host.get_download_client("Aria2")
    assert by_alias.plugin_id == ARIA2_PLUGIN_ID

    default_client = host.get_download_client("")
    assert default_client.plugin_id == ARIA2_PLUGIN_ID

    # 未知引擎名回退到默认引擎
    fallback = host.get_download_client("no-such-engine")
    assert fallback.plugin_id == ARIA2_PLUGIN_ID


def test_execute_download_capability_full_chain(monkeypatch):
    rpc = FakeAria2Rpc()
    rpc.register("aria2.addUri", result="gid-101")
    monkeypatch.setattr(requests, "post", rpc)

    host = _make_host_service()
    plugin_id, platform, payload = host.execute_download_capability(
        "aria2",
        "download.magnet.add",
        {"magnet": "magnet:?xt=urn:btih:abc"},
    )
    assert plugin_id == ARIA2_PLUGIN_ID
    assert platform == "aria2"
    assert payload["gid"] == "gid-101"
    assert payload["added"] is True
    # 未配置 secret 时，uris 直接作为第一个参数（token 插入逻辑由插件测试覆盖）
    assert rpc.calls[0]["method"] == "aria2.addUri"
    assert rpc.calls[0]["params"][0] == ["magnet:?xt=urn:btih:abc"]


def test_execute_download_task_remove(monkeypatch):
    rpc = FakeAria2Rpc()
    rpc.register("aria2.tellStatus", result={"gid": "gid-101", "status": "active"})
    rpc.register("aria2.forceRemove", result="OK")
    monkeypatch.setattr(requests, "post", rpc)

    host = _make_host_service()
    _plugin_id, _platform, payload = host.execute_download_capability(
        "aria2",
        "download.task.remove",
        {"gid": "gid-101", "force": True},
    )
    assert payload["removed"] is True


def test_no_download_plugin_raises(tmp_path):
    registry = PluginRegistry(search_root=str(tmp_path))
    gateway = ProtocolGateway(registry=registry)
    host = ProtocolHostService(gateway=gateway)
    with pytest.raises(ValueError, match="下载插件"):
        host.get_download_client("")
