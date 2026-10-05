from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]


def test_backend_proxy_mode_does_not_serve_frontend_routes(tmp_path):
    server_config_path = tmp_path / "server_config.json"
    server_config_path.write_text(
        json.dumps(
            {
                "backend": {"ssl_enabled": False},
                "frontend": {},
                "storage": {"data_dir": str(tmp_path / "data")},
                "auth": {"enabled": False},
            }
        ),
        encoding="utf-8",
    )

    script = f"""
import importlib.util
import sys
import werkzeug
from pathlib import Path

root = Path({str(ROOT_DIR)!r})
if str(root / "comic_backend") not in sys.path:
    sys.path.insert(0, str(root / "comic_backend"))
if not hasattr(werkzeug, "__version__"):
    werkzeug.__version__ = "test"

spec = importlib.util.spec_from_file_location("backend_app_proxy_mode_test", root / "comic_backend" / "app.py")
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)

app = module.create_app()
client = app.test_client()
root_resp = client.get("/")
route_resp = client.get("/library")
normal_app = module.create_app(space_mode=module.SPACE_MODE_NORMAL, require_auth=True)
normal_client = normal_app.test_client()
static_resp = normal_client.get("/static/cover/secret.jpg")

assert module.FRONTEND_ENABLED is False
assert root_resp.status_code == 200
assert b"Comic Backend API" in root_resp.data
assert route_resp.status_code == 404
assert static_resp.status_code == 401
"""

    env = os.environ.copy()
    env.update(
        {
            "SERVER_CONFIG_PATH": str(server_config_path),
            "BACKEND_SERVE_FRONTEND": "false",
            "BACKEND_SSL_ENABLED": "0",
            "BACKEND_ENABLE_THIRD_PARTY": "0",
        }
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=str(ROOT_DIR),
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
