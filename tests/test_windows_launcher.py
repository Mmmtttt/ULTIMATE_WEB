import importlib.util
import json
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]


def _load_launcher():
    path = ROOT_DIR / "scripts" / "windows_launcher.py"
    spec = importlib.util.spec_from_file_location("windows_launcher_for_test", path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_launcher_reads_frontend_url_from_server_config(tmp_path):
    launcher = _load_launcher()
    (tmp_path / "server_config.json").write_text(
        json.dumps({"frontend": {"host": "0.0.0.0", "port": 6123, "ssl_enabled": False}}),
        encoding="utf-8",
    )

    assert launcher._frontend_url(tmp_path) == "http://127.0.0.1:6123/"


def test_dev_service_specs_keep_backend_and_frontend_as_children(tmp_path):
    launcher = _load_launcher()
    specs = launcher.build_service_specs(tmp_path, "dev")

    assert [spec.key for spec in specs] == ["backend", "frontend"]
    assert specs[0].command[-2:] == ["-u", "app.py"]
    assert specs[0].cwd == tmp_path / "comic_backend"
    assert specs[1].command == ["cmd.exe", "/d", "/s", "/c", "npm.cmd run dev"]
    assert specs[1].cwd == tmp_path / "comic_frontend"


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
