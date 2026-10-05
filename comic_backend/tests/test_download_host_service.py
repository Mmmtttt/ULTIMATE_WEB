"""下载能力宿主服务测试。

覆盖：
- list_download_engines 能发现声明 download.magnet.add 的插件
- get_download_client 按引擎名 / 默认引擎解析
- execute_download_capability 完整链路（host -> gateway -> provider -> Aria2 RPC）

方案 A 契约（对齐 main 的「未启用」策略）：
main 的 protocol/runtime_config.py 规定「非 storage.* 插件默认 enabled=False」，
下载引擎同属该范围——默认停用，需用户在配置页显式开启。
因此本文件所有用例都把插件配置指向临时文件并显式开启引擎，不再依赖本机
third_party_config.json 的残留状态；另有独立用例锁定「默认停用」这一契约本身。
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
from protocol.provider_manager import ProviderManager
from protocol.registry import PluginRegistry
from protocol.runtime_config import ProtocolConfigStore

ARIA2_PLUGIN_ID = "download.aria2"
THIRD_PARTY_ROOT = BACKEND_ROOT / "third_party"

# 方案 A：引擎默认停用，用例必须显式开启后才能执行下载能力。
ARIA2_ENABLED_CONFIG = {
    "enabled": True,
    "rpc_url": "http://127.0.0.1:6800/jsonrpc",
    "secret": "",
    "dir": "/tmp/downloads",
}


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


def _make_host_service(tmp_path, adapters=None) -> ProtocolHostService:
    """构造 host service，插件配置落在临时文件。

    adapters 为空 = 不预设任何配置，交由协议层套用默认策略（非 storage.* 默认停用）。
    执行链路（gateway -> provider_manager）与展示链路共用同一份临时配置。
    """
    config_path = tmp_path / "third_party_config.json"
    config_path.write_text(
        json.dumps(
            {"default_adapter": "", "adapters": dict(adapters or {})},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    store = ProtocolConfigStore(str(config_path))
    registry = PluginRegistry(search_root=str(THIRD_PARTY_ROOT))
    manager = ProviderManager(registry=registry)
    manager._config_store = store
    gateway = ProtocolGateway(registry=registry, provider_manager=manager)
    return ProtocolHostService(gateway=gateway, config_store=store)


def _host_service_with_aria2_enabled(tmp_path) -> ProtocolHostService:
    """显式开启 Aria2（方案 A 下这是使用下载能力的必要前提）。"""
    return _make_host_service(tmp_path, adapters={"aria2": dict(ARIA2_ENABLED_CONFIG)})


def test_list_download_engines_discovers_aria2(tmp_path):
    host = _host_service_with_aria2_enabled(tmp_path)
    engines = host.list_download_engines()
    aria2 = next((item for item in engines if item["plugin_id"] == ARIA2_PLUGIN_ID), None)
    assert aria2 is not None
    assert aria2["name"] == "Aria2"
    assert "download.magnet.add" in aria2["capabilities"]
    assert "download.task.list" in aria2["capabilities"]
    assert aria2["status"].get("configured") is True
    # 引擎根目录字段存在（从插件配置 dir 读取）
    assert "base_dir" in aria2
    assert isinstance(aria2["base_dir"], str)


def test_download_engine_disabled_by_default_until_user_enables_it(tmp_path):
    """锁定 main 的默认策略：下载引擎未显式开启时处于停用状态。

    这是方案 A 的核心契约——引擎默认停用是预期行为，不是缺陷；
    用户需要在第三方平台配置页显式开启后才能执行下载能力。
    """
    host = _make_host_service(tmp_path)
    engines = host.list_download_engines()
    aria2 = next((item for item in engines if item["plugin_id"] == ARIA2_PLUGIN_ID), None)
    assert aria2 is not None
    assert aria2["status"].get("configured") is False

    with pytest.raises(RuntimeError):
        host.execute_download_capability(
            "aria2",
            "download.magnet.add",
            {"magnet": "magnet:?xt=urn:btih:abc"},
        )


def test_get_download_client_by_name_and_default(tmp_path):
    host = _host_service_with_aria2_enabled(tmp_path)
    by_name = host.get_download_client("aria2")
    assert by_name.plugin_id == ARIA2_PLUGIN_ID

    by_alias = host.get_download_client("Aria2")
    assert by_alias.plugin_id == ARIA2_PLUGIN_ID

    default_client = host.get_download_client("")
    assert default_client.plugin_id == ARIA2_PLUGIN_ID

    # 未知引擎名回退到默认引擎
    fallback = host.get_download_client("no-such-engine")
    assert fallback.plugin_id == ARIA2_PLUGIN_ID


def test_execute_download_capability_full_chain(monkeypatch, tmp_path):
    rpc = FakeAria2Rpc()
    rpc.register("aria2.addUri", result="gid-101")
    monkeypatch.setattr(requests, "post", rpc)

    host = _host_service_with_aria2_enabled(tmp_path)
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


def test_execute_download_task_remove(monkeypatch, tmp_path):
    rpc = FakeAria2Rpc()
    rpc.register("aria2.tellStatus", result={"gid": "gid-101", "status": "active"})
    rpc.register("aria2.forceRemove", result="OK")
    monkeypatch.setattr(requests, "post", rpc)

    host = _host_service_with_aria2_enabled(tmp_path)
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
