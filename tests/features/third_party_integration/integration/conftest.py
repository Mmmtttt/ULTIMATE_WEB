from __future__ import annotations

import importlib
import importlib.util
import json
import os
import sys
from pathlib import Path
from types import ModuleType

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
        "api.v1.teledrive",
        "api.v1.list",
        "api.v1.author",
        "api.v1.actor",
        "api.v1.organize",
        "api.v1.recommendation",
        "api.v1.config",
        "api.v1.tag",
        "api.v1.feed",
        "api.v1.sync",
        "api.v1.ui_state",
        "application",
        "application.base",
        "application.base.content_app_service",
        "application.config_app_service",
        "application.persisted_content_metadata",
        "application.tag_content_type_guard",
        "application.local_comic_import_service",
        "application.local_video_thumbnail_service",
        "application.softref_comic_reader",
        "application.softref_reader_protocol",
        "application.sync_app_service",
        "application.sync_directional_service",
        "application.ui_state_app_service",
        "application.random_feed_service",
        "application.tag_app_service",
        "core.constants",
        "core.runtime_profile",
        "core.host_platform_fallback",
        "core.utils",
        "domain",
        "domain.tag",
        "domain.tag.entity",
        "application.database_organize_service",
        "application.comic_app_service",
        "application.list_app_service",
        "application.author_app_service",
        "application.actor_app_service",
        "application.recommendation_app_service",
        "application.video_app_service",
        "application.video_runtime_support",
        "application.teledrive_app_service",
        "protocol",
        "protocol.gateway",
        "protocol.provider_manager",
        "protocol.registry",
        "protocol.runtime_config",
        "protocol.platform_service",
        "protocol.compatibility",
        "protocol.host_service",
        "protocol.credential_guard",
        "protocol.config_service",
        "protocol.adapter_api",
        "protocol.presentation",
        "third_party",
        "third_party.external_api",
        "third_party.platform_service",
        "infrastructure",
        "infrastructure.common",
        "infrastructure.common.result",
        "infrastructure.logger",
        "infrastructure.persistence",
        "infrastructure.persistence.repositories",
        "infrastructure.persistence.repositories.tag_repository_impl",
        "infrastructure.recommendation_cache_manager",
        "utils",
        "utils.file_parser",
        "utils.image_handler",
    ]
    for name in module_names:
        sys.modules.pop(name, None)

    for name in list(sys.modules):
        if (
            name == "protocol"
            or name.startswith("protocol.")
            or name == "third_party"
            or name.startswith("third_party.")
            or name == "application"
            or name.startswith("application.")
            or name == "infrastructure"
            or name.startswith("infrastructure.")
            or name == "domain"
            or name.startswith("domain.")
            or name == "core"
            or name.startswith("core.")
        ):
            sys.modules.pop(name, None)


def _ensure_flask_cors_available() -> None:
    try:
        importlib.import_module("flask_cors")
        return
    except Exception:
        pass

    fallback = ModuleType("flask_cors")

    class _NoOpCORS:
        def __init__(self, app=None, *args, **kwargs):
            if app is not None:
                self.init_app(app, *args, **kwargs)

        def init_app(self, app, *args, **kwargs):
            return app

    fallback.CORS = _NoOpCORS
    sys.modules["flask_cors"] = fallback


def _ensure_backend_utils_package(backend_root: Path) -> None:
    utils_root = backend_root / "utils"
    existing_utils = sys.modules.get("utils")
    existing_utils_file = str(getattr(existing_utils, "__file__", "") or "")
    if existing_utils_file.startswith(str(utils_root)):
        return

    spec = importlib.util.spec_from_file_location(
        "utils",
        utils_root / "__init__.py",
        submodule_search_locations=[str(utils_root)],
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"failed to load backend utils package from {utils_root}")

    module = importlib.util.module_from_spec(spec)
    sys.modules["utils"] = module
    spec.loader.exec_module(module)


@pytest.fixture(scope="module")
def third_party_client():
    prepared = prepare_profile("integration_third_party", clean=True)
    third_party_config_path = Path(prepared["third_party_config_path"])
    try:
        payload = json.loads(third_party_config_path.read_text(encoding="utf-8"))
    except Exception:
        payload = {}
    adapters = payload.setdefault("adapters", {})
    adapters["jmcomic"] = {
        **dict(adapters.get("jmcomic") or {}),
        "enabled": True,
        "username": "test-jm-user",
        "password": "test-jm-pass",
    }
    adapters["picacomic"] = {
        **dict(adapters.get("picacomic") or {}),
        "enabled": True,
        "account": "test-pk-account",
        "password": "test-pk-pass",
    }
    adapters["javdb"] = {
        **dict(adapters.get("javdb") or {}),
        "enabled": True,
        "cookies": {
            "_jdb_session": "test-jdb-session",
            "over18": "1",
            "locale": "zh",
            "theme": "auto",
            "list_mode": "h",
        },
    }
    third_party_config_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

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
    fake_deps_root = Path(REPO_ROOT) / "tests" / "shared" / "fake_deps"
    inserted_backend_path = False
    inserted_fake_deps_path = False
    if str(backend_root) not in sys.path:
        sys.path.insert(0, str(backend_root))
        inserted_backend_path = True
    if str(fake_deps_root) not in sys.path:
        sys.path.insert(0, str(fake_deps_root))
        inserted_fake_deps_path = True

    _ensure_flask_cors_available()
    _reset_backend_modules()
    _ensure_backend_utils_package(backend_root)
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
        if inserted_fake_deps_path:
            try:
                sys.path.remove(str(fake_deps_root))
            except ValueError:
                pass
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
