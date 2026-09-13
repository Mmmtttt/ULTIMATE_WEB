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


_FAKE_PROVIDER_SOURCE = r'''
from __future__ import annotations

from http.cookies import SimpleCookie

from protocol.base import ProtocolProvider


def _parse_cookie_string(raw):
    parsed = {}
    cookie = SimpleCookie()
    try:
        cookie.load(str(raw or ""))
    except Exception:
        return parsed
    for key, morsel in cookie.items():
        parsed[str(key)] = str(morsel.value)
    return parsed


class FakeProtocolProvider(ProtocolProvider):
    def normalize_config(self, payload):
        config = dict(payload or {})
        cookie_string = str(config.pop("cookie_string", "") or "").strip()
        if cookie_string:
            cookies = dict(config.get("cookies") or {})
            cookies.update(_parse_cookie_string(cookie_string))
            config["cookies"] = cookies
        return config

    def serialize_public_config(self, config):
        payload = dict(config or {})
        cookies = dict(payload.get("cookies") or {})
        if cookies:
            payload["cookie_string"] = "; ".join(f"{key}={value}" for key, value in cookies.items())
        return payload

    def execute(self, capability, params, context, config):
        capability = str(capability or "")
        params = dict(params or {})
        plugin_id = str(((self.manifest.get("plugin") or {}).get("id")) or "")
        config_key = str(((self.manifest.get("plugin") or {}).get("config_key")) or "")

        if capability == "catalog.search":
            if plugin_id.startswith("video."):
                return {
                    "videos": [
                        {
                            "id": f"{config_key}-video-1",
                            "video_id": f"{config_key}-video-1",
                            "title": f"{config_key} title",
                            "cover_url": f"https://example.test/{config_key}/cover.jpg",
                        }
                    ],
                    "page": int(params.get("page") or 1),
                    "total_pages": 1,
                    "has_next": False,
                }
            return {
                "albums": [
                    {
                        "album_id": f"{config_key}-album-1",
                        "title": f"{config_key} title",
                        "author": "Fake Author",
                        "pages": 3,
                        "tags": [],
                    }
                ],
                "page": int(params.get("page") or 1),
                "total_pages": 1,
                "has_next": False,
            }

        if capability == "catalog.detail":
            if plugin_id.startswith("video."):
                video_id = str(params.get("video_id") or params.get("code") or "video-1")
                return {"id": video_id, "video_id": video_id, "code": video_id, "title": f"{config_key} detail"}
            album_id = str(params.get("album_id") or "album-1")
            return {"albums": [{"album_id": album_id, "title": f"{config_key} detail", "pages": 3, "tags": []}]}

        if capability == "collection.favorites_basic":
            return {"albums": [{"album_id": "fav-1", "title": "Favorite", "pages": 1, "tags": []}]}

        if capability == "collection.list":
            return {"lists": [{"id": "favorites", "name": "Favorites"}]}

        if capability == "collection.detail":
            return {"items": [{"id": "list-1", "title": "List Item"}]}

        if capability == "asset.bundle.fetch":
            return {"success": True, "detail": {"local_pages": 3}}

        if capability == "asset.cover.fetch":
            return {"success": True, "detail": {"ok": True}}

        if capability == "asset.preview.resolve":
            album_id = str(params.get("album_id") or "album-1")
            return [f"https://example.test/{config_key}/{album_id}/{page}.jpg" for page in params.get("preview_pages") or []]

        if capability == "storage.comic_dir.resolve":
            return str(params.get("album_id") or "")

        if capability == "person.search":
            return {"actors": [{"actor_id": "actor-1", "name": str(params.get("actor_name") or "Actor")}]}

        if capability == "person.works":
            return {"works": [{"video_id": "work-1", "title": "Work"}], "page": int(params.get("page") or 1), "has_next": False}

        if capability == "health.query.status":
            cookies = dict(config.get("cookies") or {})
            return {
                "configured": bool(config.get("enabled", True)),
                "has_session_cookie": bool(cookies.get("_session")),
            }

        return {}
'''


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _fake_manifest(
    *,
    plugin_id: str,
    name: str,
    config_key: str,
    media_type: str,
    host_prefix: str,
    required_fields: list[str],
    order: int,
    capabilities: list[dict],
    fields: list[dict],
    storage_field: str = "",
    storage_relative_dir: str = "",
    cover_fit: str = "cover",
    helpers: dict | None = None,
    actions: list[dict] | None = None,
) -> dict:
    manifest = {
        "protocol_version": "2.0",
        "plugin": {
            "id": plugin_id,
            "name": name,
            "version": "1.0.0-test",
            "entrypoint": "./fake_provider.py:FakeProtocolProvider",
            "config_key": config_key,
        },
        "media_types": [media_type],
        "identity": {
            "content_type": media_type,
            "host_id_prefix": host_prefix,
            "platform_label": host_prefix,
            "aliases": [config_key],
        },
        "presentation": {
            "media_card": {
                "cover": {
                    "aspect_ratio": "16 / 9" if media_type == "video" else "2 / 3",
                    "fit": cover_fit,
                    "path_mode": "local_static",
                },
                "badge": {"show_platform_label": True, "label": host_prefix},
            }
        },
        "capabilities": capabilities,
        "configuration": {
            "order": order,
            "label": name,
            "credential": {
                "enabled_field": "enabled",
                "required_fields": required_fields,
                "unconfigured_message": f"{host_prefix} 测试平台配置不完整，不能使用该平台查询。",
                "disabled_message": f"{host_prefix} 测试平台未启用，不能使用该平台查询。",
            },
            "sections": [{"id": "basic", "label": "基础配置", "fields": fields}],
            "actions": list(actions or []),
        },
        "runtime": {"python_paths": ["."]},
    }
    if helpers:
        manifest["helpers"] = dict(helpers)
    if storage_field and storage_relative_dir:
        manifest["storage"] = {
            "data_dir_bindings": [
                {"config_field": storage_field, "relative_dir": storage_relative_dir}
            ],
            "comic_dir": {"template": "{album_id}"},
        }
    capability_keys = {str(item.get("key") or "").strip() for item in capabilities}
    if "collection.favorites_basic" in capability_keys:
        manifest["collections"] = {
            "list_mode": "virtual_only",
            "virtual_lists": [
                {
                    "id": "favorites",
                    "name": "我的收藏",
                    "description": "fake protocol favorites",
                    "capability": "collection.favorites_basic",
                }
            ],
        }
    return manifest


