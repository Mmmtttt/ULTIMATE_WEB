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


def _load_build_unified_module():
    module_path = ROOT_DIR / "scripts" / "build_unified.py"
    spec = importlib.util.spec_from_file_location("build_unified_for_snapshot_test", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None
    assert spec.loader is not None
    sys.modules[spec.name] = module
    scripts_dir = str(module_path.parent)
    path_inserted = False
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
        path_inserted = True
    try:
        spec.loader.exec_module(module)
    finally:
        if path_inserted:
            try:
                sys.path.remove(scripts_dir)
            except ValueError:
                pass
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
                "storage": {
                    "comic_dir": {
                        "template": "{author}/{title}",
                        "fallback_templates": [
                            "comics/{author}/{title}",
                            "{album_id}",
                        ],
                    }
                },
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
        assert (((merged_manifest.get("storage") or {}).get("comic_dir") or {}).get("template")) == "{author}/{title}"
        assert (
            (((merged_manifest.get("storage") or {}).get("comic_dir") or {}).get("fallback_templates") or [])
            == ["comics/{author}/{title}", "{album_id}"]
        )
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


def test_build_target_keeps_third_party_for_android_backend_build_input():
    build_unified = _load_build_unified_module()
    workspace_tmp_root = ROOT_DIR / ".codex_test_runtime"
    workspace_tmp_root.mkdir(parents=True, exist_ok=True)
    temp_dir = workspace_tmp_root / f"android_build_target_{uuid4().hex[:8]}"
    temp_dir.mkdir(parents=True, exist_ok=True)

    try:
        backend_src = temp_dir / "backend_src"
        frontend_dist = temp_dir / "frontend_dist"
        output_dir = temp_dir / "out"

        (backend_src / "app.py").parent.mkdir(parents=True, exist_ok=True)
        (backend_src / "app.py").write_text("print('backend')\n", encoding="utf-8")
        _write_json(
            backend_src / "third_party" / "demo_plugin" / "ultimate-plugin.json",
            {
                "plugin": {
                    "id": "comic.demo.mobile",
                    "name": "Demo Mobile",
                    "entrypoint": "./ultimate_provider.py:DemoProvider",
                },
                "media_types": ["comic"],
            },
        )
        (backend_src / "third_party_config.json").write_text("{}", encoding="utf-8")
        (frontend_dist / "index.html").parent.mkdir(parents=True, exist_ok=True)
        (frontend_dist / "index.html").write_text("<html></html>", encoding="utf-8")

        original_backend_dir = build_unified.BACKEND_DIR
        build_unified.BACKEND_DIR = backend_src
        try:
            target_dir = build_unified.build_target(
                {"id": "android", "runtime_profile": "mobile_core", "third_party_enabled": False, "notes": ""},
                frontend_dist_dir=frontend_dist,
                output_dir=output_dir,
                app_version="1.2.3",
            )
        finally:
            build_unified.BACKEND_DIR = original_backend_dir

        assert (target_dir / "comic_backend" / "third_party" / "demo_plugin" / "ultimate-plugin.json").exists()
        assert not (target_dir / "comic_backend" / "third_party_config.json").exists()
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_package_android_injects_embedded_backend_after_cap_sync(monkeypatch):
    package_unified = _load_package_unified_module()
    workspace_tmp_root = ROOT_DIR / ".codex_test_runtime"
    workspace_tmp_root.mkdir(parents=True, exist_ok=True)
    temp_dir = workspace_tmp_root / f"android_package_order_{uuid4().hex[:8]}"
    temp_dir.mkdir(parents=True, exist_ok=True)

    try:
        staged_target_dir = temp_dir / "staged"
        staged_web_dir = staged_target_dir / "comic_frontend_dist"
        staged_backend_dir = staged_target_dir / "comic_backend"
        staged_web_dir.mkdir(parents=True, exist_ok=True)
        staged_backend_dir.mkdir(parents=True, exist_ok=True)
        (staged_web_dir / "index.html").write_text("<html><body>ok</body></html>", encoding="utf-8")
        (staged_backend_dir / "app.py").write_text("print('backend')\n", encoding="utf-8")
        (staged_target_dir / "runtime.env").write_text("BACKEND_RUNTIME_PROFILE=android\n", encoding="utf-8")

        out_dir = temp_dir / "out"
        out_dir.mkdir(parents=True, exist_ok=True)
        events = []

        monkeypatch.setattr(package_unified, "resolve_android_java_env", lambda: {"JAVA_HOME": "/fake/java"})
        monkeypatch.setattr(package_unified, "resolve_android_sdk_dir", lambda: "/fake/sdk")
        monkeypatch.setattr(package_unified, "write_android_local_properties", lambda cwd, sdk: events.append(f"local_properties:{cwd}"))
        monkeypatch.setattr(package_unified, "apply_android_launcher_icon", lambda workspace_dir, cfg: events.append("apply_icon"))

        def fake_inject(workspace_dir, packager_cfg, app_version):
            events.append("inject_backend")

        monkeypatch.setattr(package_unified, "inject_android_embedded_backend", fake_inject)

        def fake_run_cmd(cmd, cwd, env=None):
            command_text = " ".join(cmd)
            events.append(command_text)
            if "cap add android" in command_text:
                (Path(cwd) / "android" / "app" / "src" / "main").mkdir(parents=True, exist_ok=True)
            if "gradlew" in command_text:
                apk_path = Path(cwd) / "app" / "build" / "outputs" / "apk" / "debug"
                apk_path.mkdir(parents=True, exist_ok=True)
                (apk_path / "app-debug.apk").write_bytes(b"apk")
            return 0, f"ok: {command_text}"

        monkeypatch.setattr(package_unified, "run_cmd", fake_run_cmd)

        result = package_unified.package_android(
            target="android",
            staged_target_dir=staged_target_dir,
            packager_cfg={
                "type": "capacitor",
                "app_id": "com.ultimate.web",
                "app_name": "UltimateWeb",
                "web_dir": "comic_frontend_dist",
                "workspace_web_dir": "web",
                "embed_backend": True,
                "backend_port": 5000,
                "gradle_task": "assembleDebug",
            },
            target_out_dir=out_dir,
            execute=True,
        )

        assert result.status == "built"
        sync_index = events.index("npx.cmd cap sync android" if package_unified.os.name == "nt" else "npx cap sync android")
        inject_index = events.index("inject_backend")
        gradle_index = next(i for i, value in enumerate(events) if "gradlew" in value)
        assert sync_index < inject_index < gradle_index
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_ensure_android_project_chaquopy_app_embeds_snapshot_into_bootstrap():
    package_unified = _load_package_unified_module()
    workspace_tmp_root = ROOT_DIR / ".codex_test_runtime"
    workspace_tmp_root.mkdir(parents=True, exist_ok=True)
    temp_dir = workspace_tmp_root / f"android_embed_snapshot_{uuid4().hex[:8]}"
    temp_dir.mkdir(parents=True, exist_ok=True)

    try:
        workspace_dir = temp_dir / "workspace"
        android_project_dir = workspace_dir / "android"
        app_gradle = android_project_dir / "app" / "build.gradle"
        app_gradle.parent.mkdir(parents=True, exist_ok=True)
        app_gradle.write_text(
            "apply plugin: 'com.android.application'\n"
            "android {\n"
            "    defaultConfig {\n"
            "        minSdkVersion rootProject.ext.minSdkVersion\n"
            "    }\n"
            "}\n",
            encoding="utf-8",
        )

        source_backend_dir = workspace_dir / package_unified.get_android_workspace_backend_dir({})
        source_backend_dir.mkdir(parents=True, exist_ok=True)
        (source_backend_dir / "app.py").write_text("def run_backend_server(**kwargs):\n    return None\n", encoding="utf-8")
        _write_json(
            source_backend_dir / "third_party" / "demo_plugin" / "ultimate-plugin.json",
            {
                "plugin": {
                    "id": "comic.demo.mobile",
                    "name": "Demo Mobile",
                    "entrypoint": "./ultimate_provider.py:DemoProvider",
                },
                "media_types": ["comic"],
                "identity": {"host_id_prefix": "DEMO"},
            },
        )

        package_unified.ensure_android_project_chaquopy_app(
            android_project_dir=android_project_dir,
            workspace_dir=workspace_dir,
            packager_cfg={"app_id": "com.ultimate.web", "backend_port": 5000},
            app_version="1.2.3",
        )

        bootstrap_path = android_project_dir / "app" / "src" / "main" / "python" / "ultimate_android_backend.py"
        snapshot_source_path = android_project_dir / "app" / "src" / "main" / "python" / "protocol" / package_unified.MOBILE_PROTOCOL_SNAPSHOT_FILENAME
        bootstrap_text = bootstrap_path.read_text(encoding="utf-8")

        assert snapshot_source_path.exists()
        assert "EMBEDDED_PROTOCOL_SNAPSHOT_JSON =" in bootstrap_text
        assert "comic.demo.mobile" in bootstrap_text
        assert "_materialize_protocol_snapshot" in bootstrap_text
        assert '"comic.demo.mobile"' in snapshot_source_path.read_text(encoding="utf-8")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_inspect_android_apk_for_snapshot_reports_matching_entries(tmp_path):
    package_unified = _load_package_unified_module()
    apk_path = tmp_path / "app-debug.apk"

    import zipfile

    with zipfile.ZipFile(apk_path, "w") as archive:
        archive.writestr("assets/chaquopy/app/protocol/mobile_protocol_snapshot.json", "{}")
        archive.writestr("assets/chaquopy/app/protocol/other.json", "{}")
        archive.writestr(
            "assets/chaquopy/app/ultimate_android_backend.py",
            "EMBEDDED_PROTOCOL_SNAPSHOT_JSON = '{}'\n",
        )

    summary = package_unified.inspect_android_apk_for_snapshot(apk_path)

    assert "mobile_protocol_snapshot.json" in summary
    assert "other.json" in summary
    assert "ultimate_android_backend.py" in summary
    assert "embedded_snapshot_bootstraps" in summary
