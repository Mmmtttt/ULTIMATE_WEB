from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

import pytest

from tests.shared.test_constants import REPO_ROOT
from tests.tools.prepare_test_env import prepare_profile


def _reset_backend_modules() -> None:
    module_names = [
        "app",
        "api",
        "api.v1",
        "api.v1.runtime_guard",
        "api.v1.comic",
        "api.v1.video",
        "core.constants",
        "core.runtime_profile",
        "application.video_app_service",
    ]
    for name in module_names:
        sys.modules.pop(name, None)


@pytest.fixture(scope="module")
def third_party_client():
    prepared = prepare_profile("integration_third_party", clean=True)

    env_overrides = {
        "SERVER_CONFIG_PATH": prepared["server_config_path"],
        "THIRD_PARTY_CONFIG_PATH": prepared["third_party_config_path"],
        "BACKEND_ENABLE_THIRD_PARTY": "1",
        "BACKEND_RUNTIME_PROFILE": "full",
        "ULTIMATE_ENABLE_THIRD_PARTY": "1",
        "ULTIMATE_RUNTIME_PROFILE": "full",
    }
    original_env = {key: os.environ.get(key) for key in env_overrides}
    os.environ.update(env_overrides)

    backend_root = Path(REPO_ROOT) / "comic_backend"
    inserted_backend_path = False
    if str(backend_root) not in sys.path:
        sys.path.insert(0, str(backend_root))
        inserted_backend_path = True

    _reset_backend_modules()
    backend_app = importlib.import_module("app")
    backend_app.app.config.update(TESTING=True)

    import werkzeug  # Flask<3 with Werkzeug>=3 compatibility for test_client.
    if not hasattr(werkzeug, "__version__"):
        werkzeug.__version__ = "3"

    client = backend_app.app.test_client()
    context = {
        "client": client,
        "runtime_root": Path(prepared["runtime_root"]),
        "data_dir": Path(prepared["data_dir"]),
        "meta_dir": Path(prepared["data_dir"]) / "meta_data",
        "third_party_config_path": Path(prepared["third_party_config_path"]),
        "comic_api": importlib.import_module("api.v1.comic"),
        "video_api": importlib.import_module("api.v1.video"),
        "list_api": importlib.import_module("api.v1.list"),
        "author_api": importlib.import_module("api.v1.author"),
        "actor_api": importlib.import_module("api.v1.actor"),
        "list_service_module": importlib.import_module("application.list_app_service"),
        "author_service_module": importlib.import_module("application.author_app_service"),
        "video_service_module": importlib.import_module("application.video_app_service"),
    }

    try:
        yield context
    finally:
        if inserted_backend_path:
            try:
                sys.path.remove(str(backend_root))
            except ValueError:
                pass

        for key, value in original_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
