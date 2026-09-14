from __future__ import annotations

import importlib
import importlib.util
import json
import os
import shutil
import sys
from uuid import uuid4
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]


def _load_package_unified_module():
    module_path = ROOT_DIR / "scripts" / "package_unified.py"
    spec = importlib.util.spec_from_file_location("package_unified_for_test", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_manifest(plugin_dir: Path, plugin_id: str, packaging: dict | None = None) -> None:
    plugin_dir.mkdir(parents=True, exist_ok=True)
    (plugin_dir / "ultimate-plugin.json").write_text(
        json.dumps(
            {
                "protocol_version": "1.0",
                "plugin": {
                    "id": plugin_id,
                    "name": plugin_id,
                    "version": "1.0.0",
                    "entrypoint": "./ultimate_provider.py:DemoProvider",
                },
                "media_types": ["comic"],
                "capabilities": [{"key": "catalog.search"}],
                "packaging": packaging or {},
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (plugin_dir / "ultimate_provider.py").write_text(
        "class DemoProvider:\n"
        "    def __init__(self, manifest=None, manifest_path=''):\n"
        "        self.manifest = manifest or {}\n"
        "        self.manifest_path = manifest_path\n"
        "    def execute(self, capability, params, context, config):\n"
        "        return {}\n"
        "    def normalize_config(self, payload):\n"
        "        return dict(payload or {})\n"
        "    def serialize_public_config(self, config):\n"
        "        return dict(config or {})\n",
        encoding="utf-8",
    )


def test_resident_dependency_pool_is_available_without_plugin_sources():
    package_unified = _load_package_unified_module()

    requirements = package_unified.load_resident_dependency_requirements({}, "android")

    assert "commonx>=0.6.38" in requirements
    assert "curl-cffi==0.16.3" in requirements
    assert "chaquopy-libffi>=3.3" in requirements


def test_android_dependency_collection_merges_resident_and_plugin_requirements(tmp_path):
    package_unified = _load_package_unified_module()
    third_party = tmp_path / "third_party"
    _write_manifest(
        third_party / "demo",
        "demo.plugin",
        {"android": {"enabled": True, "pip_requirements": ["demo-only==1.0"]}},
    )

    requirements = package_unified.collect_android_pip_install_entries(
        {"android_backend_enable_third_party": True},
        tmp_path,
    )
    flattened = [item for entry in requirements for item in entry]

    assert "commonx>=0.6.38" in flattened
    assert "demo-only==1.0" in flattened


def test_write_pyinstaller_scripts_excludes_external_plugins_from_compiled_binary():
    package_unified = _load_package_unified_module()
    workspace_tmp_root = ROOT_DIR / ".codex_test_runtime"
    workspace_tmp_root.mkdir(parents=True, exist_ok=True)
    temp_dir = workspace_tmp_root / f"pyinstaller_paths_{uuid4().hex[:8]}"
    temp_dir.mkdir(parents=True, exist_ok=True)

    try:
        staged_target_dir = temp_dir / "staged"
        backend_third_party = staged_target_dir / "comic_backend" / "third_party"
        _write_manifest(
            backend_third_party / "plugin_alpha",
            "comic.alpha",
            packaging={
                "pyinstaller": {
                    "collect_all": ["common", "Crypto"],
                    "pip_requirements": ["commonx>=0.6.38", "pycryptodome>=3.20.0"],
                }
            },
        )
        _write_manifest(
            backend_third_party / "plugin_beta",
            "video.beta",
            packaging={
                "pyinstaller": {
                    "collect_all": ["curl_cffi", "cffi"],
                    "hidden_imports": ["curl_cffi._wrapper"],
                    "pip_requirements": ["curl_cffi>=0.6.0", "cffi>=1.15.0"],
                }
            },
        )
        _write_manifest(backend_third_party / "plugin_gamma", "comic.gamma")
        _write_manifest(backend_third_party / "plugin_delta", "video.delta")
        _write_manifest(
            backend_third_party / "plugin_epsilon",
            "video.epsilon",
            packaging={
                "pyinstaller": {
                    "collect_all": ["curl_cffi", "lxml"],
                    "pip_requirements": ["curl_cffi>=0.6.0", "lxml>=4.9.0"],
                }
            },
        )

        cmd = package_unified.write_pyinstaller_scripts(
            out_dir=temp_dir / "out",
            staged_target_dir=staged_target_dir,
            target="windows" if os.name == "nt" else "linux",
            binary_name="ultimate_backend_test",
            entry="comic_backend/app.py",
            runtime_env={
                "BACKEND_RUNTIME_PROFILE": "full",
                "BACKEND_ENABLE_THIRD_PARTY": "true",
            },
        )

        collect_all_args = [cmd[index + 1] for index, item in enumerate(cmd[:-1]) if item == "--collect-all"]
        collect_submodules_args = [
            cmd[index + 1] for index, item in enumerate(cmd[:-1]) if item == "--collect-submodules"
        ]
        hidden_import_args = [cmd[index + 1] for index, item in enumerate(cmd[:-1]) if item == "--hidden-import"]

        assert cmd[-1] == "comic_backend/app.py"
        assert "common" not in collect_all_args
        assert "Crypto" not in collect_all_args
        assert "curl_cffi" not in collect_all_args
        assert "lxml" not in collect_all_args
        assert "cffi" not in collect_all_args
        assert "curl_cffi._wrapper" not in hidden_import_args
        assert "email" in collect_submodules_args
        assert "http" in collect_submodules_args
        assert "urllib" in collect_submodules_args
        assert "xml" in collect_submodules_args
        assert "email.mime" in hidden_import_args
        assert "email.mime.multipart" in hidden_import_args
        assert "email.mime.text" in hidden_import_args
        assert "http.cookiejar" in hidden_import_args
        assert "urllib.request" in hidden_import_args
        assert "protocol.credential_guard" in hidden_import_args
        assert "third_party" in hidden_import_args
        assert "third_party.external_api" in hidden_import_args
        assert "third_party.platform_service" in hidden_import_args
        assert "third_party.adapter" in hidden_import_args
        assert "third_party.credential_guard" in hidden_import_args
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_desktop_plugin_runtime_hidden_imports_are_importable_stdlib_modules():
    package_unified = _load_package_unified_module()

    for module_name in package_unified.DESKTOP_PLUGIN_RUNTIME_HIDDEN_IMPORTS:
        importlib.import_module(module_name)


def test_write_pyinstaller_scripts_external_mode_keeps_plugins_outside_executable():
    package_unified = _load_package_unified_module()
    workspace_tmp_root = ROOT_DIR / ".codex_test_runtime"
    workspace_tmp_root.mkdir(parents=True, exist_ok=True)
    temp_dir = workspace_tmp_root / f"pyinstaller_bundled_{uuid4().hex[:8]}"
    temp_dir.mkdir(parents=True, exist_ok=True)

    try:
        staged_target_dir = temp_dir / "staged"
        backend_third_party = staged_target_dir / "comic_backend" / "third_party"
        _write_manifest(
            backend_third_party / "plugin_alpha",
            "comic.alpha",
            packaging={
                "pyinstaller": {
                    "collect_all": ["common", "Crypto"],
                    "pip_requirements": ["commonx>=0.6.38", "pycryptodome>=3.20.0"],
                }
            },
        )
        _write_manifest(
            backend_third_party / "plugin_beta",
            "video.beta",
            packaging={
                "pyinstaller": {
                    "collect_all": ["curl_cffi", "cffi"],
                    "hidden_imports": ["curl_cffi._wrapper"],
                    "pip_requirements": ["curl_cffi>=0.6.0", "cffi>=1.15.0"],
                }
            },
        )

        cmd = package_unified.write_pyinstaller_scripts(
            out_dir=temp_dir / "out",
            staged_target_dir=staged_target_dir,
            target="windows" if os.name == "nt" else "linux",
            binary_name="ultimate_backend_test",
            entry="comic_backend/app.py",
            runtime_env={
                "BACKEND_RUNTIME_PROFILE": "full",
                "BACKEND_ENABLE_THIRD_PARTY": "true",
            },
            plugin_package_mode="external",
        )

        collect_all_args = [cmd[index + 1] for index, item in enumerate(cmd[:-1]) if item == "--collect-all"]
        hidden_import_args = [cmd[index + 1] for index, item in enumerate(cmd[:-1]) if item == "--hidden-import"]
        add_data_args = [cmd[index + 1] for index, item in enumerate(cmd[:-1]) if item == "--add-data"]

        assert "common" not in collect_all_args
        assert "Crypto" not in collect_all_args
        assert "curl_cffi" not in collect_all_args
        assert "cffi" not in collect_all_args
        assert "curl_cffi._wrapper" not in hidden_import_args
        assert not any("comic_backend/third_party/plugin_alpha" in item for item in add_data_args)
        assert not any("comic_backend/third_party/plugin_beta" in item for item in add_data_args)
        assert cmd[-1] == "comic_backend/app.py"
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_prepare_desktop_release_bundle_moves_plugins_outside_backend_source():
    package_unified = _load_package_unified_module()
    workspace_tmp_root = ROOT_DIR / ".codex_test_runtime"
    workspace_tmp_root.mkdir(parents=True, exist_ok=True)
    temp_dir = workspace_tmp_root / f"bundle_plugins_{uuid4().hex[:8]}"
    temp_dir.mkdir(parents=True, exist_ok=True)

    try:
        staged_target_dir = temp_dir / "staged"
        backend_src = staged_target_dir / "comic_backend"
        third_party_root = backend_src / "third_party"
        (backend_src / "third_party" / "__init__.py").parent.mkdir(parents=True, exist_ok=True)
        (backend_src / "third_party" / "__init__.py").write_text("", encoding="utf-8")
        (backend_src / "third_party" / "external_api.py").write_text("pass\n", encoding="utf-8")
        (staged_target_dir / "comic_frontend_dist" / "index.html").parent.mkdir(parents=True, exist_ok=True)
        (staged_target_dir / "comic_frontend_dist" / "index.html").write_text("<html></html>", encoding="utf-8")

        _write_manifest(
            third_party_root / "plugin_alpha",
            "comic.alpha",
            packaging={"external": {"pip_requirements": ["commonx>=0.6.38"]}},
        )

        bundle_dir = package_unified.prepare_desktop_release_bundle(
            target="windows" if os.name == "nt" else "linux",
            target_out_dir=temp_dir / "out",
            staged_target_dir=staged_target_dir,
            binary_name="ultimate_backend_test",
            runtime_env={
                "BACKEND_RUNTIME_PROFILE": "full",
                "BACKEND_ENABLE_THIRD_PARTY": "true",
            },
        )

        dep_manifest = bundle_dir / "runtime_deps" / "dependency_pool_manifest.json"
        assert not (bundle_dir / "plugins" / "plugin_alpha").exists()
        assert dep_manifest.exists()
        assert "commonx>=0.6.38" in dep_manifest.read_text(encoding="utf-8")
        assert not (bundle_dir / "backend_source" / "third_party" / "plugin_alpha").exists()
        assert (bundle_dir / "backend_source" / "third_party" / "__init__.py").exists()
        assert (bundle_dir / "start_project.bat").exists()
        assert (bundle_dir / "start_project.ps1").exists()
        assert (bundle_dir / "scripts" / "install_plugin_deps.ps1").exists()
        assert (bundle_dir / "scripts" / "install_plugin_deps.sh").exists()
        assert not (bundle_dir / "start_app.bat").exists()
        assert not (bundle_dir / "start_backend.bat").exists()
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_third_party_excludes_skip_bundle_source_external_copy_and_pyinstaller_add_data(monkeypatch):
    package_unified = _load_package_unified_module()
    monkeypatch.setenv(package_unified.PLUGIN_PACKAGE_EXCLUDES_ENV, "plugin_beta")
    workspace_tmp_root = ROOT_DIR / ".codex_test_runtime"
    workspace_tmp_root.mkdir(parents=True, exist_ok=True)
    temp_dir = workspace_tmp_root / f"bundle_excluded_plugins_{uuid4().hex[:8]}"
    temp_dir.mkdir(parents=True, exist_ok=True)

    try:
        staged_target_dir = temp_dir / "staged"
        backend_src = staged_target_dir / "comic_backend"
        third_party_root = backend_src / "third_party"
        (third_party_root / "__init__.py").parent.mkdir(parents=True, exist_ok=True)
        (third_party_root / "__init__.py").write_text("", encoding="utf-8")
        (staged_target_dir / "comic_frontend_dist" / "index.html").parent.mkdir(parents=True, exist_ok=True)
        (staged_target_dir / "comic_frontend_dist" / "index.html").write_text("<html></html>", encoding="utf-8")

        _write_manifest(third_party_root / "plugin_alpha", "comic.alpha")
        _write_manifest(
            third_party_root / "plugin_beta",
            "video.beta",
            packaging={"pyinstaller": {"collect_all": ["curl_cffi"]}},
        )

        bundle_dir = package_unified.prepare_desktop_release_bundle(
            target="windows" if os.name == "nt" else "linux",
            target_out_dir=temp_dir / "out_external",
            staged_target_dir=staged_target_dir,
            binary_name="ultimate_backend_test",
            runtime_env={"BACKEND_RUNTIME_PROFILE": "full", "BACKEND_ENABLE_THIRD_PARTY": "true"},
        )
        assert not (bundle_dir / "plugins" / "plugin_alpha").exists()
        assert not (bundle_dir / "plugins" / "plugin_beta").exists()
        assert not (bundle_dir / "backend_source" / "third_party" / "plugin_beta").exists()

        cmd = package_unified.write_pyinstaller_scripts(
            out_dir=temp_dir / "pyinstaller",
            staged_target_dir=staged_target_dir,
            target="windows" if os.name == "nt" else "linux",
            binary_name="ultimate_backend_test",
            entry="comic_backend/app.py",
            runtime_env={"BACKEND_RUNTIME_PROFILE": "full", "BACKEND_ENABLE_THIRD_PARTY": "true"},
            plugin_package_mode="external",
        )
        collect_all_args = [cmd[index + 1] for index, item in enumerate(cmd[:-1]) if item == "--collect-all"]
        add_data_args = [cmd[index + 1] for index, item in enumerate(cmd[:-1]) if item == "--add-data"]
        assert "curl_cffi" not in collect_all_args
        assert not any("comic_backend/third_party/plugin_beta" in item for item in add_data_args)
        assert not any("comic_backend/third_party/plugin_alpha" in item for item in add_data_args)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_external_pyinstaller_does_not_embed_project_plugin_host_overlays(monkeypatch):
    package_unified = _load_package_unified_module()
    workspace_tmp_root = ROOT_DIR / ".codex_test_runtime"
    workspace_tmp_root.mkdir(parents=True, exist_ok=True)
    temp_dir = workspace_tmp_root / f"bundle_project_plugins_{uuid4().hex[:8]}"
    temp_dir.mkdir(parents=True, exist_ok=True)

    try:
        project_plugins = temp_dir / "project_plugins"
        _write_manifest(project_plugins / "normal_plugin", "comic.normal")
        (project_plugins / "host_overlay_only").mkdir(parents=True, exist_ok=True)
        (project_plugins / "host_overlay_only" / "ultimate-host.json").write_text(
            json.dumps({"plugin": {"id": "video.child", "config_parent_key": "parent"}}, ensure_ascii=False),
            encoding="utf-8",
        )
        monkeypatch.setattr(package_unified, "PROJECT_PLUGINS_DIR", project_plugins)

        staged_target_dir = temp_dir / "staged"
        backend_third_party = staged_target_dir / "comic_backend" / "third_party"
        _write_manifest(backend_third_party / "plugin_alpha", "comic.alpha")

        cmd = package_unified.write_pyinstaller_scripts(
            out_dir=temp_dir / "pyinstaller",
            staged_target_dir=staged_target_dir,
            target="windows" if os.name == "nt" else "linux",
            binary_name="ultimate_backend_test",
            entry="comic_backend/app.py",
            runtime_env={"BACKEND_RUNTIME_PROFILE": "full", "BACKEND_ENABLE_THIRD_PARTY": "true"},
            plugin_package_mode="external",
        )

        add_data_args = [cmd[index + 1] for index, item in enumerate(cmd[:-1]) if item == "--add-data"]
        assert not any("plugins/normal_plugin" in item for item in add_data_args)
        assert not any("plugins/host_overlay_only" in item for item in add_data_args)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_prepare_desktop_release_bundle_external_mode_moves_defaults_to_extension_root():
    package_unified = _load_package_unified_module()
    workspace_tmp_root = ROOT_DIR / ".codex_test_runtime"
    workspace_tmp_root.mkdir(parents=True, exist_ok=True)
    temp_dir = workspace_tmp_root / f"bundle_bundled_plugins_{uuid4().hex[:8]}"
    temp_dir.mkdir(parents=True, exist_ok=True)

    try:
        staged_target_dir = temp_dir / "staged"
        backend_src = staged_target_dir / "comic_backend"
        third_party_root = backend_src / "third_party"
        (backend_src / "third_party" / "__init__.py").parent.mkdir(parents=True, exist_ok=True)
        (backend_src / "third_party" / "__init__.py").write_text("", encoding="utf-8")
        (staged_target_dir / "comic_frontend_dist" / "index.html").parent.mkdir(parents=True, exist_ok=True)
        (staged_target_dir / "comic_frontend_dist" / "index.html").write_text("<html></html>", encoding="utf-8")

        _write_manifest(
            third_party_root / "plugin_alpha",
            "comic.alpha",
            packaging={"external": {"pip_requirements": ["commonx>=0.6.38"]}},
        )

        bundle_dir = package_unified.prepare_desktop_release_bundle(
            target="windows" if os.name == "nt" else "linux",
            target_out_dir=temp_dir / "out",
            staged_target_dir=staged_target_dir,
            binary_name="ultimate_backend_test",
            runtime_env={
                "BACKEND_RUNTIME_PROFILE": "full",
                "BACKEND_ENABLE_THIRD_PARTY": "true",
            },
            plugin_package_mode="external",
        )

        assert not (bundle_dir / "backend_source" / "third_party" / "plugin_alpha").exists()
        assert not (bundle_dir / "plugins" / "plugin_alpha").exists()
        assert (bundle_dir / "plugins" / "README.md").exists()
        dep_manifest = bundle_dir / "runtime_deps" / "dependency_pool_manifest.json"
        assert dep_manifest.exists()
        assert "commonx>=0.6.38" in dep_manifest.read_text(encoding="utf-8")
        readme_text = (bundle_dir / "README.md").read_text(encoding="utf-8")
        assert "plugin package mode: `external`" in readme_text
        assert "external extension" in (bundle_dir / "plugins" / "README.md").read_text(encoding="utf-8")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_write_external_plugin_dependency_scripts_are_idempotent_and_fail_fast():
    package_unified = _load_package_unified_module()
    workspace_tmp_root = ROOT_DIR / ".codex_test_runtime"
    workspace_tmp_root.mkdir(parents=True, exist_ok=True)
    temp_dir = workspace_tmp_root / f"bundle_plugin_deps_{uuid4().hex[:8]}"
    temp_dir.mkdir(parents=True, exist_ok=True)

    try:
        plugin_root = temp_dir / "plugins" / "plugin_delta"
        _write_manifest(
            plugin_root,
            "video.delta",
            packaging={"external": {"pip_requirements": ["curl_cffi>=0.6.0", "lxml>=4.9.0"]}},
        )

        package_unified.write_external_plugin_dependency_scripts(temp_dir, [plugin_root])

        ps1_text = (temp_dir / "install_plugin_deps.ps1").read_text(encoding="utf-8")
        sh_text = (temp_dir / "install_plugin_deps.sh").read_text(encoding="utf-8")

        assert ".ultimate_vendor_state.json" in ps1_text
        assert ".ultimate_vendor_state.json" in sh_text
        assert "--upgrade" not in ps1_text
        assert "--upgrade" not in sh_text
        assert "already installed" in ps1_text
        assert "already installed" in sh_text
        assert "$LASTEXITCODE" in ps1_text
        assert "python version mismatch" in ps1_text
        assert "python version mismatch" in sh_text
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_install_external_plugin_dependencies_writes_state_and_skips_repeat_install(monkeypatch):
    package_unified = _load_package_unified_module()
    workspace_tmp_root = ROOT_DIR / ".codex_test_runtime"
    workspace_tmp_root.mkdir(parents=True, exist_ok=True)
    temp_dir = workspace_tmp_root / f"bundle_plugin_state_{uuid4().hex[:8]}"
    temp_dir.mkdir(parents=True, exist_ok=True)

    try:
        plugin_root = temp_dir / "plugins" / "plugin_alpha"
        _write_manifest(
            plugin_root,
            "comic.alpha",
            packaging={"external": {"pip_requirements": ["commonx>=0.6.38"]}},
        )

        call_log = []

        def fake_run_cmd(cmd, cwd, env=None):
            call_log.append({"cmd": list(cmd), "cwd": str(cwd)})
            vendor_target = Path(cmd[cmd.index("--target") + 1])
            vendor_target.mkdir(parents=True, exist_ok=True)
            (vendor_target / "installed.txt").write_text("ok", encoding="utf-8")
            return 0, "installed"

        monkeypatch.setattr(package_unified, "run_cmd", fake_run_cmd)

        ok_first, output_first = package_unified.install_external_plugin_dependencies(temp_dir, [plugin_root])
        ok_second, output_second = package_unified.install_external_plugin_dependencies(temp_dir, [plugin_root])

        state_path = temp_dir / package_unified.get_common_plugin_dependency_relative_dir() / package_unified.get_external_plugin_dependency_state_filename()
        assert ok_first is True
        assert ok_second is True
        assert len(call_log) == 1
        assert state_path.exists()
        assert "installed" in output_first
        assert "already installed" in output_second
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_desktop_bundle_scripts_export_external_plugin_root():
    package_unified = _load_package_unified_module()
    workspace_tmp_root = ROOT_DIR / ".codex_test_runtime"
    workspace_tmp_root.mkdir(parents=True, exist_ok=True)
    temp_dir = workspace_tmp_root / f"bundle_scripts_{uuid4().hex[:8]}"
    temp_dir.mkdir(parents=True, exist_ok=True)

    try:
        bundle_dir = temp_dir / "bundle"
        bundle_dir.mkdir(parents=True, exist_ok=True)
        package_unified.write_desktop_bundle_scripts(
            bundle_dir=bundle_dir,
            binary_name="ultimate_backend_test",
            runtime_env={
                "BACKEND_RUNTIME_PROFILE": "full",
                "BACKEND_ENABLE_THIRD_PARTY": "true",
            },
        )

        bat_text = (bundle_dir / "start_backend.bat").read_text(encoding="utf-8")
        ps1_text = (bundle_dir / "start_backend.ps1").read_text(encoding="utf-8")
        sh_text = (bundle_dir / "start_backend.sh").read_text(encoding="utf-8")

        assert "ULTIMATE_PLUGIN_ROOTS" in bat_text
        assert "ULTIMATE_PLUGIN_ROOTS" in ps1_text
        assert "ULTIMATE_PLUGIN_ROOTS" in sh_text
        assert "ULTIMATE_USER_PLUGIN_ROOT" in bat_text
        assert "ULTIMATE_PLUGIN_DEP_ROOTS" in ps1_text
        assert "ULTIMATE_PLUGIN_DEP_MANIFEST" in sh_text
        assert "BACKEND_HOST=127.0.0.1" in bat_text
        assert "$env:BACKEND_HOST = \"127.0.0.1\"" in ps1_text
        assert "export BACKEND_HOST=\"127.0.0.1\"" in sh_text
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_desktop_bundle_scripts_lock_backend_to_loopback_when_frontend_proxy_exists():
    package_unified = _load_package_unified_module()
    workspace_tmp_root = ROOT_DIR / ".codex_test_runtime"
    workspace_tmp_root.mkdir(parents=True, exist_ok=True)
    temp_dir = workspace_tmp_root / f"bundle_proxy_mode_{uuid4().hex[:8]}"
    temp_dir.mkdir(parents=True, exist_ok=True)

    try:
        bundle_dir = temp_dir / "bundle"
        bundle_dir.mkdir(parents=True, exist_ok=True)
        package_unified.write_desktop_bundle_scripts(
            bundle_dir=bundle_dir,
            binary_name="ultimate_backend_test",
            frontend_binary_name="ultimate_frontend_test",
            runtime_env={
                "BACKEND_RUNTIME_PROFILE": "full",
                "BACKEND_ENABLE_THIRD_PARTY": "true",
            },
        )

        bat_text = (bundle_dir / "start_backend.bat").read_text(encoding="utf-8")
        ps1_text = (bundle_dir / "start_backend.ps1").read_text(encoding="utf-8")
        sh_text = (bundle_dir / "start_backend.sh").read_text(encoding="utf-8")

        assert "BACKEND_HOST=127.0.0.1" in bat_text
        assert "$env:BACKEND_HOST = \"127.0.0.1\"" in ps1_text
        assert "export BACKEND_HOST=\"127.0.0.1\"" in sh_text
        assert "BACKEND_SERVE_FRONTEND=false" in bat_text
        assert "$env:BACKEND_SERVE_FRONTEND = \"false\"" in ps1_text
        assert "export BACKEND_SERVE_FRONTEND=\"false\"" in sh_text
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_windows_control_center_launcher_is_the_packaged_entrypoint():
    package_unified = _load_package_unified_module()
    workspace_tmp_root = ROOT_DIR / ".codex_test_runtime"
    workspace_tmp_root.mkdir(parents=True, exist_ok=True)
    temp_dir = workspace_tmp_root / f"bundle_windows_launcher_{uuid4().hex[:8]}"
    temp_dir.mkdir(parents=True, exist_ok=True)

    try:
        bundle_dir = temp_dir / "bundle"
        bundle_dir.mkdir(parents=True, exist_ok=True)
        package_unified.write_desktop_bundle_scripts(
            bundle_dir=bundle_dir,
            binary_name="ultimate_backend_windows",
            frontend_binary_name="ultimate_frontend_windows",
            launcher_binary_name="ultimate_launcher_windows",
            runtime_env={
                "BACKEND_RUNTIME_PROFILE": "full",
                "BACKEND_ENABLE_THIRD_PARTY": "true",
            },
        )

        bat_text = (bundle_dir / "start_app.bat").read_text(encoding="utf-8")
        ps1_text = (bundle_dir / "start_app.ps1").read_text(encoding="utf-8")

        assert "ultimate_launcher_windows.exe" in bat_text
        assert "--mode packaged" in bat_text
        assert "ultimate_launcher_windows.exe" in ps1_text
        assert "--mode packaged" in ps1_text
        assert "Start-Process -FilePath (Join-Path $scriptDir 'start_backend.ps1')" not in ps1_text

        package_unified.tidy_desktop_bundle_launchers(bundle_dir)
        start_bat = (bundle_dir / "start_project.bat").read_text(encoding="utf-8")
        start_ps1 = (bundle_dir / "start_project.ps1").read_text(encoding="utf-8")
        assert "-WindowStyle Hidden" in start_bat
        assert "scripts\\start_app.ps1" in start_bat
        assert "-WindowStyle Hidden" in start_ps1
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_windows_launcher_pyinstaller_command_bundles_web_brand_and_taskbar_icons():
    package_unified = _load_package_unified_module()
    workspace_tmp_root = ROOT_DIR / ".codex_test_runtime"
    workspace_tmp_root.mkdir(parents=True, exist_ok=True)
    temp_dir = workspace_tmp_root / f"launcher_brand_asset_{uuid4().hex[:8]}"
    temp_dir.mkdir(parents=True, exist_ok=True)

    try:
        command = package_unified._write_launcher_pyinstaller_script(
            out_dir=temp_dir,
            target="windows",
            binary_name="ultimate_launcher_windows",
        )
        assert ["--hidden-import", "PIL.ImageTk"] == command[command.index("--hidden-import") : command.index("--hidden-import") + 2]
        assert "--collect-data" in command
        assert "PIL" in command
        assert command[command.index("--icon") + 1] == str(ROOT_DIR / "comic_frontend" / "public" / "ultimate_web.ico")
        add_data = [command[index + 1] for index, value in enumerate(command) if value == "--add-data"]
        assert all(value.endswith(";assets") for value in add_data)
        assert any(str(ROOT_DIR / "comic_frontend" / "public" / "vite.jpg") in value for value in add_data)
        assert any(str(ROOT_DIR / "comic_frontend" / "public" / "ultimate_web.ico") in value for value in add_data)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_desktop_frontend_without_windows_launcher_keeps_existing_start_app_script():
    package_unified = _load_package_unified_module()
    workspace_tmp_root = ROOT_DIR / ".codex_test_runtime"
    workspace_tmp_root.mkdir(parents=True, exist_ok=True)
    temp_dir = workspace_tmp_root / f"bundle_non_windows_launcher_{uuid4().hex[:8]}"
    temp_dir.mkdir(parents=True, exist_ok=True)

    try:
        bundle_dir = temp_dir / "bundle"
        bundle_dir.mkdir(parents=True, exist_ok=True)
        package_unified.write_desktop_bundle_scripts(
            bundle_dir=bundle_dir,
            binary_name="ultimate_backend_linux",
            frontend_binary_name="ultimate_frontend_linux",
            runtime_env={"BACKEND_RUNTIME_PROFILE": "full"},
        )

        ps1_text = (bundle_dir / "start_app.ps1").read_text(encoding="utf-8")
        assert "ultimate_frontend_linux" not in ps1_text
        assert "start_backend.ps1" in ps1_text
        assert "$appPort = 5173" in ps1_text
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_prepare_desktop_release_bundle_copies_ffmpeg_runtime_tool_and_launchers_add_path(monkeypatch):
    package_unified = _load_package_unified_module()
    workspace_tmp_root = ROOT_DIR / ".codex_test_runtime"
    workspace_tmp_root.mkdir(parents=True, exist_ok=True)
    temp_dir = workspace_tmp_root / f"bundle_ffmpeg_{uuid4().hex[:8]}"
    temp_dir.mkdir(parents=True, exist_ok=True)

    try:
        staged_target_dir = temp_dir / "staged"
        (staged_target_dir / "comic_backend").mkdir(parents=True, exist_ok=True)
        (staged_target_dir / "comic_frontend_dist").mkdir(parents=True, exist_ok=True)
        (staged_target_dir / "runtime.env").write_text("BACKEND_RUNTIME_PROFILE=full\n", encoding="utf-8")

        fake_binary_name = "ffmpeg.exe" if os.name == "nt" else "ffmpeg"
        fake_ffmpeg = temp_dir / fake_binary_name
        fake_ffmpeg.write_bytes(b"fake-ffmpeg-runtime")
        monkeypatch.setenv("FFMPEG_PATH", str(fake_ffmpeg))

        bundle_dir = package_unified.prepare_desktop_release_bundle(
            target="windows" if os.name == "nt" else "linux",
            target_out_dir=temp_dir / "out",
            staged_target_dir=staged_target_dir,
            binary_name="ultimate_backend_test",
            runtime_env={
                "BACKEND_RUNTIME_PROFILE": "full",
                "BACKEND_ENABLE_THIRD_PARTY": "true",
            },
        )

        copied_ffmpeg = bundle_dir / "tools" / "ffmpeg" / fake_binary_name
        assert copied_ffmpeg.exists()

        bat_text = (bundle_dir / "scripts" / "start_backend.bat").read_text(encoding="utf-8")
        ps1_text = (bundle_dir / "scripts" / "start_backend.ps1").read_text(encoding="utf-8")
        sh_text = (bundle_dir / "scripts" / "start_backend.sh").read_text(encoding="utf-8")
        readme_text = (bundle_dir / "README.md").read_text(encoding="utf-8")

        assert "tools\\ffmpeg" in bat_text
        assert "tools/ffmpeg" in ps1_text
        assert "tools/ffmpeg" in sh_text
        assert "tools/ffmpeg/" in readme_text
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_copy_ffmpeg_runtime_tools_skips_android_targets():
    package_unified = _load_package_unified_module()
    workspace_tmp_root = ROOT_DIR / ".codex_test_runtime"
    workspace_tmp_root.mkdir(parents=True, exist_ok=True)
    temp_dir = workspace_tmp_root / f"android_ffmpeg_skip_{uuid4().hex[:8]}"
    temp_dir.mkdir(parents=True, exist_ok=True)

    try:
        result = package_unified.copy_ffmpeg_runtime_tools("android", temp_dir)
        assert result is None
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_copy_ffmpeg_runtime_tools_auto_provisions_windows_when_missing(monkeypatch):
    package_unified = _load_package_unified_module()
    workspace_tmp_root = ROOT_DIR / ".codex_test_runtime"
    workspace_tmp_root.mkdir(parents=True, exist_ok=True)
    temp_dir = workspace_tmp_root / f"windows_ffmpeg_auto_{uuid4().hex[:8]}"
    temp_dir.mkdir(parents=True, exist_ok=True)

    try:
        fake_runtime_root = temp_dir / "fake_runtime"
        fake_runtime_root.mkdir(parents=True, exist_ok=True)
        fake_ffmpeg = fake_runtime_root / "ffmpeg.exe"
        fake_ffmpeg.write_bytes(b"auto-provisioned-ffmpeg")
        fake_ffprobe = fake_runtime_root / "ffprobe.exe"
        fake_ffprobe.write_bytes(b"auto-provisioned-ffprobe")

        monkeypatch.setattr(package_unified, "discover_ffmpeg_runtime_tools", lambda target: {})
        monkeypatch.setattr(
            package_unified,
            "provision_windows_ffmpeg_runtime_tools",
            lambda: {
                "ffmpeg.exe": fake_ffmpeg,
                "ffprobe.exe": fake_ffprobe,
            },
        )

        result = package_unified.copy_ffmpeg_runtime_tools("windows", temp_dir)

        assert result is not None
        assert (result / "ffmpeg.exe").exists()
        assert (result / "ffprobe.exe").exists()
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

