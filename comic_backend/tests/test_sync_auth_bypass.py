import importlib.util
import sys
from pathlib import Path

import werkzeug

if not hasattr(werkzeug, "__version__"):
    werkzeug.__version__ = "test"


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def _load_backend_app():
    module_path = BACKEND_ROOT / "app.py"
    spec = importlib.util.spec_from_file_location("ultimate_backend_app_for_sync_auth_test", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_sync_token_endpoint_reaches_token_verifier_without_browser_session(monkeypatch, tmp_path):
    backend_app = _load_backend_app()
    monkeypatch.setattr(backend_app, "FRONTEND_ENABLED", False)

    calls = {"verify_token": 0}

    def fake_verify_token(token):
        calls["verify_token"] += 1
        assert token == "paired-token"
        return {"peer_id": "peer-1", "status": "active"}

    monkeypatch.setattr(backend_app, "ensure_storage_layout", lambda mode=None: None)
    monkeypatch.setattr(backend_app, "init_backup_system", lambda: None)
    monkeypatch.setattr(backend_app, "ensure_rar_backend_configured", lambda: None)
    monkeypatch.setattr(backend_app, "probe_7z_encryption_capability", lambda: None)

    app = backend_app.create_app(space_mode=backend_app.SPACE_MODE_NORMAL, require_auth=True)
    import api.v1.sync as sync_api

    monkeypatch.setattr(sync_api.directional_service, "verify_token", fake_verify_token)
    monkeypatch.setattr(sync_api.directional_service, "inventory", lambda: {"datasets": {}})

    client = app.test_client()
    response = client.get(
        "/api/v1/sync/directional/inventory",
        headers={"X-Sync-Token": "paired-token"},
    )

    assert response.status_code == 200
    assert calls["verify_token"] == 1


def test_normal_backend_still_rejects_non_sync_request_without_session(monkeypatch):
    backend_app = _load_backend_app()
    monkeypatch.setattr(backend_app, "FRONTEND_ENABLED", False)
    monkeypatch.setattr(backend_app, "ensure_storage_layout", lambda mode=None: None)
    monkeypatch.setattr(backend_app, "init_backup_system", lambda: None)
    monkeypatch.setattr(backend_app, "ensure_rar_backend_configured", lambda: None)
    monkeypatch.setattr(backend_app, "probe_7z_encryption_capability", lambda: None)

    app = backend_app.create_app(space_mode=backend_app.SPACE_MODE_NORMAL, require_auth=True)
    response = app.test_client().get("/api/v1/comic/list")

    assert response.status_code == 401
