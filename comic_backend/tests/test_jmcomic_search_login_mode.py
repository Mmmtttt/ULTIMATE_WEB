import sys
import types
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from third_party.jmcomic_adapter import JMComicAdapter


class _DummyApiClient:
    client_key = "api"


def _build_adapter(monkeypatch, config):
    monkeypatch.setattr(JMComicAdapter, "_load_jmcomic_api", lambda self: None)
    return JMComicAdapter(config=config)


def test_get_search_client_requires_credentials(monkeypatch):
    adapter = _build_adapter(monkeypatch, {"username": "", "password": ""})

    fake_module = types.SimpleNamespace(get_client=lambda **kwargs: _DummyApiClient())
    monkeypatch.setitem(sys.modules, "jmcomic_api", fake_module)

    with pytest.raises(RuntimeError, match="仅支持 API 登录态"):
        adapter._get_search_client()


def test_get_search_client_uses_api_login_and_returns_login_mode(monkeypatch):
    called = {}

    def fake_get_client(username=None, password=None):
        called["username"] = username
        called["password"] = password
        return _DummyApiClient()

    adapter = _build_adapter(
        monkeypatch,
        {"username": REDACTED_USERNAME, "password": "REDACTED_PASSWORD"},
    )
    monkeypatch.setattr(adapter, "_is_login_session_valid", lambda client, username: True)

    fake_module = types.SimpleNamespace(get_client=fake_get_client)
    monkeypatch.setitem(sys.modules, "jmcomic_api", fake_module)

    client, is_login = adapter._get_search_client()

    assert is_login is True
    assert getattr(client, "client_key", "") == "api"
    assert called["username"] == "REDACTED_USERNAME"
    assert called["password"] == "REDACTED_PASSWORD"


def test_get_search_client_raises_when_login_probe_fails(monkeypatch):
    def fake_get_client(username=None, password=None):
        return _DummyApiClient()

    adapter = _build_adapter(
        monkeypatch,
        {"username": "REDACTED_USERNAME", "password": "REDACTED_PASSWORD"},
    )
    monkeypatch.setattr(adapter, "_is_login_session_valid", lambda client, username: False)

    fake_module = types.SimpleNamespace(get_client=fake_get_client)
    monkeypatch.setitem(sys.modules, "jmcomic_api", fake_module)

    with pytest.raises(RuntimeError, match="登录态校验失败"):
        adapter._get_search_client()
