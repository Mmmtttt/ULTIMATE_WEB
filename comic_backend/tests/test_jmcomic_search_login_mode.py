import importlib.util
import sys
import types
from pathlib import Path

import pytest


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def _load_provider_module(monkeypatch):
    fake_jmcomic_api = types.SimpleNamespace(
        build_client=lambda **_kwargs: object(),
        download_album=lambda *_args, **_kwargs: ({}, True),
        get_album_detail=lambda *_args, **_kwargs: {},
        get_favorite_comics=lambda **_kwargs: {"comics": []},
        get_favorite_comics_full=lambda **_kwargs: {"comics": []},
        search_comics=lambda *_args, **_kwargs: {"results": [], "page_count": 1},
        search_comics_full=lambda *_args, **_kwargs: {"results": [], "page_count": 1},
    )
    monkeypatch.setitem(sys.modules, "jmcomic_api", fake_jmcomic_api)

    module_path = BACKEND_ROOT / "third_party" / "JMComic-Crawler-Python" / "ultimate_provider.py"
    spec = importlib.util.spec_from_file_location("jmcomic_provider_for_tests", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"failed to load provider from {module_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _build_provider(module):
    return module.JMComicProvider(manifest={}, manifest_path="")


def test_get_search_client_requires_credentials(monkeypatch):
    module = _load_provider_module(monkeypatch)
    provider = _build_provider(module)

    with pytest.raises(RuntimeError, match="未配置账号或密码"):
        provider._get_search_client({"username": "", "password": ""})


def test_get_search_client_uses_api_login_and_returns_username(monkeypatch):
    module = _load_provider_module(monkeypatch)
    provider = _build_provider(module)
    called = {}
    dummy_client = object()

    def fake_build_client(username=None, password=None, download_dir=None):
        called["username"] = username
        called["password"] = password
        called["download_dir"] = download_dir
        return dummy_client

    monkeypatch.setattr(module, "build_jm_client", fake_build_client)

    client, username = provider._get_search_client(
        {"username": "test_user", "password": "test_pass", "download_dir": "/tmp/jm"}
    )

    assert client is dummy_client
    assert username == "test_user"
    assert called == {"username": "test_user", "password": "test_pass", "download_dir": "/tmp/jm"}


def test_get_search_client_raises_when_api_login_fails(monkeypatch):
    module = _load_provider_module(monkeypatch)
    provider = _build_provider(module)

    def fake_build_client(username=None, password=None, download_dir=None):
        raise RuntimeError("boom")

    monkeypatch.setattr(module, "build_jm_client", fake_build_client)

    with pytest.raises(RuntimeError, match="登录失败"):
        provider._get_search_client({"username": "test_user", "password": "test_pass"})


def test_asset_bundle_fetch_uses_explicit_runtime_client_and_download_dir(monkeypatch):
    module = _load_provider_module(monkeypatch)
    provider = _build_provider(module)
    dummy_client = object()
    captured = {}

    def fake_build_client(username=None, password=None, download_dir=None):
        captured["client_build"] = {
            "username": username,
            "password": password,
            "download_dir": download_dir,
        }
        return dummy_client

    def fake_download_album(album_id, download_dir=None, client=None, show_progress=True, decode_images=True):
        captured["download"] = {
            "album_id": album_id,
            "download_dir": download_dir,
            "client": client,
            "show_progress": show_progress,
            "decode_images": decode_images,
        }
        return {"album_id": album_id}, True

    monkeypatch.setattr(module, "build_jm_client", fake_build_client)
    monkeypatch.setattr(module, "jm_download_album", fake_download_album)

    result = provider.execute(
        "asset.bundle.fetch",
        {
            "album_id": "123456",
            "download_dir": "D:/runtime/custom/JM-downloads",
            "show_progress": False,
            "extra": {"decode_images": False},
        },
        {},
        {"username": "runtime-user", "password": "runtime-pass", "download_dir": "D:/runtime/comic/JM"},
    )

    assert result["success"] is True
    assert captured["client_build"] == {
        "username": "runtime-user",
        "password": "runtime-pass",
        "download_dir": "D:/runtime/comic/JM",
    }
    assert captured["download"] == {
        "album_id": 123456,
        "download_dir": "D:/runtime/custom/JM-downloads",
        "client": dummy_client,
        "show_progress": False,
        "decode_images": False,
    }


def test_provider_bootstraps_local_jmcomic_package_from_plugin_dir():
    plugin_root = BACKEND_ROOT / "third_party" / "JMComic-Crawler-Python"
    lib_src_dir = (plugin_root / "lib" / "src").resolve()
    module_name = "jmcomic_provider_packaged_import_test"

    for name in ("jmcomic", "jmcomic_api", module_name):
        sys.modules.pop(name, None)

    spec = importlib.util.spec_from_file_location(module_name, plugin_root / "ultimate_provider.py")
    if spec is None or spec.loader is None:
        raise RuntimeError(f"failed to load provider from {plugin_root / 'ultimate_provider.py'}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    jmcomic_module = sys.modules.get("jmcomic")
    assert jmcomic_module is not None
    assert lib_src_dir in Path(str(jmcomic_module.__file__ or "")).resolve().parents
