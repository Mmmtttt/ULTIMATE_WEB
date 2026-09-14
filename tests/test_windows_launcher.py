import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest


ROOT_DIR = Path(__file__).resolve().parents[1]


def _load_launcher():
    path = ROOT_DIR / "scripts" / "windows_launcher.py"
    spec = importlib.util.spec_from_file_location("windows_launcher_for_test", path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_launcher_reads_frontend_url_from_active_server_config(tmp_path, monkeypatch):
    launcher = _load_launcher()
    config_path = tmp_path / "server_config.json"
    config_path.write_text(
        json.dumps({"frontend": {"host": "0.0.0.0", "port": 6123, "ssl_enabled": False}}),
        encoding="utf-8",
    )
    monkeypatch.setenv("SERVER_CONFIG_PATH", str(config_path))

    assert launcher._frontend_url(tmp_path) == "http://127.0.0.1:6123/"


def test_launcher_icon_path_uses_project_asset(tmp_path):
    launcher = _load_launcher()
    icon_path = tmp_path / "comic_frontend" / "public" / "ultimate_web.ico"
    icon_path.parent.mkdir(parents=True)
    icon_path.write_bytes(b"icon")

    assert launcher._launcher_icon_path(tmp_path) == icon_path


def test_health_checks_are_slow_and_health_access_logs_are_filtered():
    launcher = _load_launcher()

    assert launcher.HEALTH_CHECK_INTERVAL_SECONDS == 3
    assert launcher._is_health_log_line('127.0.0.1 - - "GET /health HTTP/1.1" 200 -')
    assert launcher._is_health_log_line('127.0.0.1 - - "HEAD /health HTTP/1.1" 200 -')
    assert not launcher._is_health_log_line('127.0.0.1 - - "GET /api/v1/comics HTTP/1.1" 200 -')


def test_dev_service_specs_keep_backend_and_frontend_as_children(tmp_path):
    launcher = _load_launcher()
    specs = launcher.build_service_specs(tmp_path, "dev")

    assert [spec.key for spec in specs] == ["backend", "frontend"]
    assert specs[0].command[-2:] == ["-u", "app.py"]
    assert specs[0].cwd == tmp_path / "comic_backend"
    assert specs[1].command == ["cmd.exe", "/d", "/s", "/c", "npm.cmd run dev"]
    assert specs[1].cwd == tmp_path / "comic_frontend"
    assert specs[0].env["BACKEND_HOST"] == "127.0.0.1"


def test_packaged_service_specs_use_release_binaries(tmp_path):
    launcher = _load_launcher()
    specs = launcher.build_service_specs(
        tmp_path,
        "packaged",
        backend_exe="backend.exe",
        frontend_exe="frontend.exe",
    )

    assert specs[0].command == [str(tmp_path / "bin" / "backend.exe")]
    assert specs[1].command == [str(tmp_path / "bin" / "frontend.exe")]
    assert specs[0].env["BACKEND_HOST"] == "127.0.0.1"
    assert specs[0].env["BACKEND_SERVE_FRONTEND"] == "false"


def test_space_ports_distinguish_single_and_dual_backend_modes():
    launcher = _load_launcher()

    assert launcher._space_ports({"backend": {"port": 5100}, "auth": {"enabled": False}}) == {
        "private": None,
        "normal": 5100,
    }
    assert launcher._space_ports({
        "backend": {"port": 5100},
        "auth": {"enabled": True, "password": "secret", "private_port": 5101, "normal_port": 5102},
    }) == {"private": 5101, "normal": 5102}


def test_private_data_path_matches_backend_relative_path_rules(tmp_path):
    launcher = _load_launcher()
    config = {
        "storage": {"data_dir": str(tmp_path / "UltimateData")},
        "auth": {"private_data_dir": "../UltimateData_private"},
    }

    assert launcher._resolve_private_data_path(tmp_path, config) == tmp_path / "UltimateData_private"


def test_data_migration_skips_symlinks_and_rejects_nested_targets(tmp_path):
    launcher = _load_launcher()
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    (source / "real.txt").write_text("real", encoding="utf-8")
    try:
        os.symlink(source / "real.txt", source / "link.txt")
    except (OSError, NotImplementedError):
        pass

    files, size = launcher._copy_tree_without_symlinks(source, target)
    assert files == 1
    assert size == 4
    assert (target / "real.txt").read_text(encoding="utf-8") == "real"
    assert not (target / "link.txt").exists()

    with pytest.raises(ValueError):
        launcher._copy_tree_without_symlinks(source, source / "nested")