def _write_fake_protocol_plugins(root: Path) -> None:
    common_video_capabilities = [
        {"key": "catalog.search"},
        {"key": "catalog.detail"},
        {"key": "catalog.by_code"},
        {"key": "collection.list"},
        {"key": "collection.detail"},
        {"key": "person.search"},
        {"key": "person.works"},
        {"key": "health.query.status"},
    ]
    plugin_specs = [
        (
            "comic_alpha",
            _fake_manifest(
                plugin_id="comic.alpha",
                name="Comic Alpha",
                config_key="comic_alpha",
                media_type="comic",
                host_prefix="CA",
                required_fields=["username", "password"],
                order=10,
                capabilities=[
                    {"key": "catalog.search", "result_detail_policy": {"mode": "search_payload"}},
                    {"key": "catalog.detail"},
                    {"key": "collection.favorites"},
                    {"key": "collection.favorites_basic"},
                    {"key": "collection.list"},
                    {"key": "collection.detail"},
                    {"key": "asset.bundle.fetch", "default_params": {"decode_images": True}},
                    {"key": "asset.cover.fetch"},
                    {"key": "asset.preview.resolve"},
                    {"key": "storage.comic_dir.resolve"},
                    {"key": "health.query.status"},
                ],
                fields=[
                    {"key": "enabled", "label": "启用", "type": "boolean"},
                    {"key": "username", "label": "账号", "type": "text"},
                    {"key": "password", "label": "密码", "type": "password", "secret": True},
                ],
                storage_field="download_dir",
                storage_relative_dir="comic/{host_prefix}",
            ),
        ),
        (
            "comic_beta",
            _fake_manifest(
                plugin_id="comic.beta",
                name="Comic Beta",
                config_key="comic_beta",
                media_type="comic",
                host_prefix="CB",
                required_fields=["account", "password"],
                order=20,
                capabilities=[
                    {"key": "catalog.search"},
                    {"key": "catalog.detail"},
                    {"key": "collection.favorites_basic"},
                    {"key": "asset.bundle.fetch"},
                    {"key": "asset.cover.fetch"},
                    {"key": "asset.preview.resolve"},
                    {"key": "storage.comic_dir.resolve"},
                    {"key": "health.query.status"},
                ],
                fields=[
                    {"key": "enabled", "label": "启用", "type": "boolean"},
                    {"key": "account", "label": "账号", "type": "text"},
                    {"key": "password", "label": "密码", "type": "password", "secret": True},
                ],
                storage_field="base_dir",
                storage_relative_dir="comic/{host_prefix}",
            ),
        ),
        (
            "video_alpha",
            _fake_manifest(
                plugin_id="video.alpha",
                name="Video Alpha",
                config_key="video_alpha",
                media_type="video",
                host_prefix="VA",
                required_fields=["cookies._session"],
                order=30,
                capabilities=common_video_capabilities,
                fields=[
                    {"key": "enabled", "label": "启用", "type": "boolean"},
                    {"key": "cookie_string", "label": "Cookie", "type": "textarea", "secret": True},
                ],
                helpers={
                    "video_alpha_cookie_guide": {
                        "content_type": "text/html",
                        "body": "<html><body>Video Alpha Cookie Guide</body></html>",
                    }
                },
                actions=[
                    {
                        "key": "auth.open_cookie_guide",
                        "label": "打开 Cookie 帮助",
                        "kind": "open_url",
                        "helper_key": "video_alpha_cookie_guide",
                        "scope": "configuration",
                    }
                ],
            ),
        ),
        (
            "video_beta",
            _fake_manifest(
                plugin_id="video.beta",
                name="Video Beta",
                config_key="video_beta",
                media_type="video",
                host_prefix="VB",
                required_fields=[],
                order=40,
                capabilities=common_video_capabilities,
                fields=[{"key": "enabled", "label": "启用", "type": "boolean"}],
                cover_fit="contain",
            ),
        ),
    ]
    for plugin_dir_name, manifest in plugin_specs:
        plugin_dir = root / plugin_dir_name
        plugin_dir.mkdir(parents=True, exist_ok=True)
        (plugin_dir / "fake_provider.py").write_text(_FAKE_PROVIDER_SOURCE, encoding="utf-8")
        _write_json(plugin_dir / "ultimate-plugin.json", manifest)


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
def teledrive_client():
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


