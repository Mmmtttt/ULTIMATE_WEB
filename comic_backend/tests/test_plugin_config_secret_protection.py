"""插件配置保存时 secret 字段（密码/密钥）空值保护测试。

场景：前端回显时 secret 字段被清空（serialize_public_config 置空），
用户打开/关闭任意开关保存配置时若不做保护，会把已配置的密码覆盖为空，
导致下载引擎（qBittorrent/Aria2）连接失败。本测试验证 save_updates
对空 secret 提交保留旧值。
"""
import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from protocol.config_service import PluginConfigService


class FakeConfigStore:
    def __init__(self, initial: dict = None):
        self.data = dict(initial or {})
        self.saved_keys = []

    def get_plugin_config(self, config_key, reload: bool = False) -> dict:
        return dict(self.data.get(str(config_key or "").strip(), {}) or {})

    def set_plugin_config(self, config_key: str, payload: dict):
        self.data[str(config_key or "").strip()] = dict(payload or {})
        self.saved_keys.append(str(config_key or "").strip())

    def reset_runtime_caches(self, keys):
        pass


def _make_service(initial: dict):
    service = PluginConfigService()
    service._config_store = FakeConfigStore(initial)
    return service


QB_OLD = {
    "enabled": True,
    "webui_url": "http://127.0.0.1:8087",
    "username": "niaoshu",
    "password": "123456",
    "dir": "",
    "timeout_seconds": 30,
}


def test_empty_password_preserves_old_value():
    """提交空密码（前端回显）时保留已配置的密码"""
    service = _make_service({"qbittorrent": dict(QB_OLD)})
    service.save_updates({
        "adapter": "qbittorrent",
        "config": {
            "enabled": True,
            "webui_url": "http://127.0.0.1:8087",
            "username": "niaoshu",
            "password": "",
            "auto_organize_enabled": True,
            "auto_import_enabled": True,
        },
    })
    saved = service._config_store.data["qbittorrent"]
    assert saved["password"] == "123456"
    assert saved["auto_organize_enabled"] is True
    assert saved["auto_import_enabled"] is True


def test_new_password_overwrites_old_value():
    """用户主动填写新密码时正常更新"""
    service = _make_service({"qbittorrent": dict(QB_OLD)})
    service.save_updates({
        "adapter": "qbittorrent",
        "config": {"password": "new-pass-888"},
    })
    saved = service._config_store.data["qbittorrent"]
    assert saved["password"] == "new-pass-888"


def test_aria2_secret_preserved_when_empty():
    """Aria2 的 secret 同样受保护"""
    aria_old = {"enabled": True, "rpc_url": "http://127.0.0.1:6800/jsonrpc", "secret": "rpc-secret"}
    service = _make_service({"aria2": aria_old})
    service.save_updates({
        "adapter": "aria2",
        "config": {"enabled": True, "rpc_url": "http://127.0.0.1:6800/jsonrpc", "secret": ""},
    })
    saved = service._config_store.data["aria2"]
    assert saved["secret"] == "rpc-secret"


def test_empty_secret_with_no_old_value_stays_empty():
    """首次配置时无旧值，空 secret 不填默认"""
    service = _make_service({})
    service.save_updates({
        "adapter": "qbittorrent",
        "config": {"webui_url": "http://127.0.0.1:8080", "username": "u", "password": ""},
    })
    saved = service._config_store.data["qbittorrent"]
    assert saved["password"] == ""
