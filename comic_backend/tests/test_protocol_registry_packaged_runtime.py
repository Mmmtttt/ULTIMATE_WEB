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