@pytest.fixture(scope="module")
def fake_third_party_client():
    prepared = prepare_profile("integration_third_party_fake", clean=True)
    runtime_root = Path(prepared["runtime_root"])
    fake_plugin_root = runtime_root / "fake_protocol_plugins"
    _write_fake_protocol_plugins(fake_plugin_root)

    third_party_config_path = Path(prepared["third_party_config_path"])
    payload = {}
    try:
        payload = json.loads(third_party_config_path.read_text(encoding="utf-8"))
    except Exception:
        payload = {}
    adapters = payload.setdefault("adapters", {})
    adapters["comic_alpha"] = {
        **dict(adapters.get("comic_alpha") or {}),
        "enabled": True,
        "username": "test-comic-alpha",
        "password": "test-comic-alpha-pass",
    }
    adapters["comic_beta"] = {
        **dict(adapters.get("comic_beta") or {}),
        "enabled": True,
        "account": "test-comic-beta",
        "password": "test-comic-beta-pass",
    }
    adapters["video_alpha"] = {
        **dict(adapters.get("video_alpha") or {}),
        "enabled": True,
        "cookies": {
            "_session": "test-video-alpha-session",
            "over18": "1",
            "locale": "zh",
        },
    }
    adapters["video_beta"] = {
        **dict(adapters.get("video_beta") or {}),
        "enabled": True,
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
        "ULTIMATE_PLUGIN_ROOTS": str(fake_plugin_root),
        "ULTIMATE_PLUGIN_ROOTS_ONLY": "1",
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

    import werkzeug
    if not hasattr(werkzeug, "__version__"):
        werkzeug.__version__ = "3"

    client = backend_app.app.test_client()
    context = {
        "client": client,
        "runtime_root": runtime_root,
        "data_dir": Path(prepared["data_dir"]),
        "meta_dir": Path(prepared["data_dir"]) / "meta_data",
        "third_party_config_path": third_party_config_path,
        "fake_plugin_root": fake_plugin_root,
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
