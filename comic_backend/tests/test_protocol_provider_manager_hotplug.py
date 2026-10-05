import json
import platform
import shutil
import sys
from pathlib import Path
from uuid import uuid4


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from protocol.provider_manager import ProviderManager
from protocol.registry import PluginRegistry


def _platform_tag() -> str:
    system_name = str(platform.system() or "").strip().lower() or sys.platform.lower()
    machine = str(platform.machine() or "").strip().lower() or "unknown"
    return f"{system_name}-{machine}"


def _python_tag() -> str:
    return f"py{sys.version_info.major}{sys.version_info.minor}"


def test_provider_manager_loads_plugin_from_external_runtime_paths():
    workspace_tmp_root = Path.cwd() / ".codex_test_runtime"
    workspace_tmp_root.mkdir(parents=True, exist_ok=True)
    temp_dir = workspace_tmp_root / f"provider_hotplug_{uuid4().hex[:8]}"
    temp_dir.mkdir(parents=True, exist_ok=True)

    try:
        plugin_dir = temp_dir / "plugins" / "demo_plugin"
        helper_dir = plugin_dir / "src"
        vendor_dir = plugin_dir / "vendor" / "python" / _python_tag() / _platform_tag()
        helper_dir.mkdir(parents=True, exist_ok=True)
        vendor_dir.mkdir(parents=True, exist_ok=True)

        (plugin_dir / "ultimate-plugin.json").write_text(
            json.dumps(
                {
                    "protocol_version": "2.0",
                    "plugin": {
                        "id": "comic.demo.hotplug",
                        "name": "Demo Hotplug",
                        "version": "1.0.0",
                        "entrypoint": "./ultimate_provider.py:DemoProvider",
                        "config_key": "demo_hotplug",
                    },
                    "media_types": ["comic"],
                    "capabilities": [{"key": "catalog.search"}],
                    "runtime": {
                        "python_paths": [".", "src"],
                        "vendor_path_templates": [
                            "vendor/python",
                            "vendor/python/{python_tag}",
                            "vendor/python/{python_tag}/{platform_tag}",
                        ],
                    },
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        (helper_dir / "helper_module.py").write_text("VALUE = 'helper-ok'\n", encoding="utf-8")
        (vendor_dir / "vendored_module.py").write_text("VALUE = 'vendor-ok'\n", encoding="utf-8")
        (plugin_dir / "ultimate_provider.py").write_text(
            "from protocol.base import ProtocolProvider\n"
            "from helper_module import VALUE as HELPER_VALUE\n"
            "from vendored_module import VALUE as VENDOR_VALUE\n"
            "class DemoProvider(ProtocolProvider):\n"
            "    def execute(self, capability, params, context, config):\n"
            "        return {'helper': HELPER_VALUE, 'vendor': VENDOR_VALUE}\n",
            encoding="utf-8",
        )

        registry = PluginRegistry(search_root=str(plugin_dir.parent))
        manager = ProviderManager(registry=registry)

        # 新版启用守卫要求平台显式启用后才能执行 catalog.* 能力
        class _EnabledConfigStore:
            def get_plugin_config(self, config_key, reload=False):
                return {"enabled": True}

        manager._config_store = _EnabledConfigStore()
        result = manager.execute("comic.demo.hotplug", "catalog.search", params={}, context={})

        assert result == {"helper": "helper-ok", "vendor": "vendor-ok"}
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
