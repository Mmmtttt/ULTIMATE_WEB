"""qBittorrent 插件协议测试。

覆盖：
- manifest 能被真实 third_party 目录扫描发现，且声明了下载能力
- provider 能被 ProviderManager 动态加载
- normalize_config / serialize_public_config（密码脱敏）
- get_query_status 配置就绪判断
- download.magnet.add 构造正确的 /torrents/add 表单载荷
- download.task.status / list / pause / resume / remove 的调用与状态映射
- 登录失败、未启用插件的行为
"""
import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import requests

from protocol.provider_manager import ProviderManager
from protocol.registry import PluginRegistry

QBITTORRENT_PLUGIN_ID = "download.qbittorrent"
THIRD_PARTY_ROOT = BACKEND_ROOT / "third_party"


class FakeResponse:
    def __init__(self, status_code=200, text="", json_body=None):
        self.status_code = status_code
        self.text = text
        self._json_body = json_body

    def json(self):
        return self._json_body


class FakeQbtApi:
    """按 endpoint 分发响应的 qBittorrent WebUI API 桩。"""

    def __init__(self):
        self.calls: list[dict] = []
        self.routes: dict = {}

    def register(self, endpoint, status_code=200, text="", json_body=None):
        self.routes[endpoint] = FakeResponse(status_code, text, json_body)

    def handle(self, method, url, params=None, data=None):
        endpoint = url.split("/api/v2/", 1)[-1].split("?", 1)[0]
        self.calls.append({
            "method": method,
            "endpoint": endpoint,
            "params": params,
            "data": data,
        })
        response = self.routes.get(endpoint)
        if response is None:
            return FakeResponse(200, "{}", {})
        return response


class FakeSession:
    def __init__(self, api: FakeQbtApi):
        self.api = api
        self.headers = {}

    def post(self, url, data=None, params=None, timeout=None):
        return self.api.handle("POST", url, params=params, data=data)

    def get(self, url, params=None, timeout=None):
        return self.api.handle("GET", url, params=params)


def _make_provider():
    registry = PluginRegistry(search_root=str(THIRD_PARTY_ROOT))
    manager = ProviderManager(registry=registry)
    return manager.get_provider(QBITTORRENT_PLUGIN_ID)


def _base_config(**overrides) -> dict:
    config = {
        "enabled": True,
        "webui_url": "http://127.0.0.1:8080",
        "username": "admin",
        "password": "adminadmin",
        "dir": "",
        "timeout_seconds": 30,
    }
    config.update(overrides)
    return config


def _install_fake(monkeypatch, api: FakeQbtApi):
    api.register("auth/login", text="Ok.")
    monkeypatch.setattr(requests, "Session", lambda: FakeSession(api))


def _sample_item(**overrides) -> dict:
    item = {
        "hash": "abc123",
        "name": "Sample Torrent",
        "state": "downloading",
        "progress": 0.42,
        "size": 1000,
        "dlspeed": 512000,
        "upspeed": 1024,
        "save_path": "/downloads",
    }
    item.update(overrides)
    return item


# ---------- 发现与加载 ----------


def test_qbittorrent_plugin_discovered_and_loaded():
    registry = PluginRegistry(search_root=str(THIRD_PARTY_ROOT))
    manifest = registry.get_manifest(QBITTORRENT_PLUGIN_ID)
    assert manifest is not None
    keys = set(manifest.capability_keys)
    assert {"download.magnet.add", "download.task.status", "download.task.list", "download.task.pause", "download.task.resume", "download.task.remove", "download.task.migrate", "health.query.status"} <= keys

    provider = _make_provider()
    assert provider is not None


# ---------- 配置 ----------


def test_normalize_config_and_password_serialization():
    provider = _make_provider()
    normalized = provider.normalize_config(_base_config())
    assert normalized["webui_url"] == "http://127.0.0.1:8080"
    assert normalized["username"] == "admin"
    assert normalized["password"] == "adminadmin"

    public = provider.serialize_public_config(_base_config())
    assert public["password"] == ""
    assert public["password_configured"] is True


def test_query_status_configuration():
    provider = _make_provider()
    status = provider.get_query_status(_base_config())
    assert status["configured"] is True

    status = provider.get_query_status(_base_config(enabled=False))
    assert status["configured"] is False


# ---------- download.magnet.add ----------


def test_add_magnet_posts_torrents_add(monkeypatch):
    api = FakeQbtApi()
    _install_fake(monkeypatch, api)

    provider = _make_provider()
    result = provider.execute(
        "download.magnet.add",
        {"magnet": "magnet:?xt=urn:btih:abc"},
        {},
        _base_config(dir="/downloads"),
    )
    assert result["added"] is True

    add_calls = [c for c in api.calls if c["endpoint"] == "torrents/add"]
    assert len(add_calls) == 1
    assert add_calls[0]["method"] == "POST"
    assert "magnet:?xt=urn:btih:abc" in add_calls[0]["data"]["urls"]
    assert add_calls[0]["data"]["savepath"] == "/downloads"


