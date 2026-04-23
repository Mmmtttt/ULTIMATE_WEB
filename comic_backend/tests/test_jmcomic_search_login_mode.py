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
        download_album=lambda *_args, **_kwargs: ({}, True),
        get_album_detail=lambda *_args, **_kwargs: {},
        get_client=lambda **_kwargs: object(),
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

    def fake_get_client(username=None, password=None):
        called["username"] = username
        called["password"] = password
        return dummy_client

    monkeypatch.setattr(module, "get_client", fake_get_client)

    client, username = provider._get_search_client({"username": "test_user", "password": "test_pass"})

    assert client is dummy_client
    assert username == "test_user"
    assert called == {"username": "test_user", "password": "test_pass"}


def test_get_search_client_raises_when_api_login_fails(monkeypatch):
    module = _load_provider_module(monkeypatch)
    provider = _build_provider(module)

    def fake_get_client(username=None, password=None):
        raise RuntimeError("boom")

    monkeypatch.setattr(module, "get_client", fake_get_client)

    with pytest.raises(RuntimeError, match="登录失败"):
        provider._get_search_client({"username": "test_user", "password": "test_pass"})
