from __future__ import annotations

import importlib.util
import shutil
import sys
from pathlib import Path
from uuid import uuid4


ROOT_DIR = Path(__file__).resolve().parents[1]


def _load_build_unified_module():
    module_path = ROOT_DIR / "scripts" / "build_unified.py"
    scripts_dir = str(module_path.parent)
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    spec = importlib.util.spec_from_file_location("build_unified_for_network_binding_test", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_desktop_build_workspace_launchers_bind_backend_to_loopback():
    build_unified = _load_build_unified_module()
    workspace_tmp_root = ROOT_DIR / ".codex_test_runtime"
    workspace_tmp_root.mkdir(parents=True, exist_ok=True)
    temp_dir = workspace_tmp_root / f"network_binding_{uuid4().hex[:8]}"
    temp_dir.mkdir(parents=True, exist_ok=True)

    try:
        target = {
            "id": "windows",
            "runtime_profile": "full",
            "third_party_enabled": True,
        }
        build_unified.write_runtime_env(target, temp_dir, "1.2.3")
        build_unified.write_launchers(target, temp_dir)

        runtime_env = (temp_dir / "runtime.env").read_text(encoding="utf-8")
        bat_text = (temp_dir / "start_backend.bat").read_text(encoding="utf-8")
        sh_text = (temp_dir / "start_backend.sh").read_text(encoding="utf-8")

        assert "BACKEND_HOST=127.0.0.1" in runtime_env
        assert "BACKEND_HOST=127.0.0.1" in bat_text
        assert "export BACKEND_HOST=\"127.0.0.1\"" in sh_text
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_android_build_workspace_does_not_force_backend_loopback():
    build_unified = _load_build_unified_module()
    workspace_tmp_root = ROOT_DIR / ".codex_test_runtime"
    workspace_tmp_root.mkdir(parents=True, exist_ok=True)
    temp_dir = workspace_tmp_root / f"android_network_binding_{uuid4().hex[:8]}"
    temp_dir.mkdir(parents=True, exist_ok=True)

    try:
        target = {
            "id": "android",
            "runtime_profile": "mobile_core",
            "third_party_enabled": False,
        }
        build_unified.write_runtime_env(target, temp_dir, "1.2.3")
        build_unified.write_launchers(target, temp_dir)

        runtime_env = (temp_dir / "runtime.env").read_text(encoding="utf-8")
        bat_text = (temp_dir / "start_backend.bat").read_text(encoding="utf-8")
        sh_text = (temp_dir / "start_backend.sh").read_text(encoding="utf-8")

        assert "BACKEND_HOST=127.0.0.1" not in runtime_env
        assert "BACKEND_HOST=127.0.0.1" not in bat_text
        assert "export BACKEND_HOST=\"127.0.0.1\"" not in sh_text
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_docker_compose_publishes_backend_to_host_loopback_by_default():
    compose_text = (ROOT_DIR / "docker-compose.yml").read_text(encoding="utf-8")

    assert '"127.0.0.1:5000:5000"' in compose_text
    assert '- "5000:5000"' not in compose_text
