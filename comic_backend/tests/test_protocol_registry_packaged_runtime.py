import json
import shutil
import sys
from uuid import uuid4
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import protocol.registry as registry_module


def test_plugin_registry_scans_backend_root_third_party_in_packaged_layout(monkeypatch):
    workspace_tmp_root = Path.cwd() / ".codex_test_runtime"
    workspace_tmp_root.mkdir(parents=True, exist_ok=True)
    temp_dir = workspace_tmp_root / f"registry_packaged_{uuid4().hex[:8]}"
    temp_dir.mkdir(parents=True, exist_ok=True)

    try:
        bundle_root = temp_dir / "release_bundle"
        backend_source = bundle_root / "backend_source"
        plugin_dir = backend_source / "third_party" / "demo_plugin"
        plugin_dir.mkdir(parents=True, exist_ok=True)

        (plugin_dir / "ultimate-plugin.json").write_text(
            json.dumps(
                {
                    "protocol_version": "1.0",
                    "plugin": {
                        "id": "video.demo.packaged",
                        "name": "Demo Packaged",
                        "version": "1.0.0",
                        "entrypoint": "./ultimate_provider.py:DemoProvider",
                    },
                    "media_types": ["video"],
                    "capabilities": [{"key": "catalog.search"}],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        (plugin_dir / "ultimate_provider.py").write_text(
            "from protocol.base import ProtocolProvider\n"
            "class DemoProvider(ProtocolProvider):\n"
            "    def execute(self, capability, params, context, config):\n"
            "        return {}\n",
            encoding="utf-8",
        )

        monkeypatch.setattr(registry_module, "BACKEND_ROOT", str(backend_source))
        monkeypatch.setattr(registry_module, "PROJECT_ROOT", str(bundle_root))

        registry = registry_module.PluginRegistry()
        manifests = registry.list_manifests()

        assert any(manifest.plugin_id == "video.demo.packaged" for manifest in manifests)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_plugin_registry_merges_host_overlay_into_manifest(monkeypatch):
    workspace_tmp_root = Path.cwd() / ".codex_test_runtime"
    workspace_tmp_root.mkdir(parents=True, exist_ok=True)
    temp_dir = workspace_tmp_root / f"registry_overlay_{uuid4().hex[:8]}"
    temp_dir.mkdir(parents=True, exist_ok=True)

    try:
        plugin_dir = temp_dir / "third_party" / "demo_plugin"
        plugin_dir.mkdir(parents=True, exist_ok=True)
        (plugin_dir / "ultimate-plugin.json").write_text(
            json.dumps(
                {
                    "protocol_version": "2.0",
                    "plugin": {
                        "id": "video.demo.overlay",
                        "name": "Demo Overlay",
                        "version": "1.0.0",
                        "entrypoint": "protocol.snapshot_provider:MetadataOnlyProvider",
                        "config_key": "demo_overlay",
                    },
                    "media_types": ["video"],
                    "capabilities": [{"key": "catalog.search"}],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        (plugin_dir / "ultimate-host.json").write_text(
            json.dumps(
                {
                    "plugin": {"id": "video.demo.overlay"},
                    "identity": {
                        "platform_label": "DEMO",
                        "host_id_prefix": "DEMO",
                    },
                    "presentation": {
                        "media_card": {
                            "cover": {
                                "aspect_ratio": "16 / 9",
                                "mobile_aspect_ratio": "3 / 2",
                            }
                        }
                    },
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        registry = registry_module.PluginRegistry(search_root=str(plugin_dir.parent))
        manifests = registry.list_manifests()
        manifest = next(item for item in manifests if item.plugin_id == "video.demo.overlay")

        assert manifest.identity.get("host_id_prefix") == "DEMO"
        cover = (((manifest.presentation or {}).get("media_card") or {}).get("cover") or {})
        assert cover.get("aspect_ratio") == "16 / 9"
        assert cover.get("mobile_aspect_ratio") == "3 / 2"
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_plugin_registry_loads_mobile_protocol_snapshot_without_third_party_dirs(monkeypatch):
    workspace_tmp_root = Path.cwd() / ".codex_test_runtime"
    workspace_tmp_root.mkdir(parents=True, exist_ok=True)
    temp_dir = workspace_tmp_root / f"registry_snapshot_{uuid4().hex[:8]}"
    temp_dir.mkdir(parents=True, exist_ok=True)

    try:
        snapshot_path = temp_dir / "mobile_protocol_snapshot.json"
        snapshot_path.write_text(
            json.dumps(
                {
                    "version": 1,
                    "manifests": [
                        {
                            "protocol_version": "2.0",
                            "plugin": {
                                "id": "comic.snapshot.demo",
                                "name": "Snapshot Demo",
                                "version": "0.0.0-snapshot",
                                "config_key": "snapshot_demo",
                                "entrypoint": "protocol.snapshot_provider:MetadataOnlyProvider",
                            },
                            "media_types": ["comic"],
                            "identity": {
                                "platform_label": "SNAP",
                                "host_id_prefix": "SNAP",
                            },
                            "storage": {
                                "host_resolution": {
                                    "comic_local_dir": {
                                        "path_templates": ["{host_prefix}/{original_id}"]
                                    }
                                }
                            },
                        }
                    ],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        monkeypatch.setenv("BACKEND_PROTOCOL_SNAPSHOT_PATH", str(snapshot_path))
        registry = registry_module.PluginRegistry(search_root=str(temp_dir / "missing_third_party"))
        manifests = registry.list_manifests()
        manifest = next(item for item in manifests if item.plugin_id == "comic.snapshot.demo")

        assert manifest.entrypoint == "protocol.snapshot_provider:MetadataOnlyProvider"
        assert manifest.identity.get("host_id_prefix") == "SNAP"
        assert (
            (((manifest.storage or {}).get("host_resolution") or {}).get("comic_local_dir") or {}).get("path_templates")
            == ["{host_prefix}/{original_id}"]
        )
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_plugin_registry_scans_external_plugin_roots_from_env(monkeypatch):
    workspace_tmp_root = Path.cwd() / ".codex_test_runtime"
    workspace_tmp_root.mkdir(parents=True, exist_ok=True)
    temp_dir = workspace_tmp_root / f"registry_external_{uuid4().hex[:8]}"
    temp_dir.mkdir(parents=True, exist_ok=True)

    try:
        external_root = temp_dir / "plugins"
        plugin_dir = external_root / "demo_plugin"
        plugin_dir.mkdir(parents=True, exist_ok=True)
        (plugin_dir / "ultimate-plugin.json").write_text(
            json.dumps(
                {
                    "protocol_version": "2.0",
                    "plugin": {
                        "id": "comic.demo.external",
                        "name": "Demo External",
                        "version": "1.0.0",
                        "entrypoint": "./ultimate_provider.py:DemoProvider",
                    },
                    "media_types": ["comic"],
                    "capabilities": [{"key": "catalog.search"}],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        (plugin_dir / "ultimate_provider.py").write_text(
            "from protocol.base import ProtocolProvider\n"
            "class DemoProvider(ProtocolProvider):\n"
            "    def execute(self, capability, params, context, config):\n"
            "        return {'ok': True}\n",
            encoding="utf-8",
        )

        monkeypatch.setenv("ULTIMATE_PLUGIN_ROOTS", str(external_root))
        registry = registry_module.PluginRegistry()
        manifests = registry.list_manifests()

        assert any(manifest.plugin_id == "comic.demo.external" for manifest in manifests)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_plugin_registry_scans_release_bundle_plugins_root(monkeypatch):
    workspace_tmp_root = Path.cwd() / ".codex_test_runtime"
    workspace_tmp_root.mkdir(parents=True, exist_ok=True)
    temp_dir = workspace_tmp_root / f"registry_bundle_plugins_{uuid4().hex[:8]}"
    temp_dir.mkdir(parents=True, exist_ok=True)

    try:
        bundle_root = temp_dir / "release_bundle"
        backend_source = bundle_root / "backend_source"
        plugins_root = bundle_root / "plugins"
        backend_source.mkdir(parents=True, exist_ok=True)
        plugin_dir = plugins_root / "demo_plugin"
        plugin_dir.mkdir(parents=True, exist_ok=True)

        (plugin_dir / "ultimate-plugin.json").write_text(
            json.dumps(
                {
                    "protocol_version": "2.0",
                    "plugin": {
                        "id": "video.demo.bundle",
                        "name": "Demo Bundle Plugin",
                        "version": "1.0.0",
                        "entrypoint": "./ultimate_provider.py:DemoProvider",
                    },
                    "media_types": ["video"],
                    "capabilities": [{"key": "catalog.search"}],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        (plugin_dir / "ultimate_provider.py").write_text(
            "from protocol.base import ProtocolProvider\n"
            "class DemoProvider(ProtocolProvider):\n"
            "    def execute(self, capability, params, context, config):\n"
            "        return {'ok': True}\n",
            encoding="utf-8",
        )

        monkeypatch.setattr(registry_module, "BACKEND_ROOT", str(backend_source))
        monkeypatch.setattr(registry_module, "PROJECT_ROOT", str(bundle_root))
        registry = registry_module.PluginRegistry()
        manifests = registry.list_manifests()

        assert any(manifest.plugin_id == "video.demo.bundle" for manifest in manifests)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
