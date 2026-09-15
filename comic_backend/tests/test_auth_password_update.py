import json
import sys
from pathlib import Path
from urllib.parse import quote

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


def test_runtime_space_apps_use_isolated_session_cookies(monkeypatch):
    import app as backend_app

    monkeypatch.setattr(backend_app, "ensure_storage_layout", lambda _space_mode: None)

    private_app = backend_app.create_app(
        space_mode=SPACE_MODE_PRIVATE,
        require_auth=False,
    )
    normal_app = backend_app.create_app(
        space_mode=SPACE_MODE_NORMAL,
        require_auth=True,
    )

    assert private_app.config["SESSION_COOKIE_NAME"] == "ultimate_web_private_session"
    assert normal_app.config["SESSION_COOKIE_NAME"] == "ultimate_web_normal_session"
    assert private_app.config["SESSION_COOKIE_NAME"] != normal_app.config["SESSION_COOKIE_NAME"]


def test_normal_space_allows_cors_preflight_without_session(monkeypatch):
    import app as backend_app

    monkeypatch.setattr(backend_app, "ensure_storage_layout", lambda _space_mode: None)
    normal_app = backend_app.create_app(
        space_mode=SPACE_MODE_NORMAL,
        require_auth=True,
    )

    response = normal_app.test_client().options(
        "/api/v1/ui-state",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert response.status_code != 401


def test_normal_auth_token_authorizes_normal_space_without_cookie(tmp_path, monkeypatch):
    import app as backend_app

    config_path = tmp_path / "server_config.json"
    config_path.write_text(
        json.dumps({"auth": {"enabled": True, "password": "correct"}}),
        encoding="utf-8",
    )
    monkeypatch.setattr(auth_api, "SERVER_CONFIG_PATH", str(config_path))
    monkeypatch.setattr(
        auth_api,
        "_load_server_config",
        lambda: json.loads(config_path.read_text(encoding="utf-8")),
    )
    monkeypatch.setattr(backend_app, "ensure_storage_layout", lambda _space_mode: None)

    private_app = backend_app.create_app(
        space_mode=SPACE_MODE_PRIVATE,
        require_auth=False,
    )
    normal_app = backend_app.create_app(
        space_mode=SPACE_MODE_NORMAL,
        require_auth=True,
    )

    login_response = private_app.test_client().post(
        "/api/v1/auth/login",
        json={"password": "correct"},
    )
    token = login_response.get_json()["data"]["normal_auth_token"]

    status_response = normal_app.test_client().get(
        "/api/v1/auth/status",
        headers={auth_api.NORMAL_AUTH_TOKEN_HEADER: token},
    )

    assert login_response.status_code == 200
    assert token
    assert status_response.status_code == 200
    assert status_response.get_json()["data"]["authenticated"] is True

    query_status_response = normal_app.test_client().get(
        f"/api/v1/auth/status?normal_auth_token={quote(token, safe='')}"
    )

    assert query_status_response.status_code == 200
    assert query_status_response.get_json()["data"]["authenticated"] is True

    unauthenticated_cover_response = normal_app.test_client().get(
        "/static/cover/missing.jpg"
    )
    authenticated_cover_response = normal_app.test_client().get(
        f"/static/cover/missing.jpg?normal_auth_token={quote(token, safe='')}"
    )

    assert unauthenticated_cover_response.status_code == 401
    assert authenticated_cover_response.status_code != 401


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
