import sys
from pathlib import Path

import pytest


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from protocol.base import PluginManifest
from protocol.provider_manager import ProviderManager


class _FakeRegistry:
    def __init__(self, manifests=None):
        default_manifest = PluginManifest(
            raw={
                "plugin": {
                    "id": "comic.demo",
                    "name": "Demo",
                    "config_key": "demo",
                    "entrypoint": "unused:Demo",
                },
                "capabilities": [{"key": "catalog.search"}, {"key": "health.query.status"}],
            },
            path=str(BACKEND_ROOT / "third_party" / "demo" / "ultimate-plugin.json"),
        )
        manifest_list = list(manifests or [default_manifest])
        self.manifests = {manifest.plugin_id: manifest for manifest in manifest_list}
        self.manifest = manifest_list[0]

    def get_manifest(self, plugin_id):
        return self.manifests[plugin_id]


class _FakeProvider:
    def execute(self, capability, params, context, config):
        return {"capability": capability, "enabled": config.get("enabled")}

    def get_query_status(self, config):
        return {"configured": True, "message": "", "missing_fields": []}

    def build_client(self, config, *args, **kwargs):
        return {"enabled": config.get("enabled")}


class _FakeConfigStore:
    def __init__(self, config):
        self.config = dict(config)
        self.requests = []

    def get_plugin_config(self, config_key, reload=False):
        self.requests.append(str(config_key or "").strip())
        if any(isinstance(value, dict) for value in self.config.values()):
            return dict(self.config.get(config_key, {}) or {})
        return dict(self.config)


def _make_manager(config):
    manager = ProviderManager(registry=_FakeRegistry())
    manager._providers["comic.demo"] = _FakeProvider()
    manager._config_store = _FakeConfigStore(config)
    return manager


def _make_child_manager(config):
    parent_manifest = PluginManifest(
        raw={
            "plugin": {
                "id": "video.parent",
                "name": "Parent",
                "config_key": "parent",
                "entrypoint": "unused:Parent",
            },
            "capabilities": [{"key": "catalog.search"}],
            "configuration": {
                "credential": {
                    "enabled_field": "enabled",
                    "required_fields": ["cookies.session"],
                },
                "sections": [
                    {
                        "id": "basic",
                        "fields": [{"key": "enabled", "type": "boolean"}],
                    }
                ],
            },
        },
        path=str(BACKEND_ROOT / "third_party" / "parent" / "ultimate-plugin.json"),
    )
    child_manifest = PluginManifest(
        raw={
            "plugin": {
                "id": "video.child",
                "name": "Child",
                "config_parent_key": "parent",
                "entrypoint": "unused:Child",
            },
            "capabilities": [{"key": "catalog.search"}, {"key": "health.query.status"}],
            "configuration": {
                "credential": {
                    "enabled_field": "enabled",
                    "required_fields": [],
                    "disabled_message": "Parent 未启用，不能使用 Child 子能力。",
                },
                "sections": [],
            },
        },
        path=str(BACKEND_ROOT / "third_party" / "parent" / "child" / "ultimate-plugin.json"),
    )
    manager = ProviderManager(registry=_FakeRegistry([parent_manifest, child_manifest]))
    manager._providers["video.child"] = _FakeProvider()
    manager._config_store = _FakeConfigStore({"parent": dict(config)})
    return manager


def test_provider_manager_blocks_query_capabilities_when_plugin_disabled():
    manager = _make_manager({"enabled": False})

    with pytest.raises(RuntimeError, match="未启用"):
        manager.execute("comic.demo", "catalog.search", {"keyword": "x"})


def test_provider_manager_allows_health_status_even_when_plugin_disabled():
    manager = _make_manager({"enabled": False})

    result = manager.execute("comic.demo", "health.query.status", {})

    assert result == {"capability": "health.query.status", "enabled": False}


def test_provider_manager_query_status_reports_disabled_plugin_not_configured():
    manager = _make_manager({"enabled": False})

    result = manager.get_query_status("comic.demo")

    assert result["configured"] is False
    assert "未启用" in result["message"]


def test_provider_manager_allows_query_capabilities_when_plugin_enabled():
    manager = _make_manager({"enabled": True})

    result = manager.execute("comic.demo", "catalog.search", {"keyword": "x"})

    assert result == {"capability": "catalog.search", "enabled": True}


def test_provider_manager_blocks_client_creation_when_plugin_disabled():
    manager = _make_manager({"enabled": False})

    with pytest.raises(RuntimeError, match="未启用"):
        manager.get_client("comic.demo")


def test_provider_manager_allows_client_creation_when_plugin_enabled():
    manager = _make_manager({"enabled": True})

    assert manager.get_client("comic.demo") == {"enabled": True}


def test_provider_manager_child_capability_follows_parent_config_enabled_only():
    manager = _make_child_manager({"enabled": True})

    result = manager.execute("video.child", "catalog.search", {"keyword": "x"})

    assert result == {"capability": "catalog.search", "enabled": True}
    assert manager._config_store.requests == ["parent"]


def test_provider_manager_child_capability_blocks_when_parent_switch_disabled():
    manager = _make_child_manager({"enabled": False})

    with pytest.raises(RuntimeError, match="Child 子能力"):
        manager.execute("video.child", "catalog.search", {"keyword": "x"})

    assert manager._config_store.requests == ["parent"]