def test_add_magnet_joins_multiple_uris(monkeypatch):
    api = FakeQbtApi()
    _install_fake(monkeypatch, api)

    provider = _make_provider()
    provider.execute(
        "download.magnet.add",
        {"uris": ["magnet:a", "https://example.com/x.torrent"]},
        {},
        _base_config(),
    )
    add_calls = [c for c in api.calls if c["endpoint"] == "torrents/add"]
    assert add_calls[0]["data"]["urls"] == "magnet:a\nhttps://example.com/x.torrent"


def test_add_magnet_without_uris_raises(monkeypatch):
    api = FakeQbtApi()
    _install_fake(monkeypatch, api)

    provider = _make_provider()
    with pytest.raises(ValueError):
        provider.execute("download.magnet.add", {}, {}, _base_config())


# ---------- download.task.status / list ----------


def test_task_list_normalizes_states(monkeypatch):
    api = FakeQbtApi()
    _install_fake(monkeypatch, api)
    api.register(
        "torrents/info",
        json_body=[
            _sample_item(state="downloading"),
            _sample_item(hash="b", state="queuedDL", size=200, progress=0.0),
            _sample_item(hash="c", state="pausedDL"),
            _sample_item(hash="d", state="uploading", progress=1.0),
            _sample_item(hash="e", state="error"),
        ],
    )

    provider = _make_provider()
    result = provider.execute("download.task.list", {}, {}, _base_config())
    by_gid = {task["gid"]: task for task in result["tasks"]}
    assert by_gid["abc123"]["status"] == "active"
    assert by_gid["abc123"]["progress"] == 0.42
    assert by_gid["abc123"]["completed_length"] == 420
    assert by_gid["abc123"]["download_speed"] == 512000
    assert by_gid["b"]["status"] == "waiting"
    assert by_gid["c"]["status"] == "paused"
    assert by_gid["d"]["status"] == "complete"
    assert by_gid["e"]["status"] == "error"

    filtered = provider.execute("download.task.list", {"status": "active"}, {}, _base_config())
    assert {task["gid"] for task in filtered["tasks"]} == {"abc123"}


def test_task_status_by_hash(monkeypatch):
    api = FakeQbtApi()
    _install_fake(monkeypatch, api)
    api.register("torrents/info", json_body=[_sample_item(hash="abc123", state="metaDL")])

    provider = _make_provider()
    result = provider.execute("download.task.status", {"gid": "abc123"}, {}, _base_config())
    assert result["gid"] == "abc123"
    assert result["status"] == "active"


def test_task_status_missing_gid_raises(monkeypatch):
    api = FakeQbtApi()
    _install_fake(monkeypatch, api)

    provider = _make_provider()
    with pytest.raises(ValueError):
        provider.execute("download.task.status", {}, {}, _base_config())


# ---------- download.task.pause / resume / remove ----------


def test_task_pause_posts_stop(monkeypatch):
    api = FakeQbtApi()
    _install_fake(monkeypatch, api)
    api.register("torrents/info", json_body=[_sample_item(state="downloading")])

    provider = _make_provider()
    result = provider.execute("download.task.pause", {"gid": "abc123"}, {}, _base_config())
    assert result["paused"] is True
    assert result["already"] is False

    stop_calls = [c for c in api.calls if c["endpoint"] == "torrents/stop"]
    assert len(stop_calls) == 1
    assert stop_calls[0]["data"]["hashes"] == "abc123"


def test_task_pause_already_paused_is_idempotent(monkeypatch):
    api = FakeQbtApi()
    _install_fake(monkeypatch, api)
    api.register("torrents/info", json_body=[_sample_item(state="pausedDL")])

    provider = _make_provider()
    result = provider.execute("download.task.pause", {"gid": "abc123"}, {}, _base_config())
    assert result["paused"] is True
    assert result["already"] is True
    assert all(c["endpoint"] != "torrents/stop" for c in api.calls)


def test_task_resume_posts_start(monkeypatch):
    api = FakeQbtApi()
    _install_fake(monkeypatch, api)
    api.register("torrents/info", json_body=[_sample_item(state="stoppedDL")])

    provider = _make_provider()
    result = provider.execute("download.task.resume", {"gid": "abc123"}, {}, _base_config())
    assert result["resumed"] is True
    assert result["already"] is False

    start_calls = [c for c in api.calls if c["endpoint"] == "torrents/start"]
    assert len(start_calls) == 1
    assert start_calls[0]["data"]["hashes"] == "abc123"


def test_task_remove_posts_delete(monkeypatch):
    api = FakeQbtApi()
    _install_fake(monkeypatch, api)

    provider = _make_provider()
    result = provider.execute("download.task.remove", {"gid": "abc123"}, {}, _base_config())
    assert result["removed"] is True

    delete_calls = [c for c in api.calls if c["endpoint"] == "torrents/delete"]
    assert len(delete_calls) == 1
    assert delete_calls[0]["data"]["hashes"] == "abc123"
    assert delete_calls[0]["data"]["deleteFiles"] == "false"


