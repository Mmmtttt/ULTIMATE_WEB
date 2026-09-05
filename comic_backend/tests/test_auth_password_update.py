import json
import sys
from pathlib import Path

import werkzeug
from flask import Flask

if not hasattr(werkzeug, "__version__"):
    werkzeug.__version__ = "test"


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import api.v1.auth as auth_api
from core.storage_layout import SPACE_MODE_NORMAL, SPACE_MODE_PRIVATE


def _make_app(space_mode: str) -> Flask:
    app = Flask(__name__)
    app.secret_key = "test-secret"
    app.config["SPACE_MODE"] = space_mode
    app.register_blueprint(auth_api.auth_bp, url_prefix="/api/v1/auth")
    return app


def test_update_project_password_saves_plaintext_in_normal_space(tmp_path, monkeypatch):
    config_path = tmp_path / "server_config.json"
    config_path.write_text(json.dumps({"auth": {"enabled": False, "password": ""}}), encoding="utf-8")

    def load_config():
        return json.loads(config_path.read_text(encoding="utf-8"))

    monkeypatch.setattr(auth_api, "SERVER_CONFIG_PATH", str(config_path))
    monkeypatch.setattr(auth_api, "_load_server_config", load_config)

    response = _make_app(SPACE_MODE_NORMAL).test_client().put(
        "/api/v1/auth/password",
        json={"password": "new-pass"},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["data"]["enabled"] is True
    assert payload["data"]["authenticated"] is True

    saved = json.loads(config_path.read_text(encoding="utf-8"))
    assert saved["auth"]["enabled"] is True
    assert saved["auth"]["password"] == "new-pass"


def test_update_project_password_is_rejected_in_private_space(tmp_path, monkeypatch):
    config_path = tmp_path / "server_config.json"
    config_path.write_text(json.dumps({"auth": {"enabled": False, "password": ""}}), encoding="utf-8")
    monkeypatch.setattr(auth_api, "SERVER_CONFIG_PATH", str(config_path))
    monkeypatch.setattr(auth_api, "_load_server_config", lambda: json.loads(config_path.read_text(encoding="utf-8")))

    response = _make_app(SPACE_MODE_PRIVATE).test_client().put(
        "/api/v1/auth/password",
        json={"password": "new-pass"},
    )

    assert response.status_code == 403
    saved = json.loads(config_path.read_text(encoding="utf-8"))
    assert saved["auth"]["enabled"] is False
    assert saved["auth"]["password"] == ""
