from __future__ import annotations

import json
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from core.storage_layout import SPACE_MODE_NORMAL, SPACE_MODE_PRIVATE, set_current_space_mode
from protocol.base import PluginManifest
from protocol.registry import PluginRegistry
from protocol.runtime_config import ProtocolConfigStore
import protocol.space_access as space_access


def _manifest(plugin_id: str) -> PluginManifest:
    return PluginManifest(
        raw={
            "protocol_version": "2.0",
            "plugin": {"id": plugin_id, "name": plugin_id},
            "media_types": ["video"],
        },
        path=f"/tmp/{plugin_id}/ultimate-plugin.json",
    )


def test_registry_filters_plugins_in_private_space(monkeypatch, tmp_path):
    config_path = tmp_path / "third_party_config.json"
    config_path.write_text(
        json.dumps(
            {
                "space_access": {
                    "private_enabled_plugin_ids": [
                        "video.demo.allowed",
                        "video.demo.allowed",
                        "",
                    ]
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(space_access, "THIRD_PARTY_CONFIG_PATH", str(config_path))

    registry = PluginRegistry(search_root=str(tmp_path / "missing"))
    registry._manifests = {
        "video.demo.allowed": _manifest("video.demo.allowed"),
        "video.demo.blocked": _manifest("video.demo.blocked"),
    }
    registry._loaded = True

    set_current_space_mode(SPACE_MODE_NORMAL)
    assert [item.plugin_id for item in registry.list_manifests()] == [
        "video.demo.allowed",
        "video.demo.blocked",
    ]

    set_current_space_mode(SPACE_MODE_PRIVATE)
    try:
        assert [item.plugin_id for item in registry.list_manifests()] == ["video.demo.allowed"]
        assert registry.get_manifest("video.demo.allowed").plugin_id == "video.demo.allowed"
        try:
            registry.get_manifest("video.demo.blocked")
        except KeyError as error:
            assert "unavailable in current space" in str(error)
        else:
            raise AssertionError("blocked plugin was returned in private space")
    finally:
        set_current_space_mode(SPACE_MODE_NORMAL)


def test_space_access_config_is_normalized_and_persisted(tmp_path):
    config_path = tmp_path / "third_party_config.json"
    store = ProtocolConfigStore(str(config_path))

    store.set_space_access(
        {"private_enabled_plugin_ids": ["video.demo.one", "", "video.demo.one", 42]}
    )

    payload = json.loads(config_path.read_text(encoding="utf-8"))
    assert payload["space_access"]["private_enabled_plugin_ids"] == [
        "video.demo.one",
        "42",
    ]
    assert store.get_space_access() == {
        "private_enabled_plugin_ids": ["video.demo.one", "42"]
    }


def test_private_space_without_allowlist_can_still_list_authorizable_plugins(monkeypatch, tmp_path):
    """白名单为空时，隐私空间里的授权界面仍必须能看到插件。

    授权列表若取自被空间门禁过滤的结果，在隐私空间里恒为空——用户必须先授权
    才能看到条目、又必须看到条目才能授权，形成死锁。因此授权列表要改用
    list_all_manifests()。
    """
    config_path = tmp_path / "third_party_config.json"
    config_path.write_text(
        json.dumps({"space_access": {"private_enabled_plugin_ids": []}}),
        encoding="utf-8",
    )
    monkeypatch.setattr(space_access, "THIRD_PARTY_CONFIG_PATH", str(config_path))

    registry = PluginRegistry(search_root=str(tmp_path / "missing"))
    registry._manifests = {
        "download.libretorrent": _manifest("download.libretorrent"),
        "video.demo.other": _manifest("video.demo.other"),
    }
    registry._loaded = True

    set_current_space_mode(SPACE_MODE_PRIVATE)
    try:
        # 受门禁的业务查询：隐私空间下确实什么都不可用
        assert registry.list_manifests() == []
        # 授权界面专用清单：不受门禁影响，否则无法完成授权
        assert [item.plugin_id for item in registry.list_all_manifests()] == [
            "download.libretorrent",
            "video.demo.other",
        ]
    finally:
        set_current_space_mode(SPACE_MODE_NORMAL)