# ---------- 错误与边界 ----------


def test_login_failure_raises(monkeypatch):
    api = FakeQbtApi()
    api.register("auth/login", status_code=403, text="Fails.")
    monkeypatch.setattr(requests, "Session", lambda: FakeSession(api))

    provider = _make_provider()
    with pytest.raises(RuntimeError, match="登录失败"):
        provider.execute("download.magnet.add", {"magnet": "magnet:a"}, {}, _base_config())


def test_login_ok_legacy_4x_text_response(monkeypatch):
    """旧版 qBittorrent 4.x：登录返回 200 + 'Ok.'"""
    api = FakeQbtApi()
    _install_fake(monkeypatch, api)
    api.register("torrents/add")

    provider = _make_provider()
    result = provider.execute("download.magnet.add", {"magnet": "magnet:a"}, {}, _base_config())
    assert result["added"] is True


def test_login_ok_5x_empty_204_response(monkeypatch):
    """新版 qBittorrent 5.x：登录返回 204 空响应，应视为成功"""
    api = FakeQbtApi()
    api.register("auth/login", status_code=204, text="")
    monkeypatch.setattr(requests, "Session", lambda: FakeSession(api))

    provider = _make_provider()
    result = provider.execute("download.magnet.add", {"magnet": "magnet:a"}, {}, _base_config())
    assert result["added"] is True


def test_login_fails_text_raises(monkeypatch):
    """qBittorrent 4.x 登录失败：返回 200 + 'Fails.'"""
    api = FakeQbtApi()
    api.register("auth/login", text="Fails.")
    monkeypatch.setattr(requests, "Session", lambda: FakeSession(api))

    provider = _make_provider()
    with pytest.raises(RuntimeError, match="用户名或密码错误"):
        provider.execute("download.magnet.add", {"magnet": "magnet:a"}, {}, _base_config())


def test_http_error_raises(monkeypatch):
    api = FakeQbtApi()
    _install_fake(monkeypatch, api)
    api.register("torrents/info", status_code=500, text="boom")

    provider = _make_provider()
    with pytest.raises(RuntimeError, match="HTTP 500"):
        provider.execute("download.task.list", {}, {}, _base_config())


def test_disabled_plugin_raises(monkeypatch):
    api = FakeQbtApi()
    _install_fake(monkeypatch, api)

    provider = _make_provider()
    with pytest.raises(RuntimeError, match="未启用"):
        provider.execute("download.task.list", {}, {}, _base_config(enabled=False))


def test_unsupported_capability_raises(monkeypatch):
    api = FakeQbtApi()
    _install_fake(monkeypatch, api)

    provider = _make_provider()
    with pytest.raises(ValueError, match="不支持的能力"):
        provider.execute("catalog.search", {}, {}, _base_config())


# ---------- download.task.migrate ----------


def test_task_migrate_deletes_and_readds_in_new_dir(tmp_path, monkeypatch):
    api = FakeQbtApi()
    _install_fake(monkeypatch, api)
    api.register("torrents/info", json_body=[_sample_item(hash="ABC123")])

    target_dir = tmp_path / "movies" / "ABC-123"
    provider = _make_provider()
    result = provider.execute(
        "download.task.migrate",
        {"gid": "ABC123", "dir": str(target_dir)},
        {},
        _base_config(),
    )
    assert result["migrated"] is True
    assert target_dir.is_dir()

    by_endpoint = {}
    for call in api.calls:
        if call["endpoint"] != "auth/login":
            by_endpoint.setdefault(call["endpoint"], call)
    info_call = by_endpoint["torrents/info"]
    assert info_call["method"] == "GET"
    assert info_call["params"]["hashes"] == "ABC123"

    delete_call = by_endpoint["torrents/delete"]
    assert delete_call["data"]["hashes"] == "abc123"
    assert delete_call["data"]["deleteFiles"] == "false"

    add_call = by_endpoint["torrents/add"]
    assert add_call["data"]["urls"] == "magnet:?xt=urn:btih:abc123"
    assert add_call["data"]["savepath"] == str(target_dir)


def test_task_migrate_missing_task_raises(tmp_path, monkeypatch):
    api = FakeQbtApi()
    _install_fake(monkeypatch, api)
    api.register("torrents/info", json_body=[])

    provider = _make_provider()
    with pytest.raises(RuntimeError, match="任务不存在"):
        provider.execute(
            "download.task.migrate",
            {"gid": "ABC123", "dir": str(tmp_path / "new")},
            {},
            _base_config(),
        )


def test_task_migrate_requires_gid_and_dir():
    provider = _make_provider()
    with pytest.raises(ValueError, match="gid"):
        provider.execute("download.task.migrate", {"dir": "x"}, {}, _base_config())
    with pytest.raises(ValueError, match="dir"):
        provider.execute("download.task.migrate", {"gid": "ABC123"}, {}, _base_config())
