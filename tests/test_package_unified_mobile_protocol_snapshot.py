from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from pathlib import Path
from uuid import uuid4


ROOT_DIR = Path(__file__).resolve().parents[1]


def _load_package_unified_module():
    module_path = ROOT_DIR / "scripts" / "package_unified.py"
    spec = importlib.util.spec_from_file_location("package_unified_for_snapshot_test", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def test_build_mobile_protocol_snapshot_merges_manifest_and_overlay_and_keeps_overlay_only_plugins():
    package_unified = _load_package_unified_module()
    workspace_tmp_root = ROOT_DIR / ".codex_test_runtime"
    workspace_tmp_root.mkdir(parents=True, exist_ok=True)
    temp_dir = workspace_tmp_root / f"mobile_snapshot_{uuid4().hex[:8]}"
    temp_dir.mkdir(parents=True, exist_ok=True)

    try:
        third_party_root = temp_dir / "third_party"

        _write_json(
            third_party_root / "demo_plugin" / "ultimate-plugin.json",
            {
                "protocol_version": "2.0",
                "plugin": {
                    "id": "video.demo.snapshot",
                    "name": "Demo Snapshot",
                    "version": "1.2.3",
                    "entrypoint": "./ultimate_provider.py:DemoProvider",
                    "config_key": "demo_snapshot",
                },
                "media_types": ["video"],
            },
        )
        _write_json(
            third_party_root / "demo_plugin" / "ultimate-host.json",
            {
                "plugin": {"id": "video.demo.snapshot"},
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
        )
        _write_json(
            third_party_root / "overlay_only_plugin" / "ultimate-host.json",
            {
                "plugin": {
                    "id": "comic.overlay.only",
                    "name": "Overlay Only",
                    "config_key": "overlay_only",
                },
                "media_types": ["comic"],
                "identity": {
                    "platform_label": "ONLY",
                    "host_id_prefix": "ONLY",
                },
                "storage": {
                    "host_resolution": {
                        "comic_local_dir": {
                            "path_templates": ["{host_prefix}/{original_id}"]
                        }
                    }
                },
            },
        )

        snapshot = package_unified.build_mobile_protocol_snapshot(third_party_root)
        manifests = {item["plugin"]["id"]: item for item in snapshot.get("manifests", [])}

        merged_manifest = manifests["video.demo.snapshot"]
        overlay_only_manifest = manifests["comic.overlay.only"]

        assert merged_manifest["plugin"]["entrypoint"] == package_unified.SNAPSHOT_PROVIDER_ENTRYPOINT
        assert merged_manifest["identity"]["host_id_prefix"] == "DEMO"
        assert (
            (((merged_manifest.get("presentation") or {}).get("media_card") or {}).get("cover") or {}).get("mobile_aspect_ratio")
            == "3 / 2"
        )

        assert overlay_only_manifest["plugin"]["entrypoint"] == package_unified.SNAPSHOT_PROVIDER_ENTRYPOINT
        assert overlay_only_manifest["plugin"]["version"] == "0.0.0-snapshot"
        assert overlay_only_manifest["identity"]["host_id_prefix"] == "ONLY"
        assert (
            (((overlay_only_manifest.get("storage") or {}).get("host_resolution") or {}).get("comic_local_dir") or {}).get("path_templates")
            == ["{host_prefix}/{original_id}"]
        )
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_write_android_capacitor_plan_keeps_backend_build_input_out_of_web_dir():
    package_unified = _load_package_unified_module()
    workspace_tmp_root = ROOT_DIR / ".codex_test_runtime"
    workspace_tmp_root.mkdir(parents=True, exist_ok=True)
    temp_dir = workspace_tmp_root / f"android_workspace_{uuid4().hex[:8]}"
    temp_dir.mkdir(parents=True, exist_ok=True)

    try:
        staged_target_dir = temp_dir / "staged"
        staged_web_dir = staged_target_dir / "comic_frontend_dist"
        staged_backend_dir = staged_target_dir / "comic_backend"
        staged_web_dir.mkdir(parents=True, exist_ok=True)
        staged_backend_dir.mkdir(parents=True, exist_ok=True)

        (staged_web_dir / "index.html").write_text("<html><head></head><body>ok</body></html>", encoding="utf-8")
        (staged_backend_dir / "app.py").write_text("print('backend')\n", encoding="utf-8")
        (staged_target_dir / "runtime.env").write_text("BACKEND_RUNTIME_PROFILE=android\n", encoding="utf-8")

        packager_cfg = {
            "app_id": "com.ultimate.web",
            "app_name": "UltimateWeb",
            "embed_backend": True,
            "backend_port": 5000,
            "web_dir": "comic_frontend_dist",
            "workspace_web_dir": "web",
            "workspace_backend_dir": "_backend_build_input",
            "gradle_task": "assembleDebug",
        }

        _commands, workspace_dir, _apk_relative_path = package_unified.write_android_capacitor_plan(
            target_out_dir=temp_dir / "out",
            staged_target_dir=staged_target_dir,
            packager_cfg=packager_cfg,
            app_version="1.2.3",
        )

        assert (workspace_dir / "web" / "index.html").exists()
        assert not (workspace_dir / "web" / "backend_source").exists()
        assert not (workspace_dir / "web" / "backend_bootstrap.json").exists()
        assert not (workspace_dir / "web" / "runtime.env").exists()
        assert (workspace_dir / "_backend_build_input" / "app.py").exists()

        plan_text = (temp_dir / "out" / "android_packaging_plan.md").read_text(encoding="utf-8")
        assert "`_backend_build_input`" in plan_text
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
