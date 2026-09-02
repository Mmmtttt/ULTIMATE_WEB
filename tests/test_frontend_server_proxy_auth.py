from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]


def _load_frontend_server():
    import werkzeug
    if not hasattr(werkzeug, "__version__"):
        werkzeug.__version__ = "test"

    module_path = ROOT_DIR / "comic_frontend" / "frontend_server.py"
    spec = importlib.util.spec_from_file_location("frontend_server_for_test", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _server_config(*, auth_enabled: bool = True) -> dict:
    return {
        "backend": {
            "port": 6123,
            "ssl_enabled": False,
        },
        "frontend": {
            "host": "127.0.0.1",
            "port": 6173,
            "ssl_enabled": False,
        },
        "auth": {
            "enabled": auth_enabled,
            "password": "correct",
            "private_port": 6100,
            "normal_port": 6101,
            "secret_key": "test-secret",
        },
    }


def _configure_frontend_server(frontend_server, tmp_path: Path, config: dict) -> None:
    config_path = tmp_path / "server_config.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    frontend_server.SERVER_CONFIG_PATH = str(config_path)
    frontend_server.SERVER_CONFIG = config
    frontend_server._SERVER_CONFIG_MTIME = None
    frontend_server._refresh_server_config_if_changed()


class FakeResponse:
    def __init__(self, payload: dict | bytes, *, status_code: int = 200, headers: dict | None = None):
        self.status_code = status_code
        self.headers = headers or {"content-type": "application/json"}
        if isinstance(payload, bytes):
            self.content = payload
        else:
            self.content = json.dumps(payload).encode("utf-8")


class FakeStreamingResponse:
    def __init__(self, chunks: list[bytes], *, status_code: int = 200, headers: dict | None = None):
        self.status_code = status_code
        self.headers = headers or {}
        self.chunks = chunks
        self.closed = False

    @property
    def content(self):
        raise AssertionError("streaming proxy responses must not be buffered through .content")

    def iter_content(self, chunk_size=1):
        for chunk in self.chunks:
            yield chunk

    def close(self):
        self.closed = True


def test_frontend_proxy_routes_assets_by_per_client_space_cookie_and_ignores_header_spoofing(monkeypatch, tmp_path):
    frontend_server = _load_frontend_server()
    _configure_frontend_server(frontend_server, tmp_path, _server_config(auth_enabled=True))

    calls = []

    def fake_request(url, **kwargs):
        calls.append({"url": url, "kwargs": kwargs})
        if url.endswith("/api/v1/auth/login"):
            password = (kwargs.get("json") or {}).get("password")
            authenticated = password == "correct"
            mode = "normal" if authenticated else "private"
            return FakeResponse(
                {
                    "code": 200,
                    "msg": "success",
                    "data": {"authenticated": authenticated, "mode": mode},
                },
                headers={
                    "content-type": "application/json",
                    "set-cookie": f"session={mode}-backend-session; Path=/",
                },
            )
        return FakeResponse({"code": 200, "msg": "success", "data": {"url": url}})

    monkeypatch.setattr(frontend_server.requests, "post", fake_request)
    monkeypatch.setattr(frontend_server.requests, "get", fake_request)

    app = frontend_server.create_app()
    client_a = app.test_client()
    client_b = app.test_client()

    login_a = client_a.post("/api/v1/auth/login", json={"password": "correct"}, base_url="https://front.test")
    login_b = client_b.post("/api/v1/auth/login", json={"password": "wrong"}, base_url="https://front.test")

    assert login_a.status_code == 200
    assert login_b.status_code == 200

    client_a.get("/static/cover/normal-cover.jpg", base_url="https://front.test")
    client_b.get("/static/cover/private-cover.jpg", base_url="https://front.test")

    client_a.get(
        "/api/v1/comic/list",
        headers={"X-Space-Mode": "private"},
        base_url="https://front.test",
    )
    client_b.get(
        "/api/v1/comic/list",
        headers={"X-Space-Mode": "normal"},
        base_url="https://front.test",
    )

    routed_urls = [item["url"] for item in calls]
    assert "http://127.0.0.1:6101/static/cover/normal-cover.jpg" in routed_urls
    assert "http://127.0.0.1:6100/static/cover/private-cover.jpg" in routed_urls
    assert routed_urls[-2] == "http://127.0.0.1:6101/api/v1/comic/list"
    assert routed_urls[-1] == "http://127.0.0.1:6100/api/v1/comic/list"


def test_frontend_proxy_uses_single_backend_port_when_auth_is_disabled(monkeypatch, tmp_path):
    frontend_server = _load_frontend_server()
    _configure_frontend_server(frontend_server, tmp_path, _server_config(auth_enabled=False))

    calls = []

    def fake_get(url, **kwargs):
        calls.append({"url": url, "kwargs": kwargs})
        return FakeResponse({"code": 200, "msg": "success", "data": {}})

    monkeypatch.setattr(frontend_server.requests, "get", fake_get)

    app = frontend_server.create_app()
    client = app.test_client()
    response = client.get("/api/v1/comic/list")

    assert response.status_code == 200
    assert calls[-1]["url"] == "http://127.0.0.1:6123/api/v1/comic/list"


def test_frontend_proxy_reloads_server_config_without_restart(monkeypatch, tmp_path):
    frontend_server = _load_frontend_server()
    config = _server_config(auth_enabled=False)
    _configure_frontend_server(frontend_server, tmp_path, config)

    calls = []

    def fake_get(url, **kwargs):
        calls.append({"url": url, "kwargs": kwargs})
        return FakeResponse({"code": 200, "msg": "success", "data": {}})

    monkeypatch.setattr(frontend_server.requests, "get", fake_get)

    app = frontend_server.create_app()
    client = app.test_client()
    client.get("/api/v1/comic/list")

    config["backend"]["port"] = 6124
    config_path = Path(frontend_server.SERVER_CONFIG_PATH)
    previous_mtime = os.path.getmtime(config_path)
    config_path.write_text(json.dumps(config), encoding="utf-8")
    os.utime(config_path, (previous_mtime + 2, previous_mtime + 2))

    client.get("/api/v1/comic/list")

    assert calls[-2]["url"] == "http://127.0.0.1:6123/api/v1/comic/list"
    assert calls[-1]["url"] == "http://127.0.0.1:6124/api/v1/comic/list"


def test_frontend_proxy_streams_local_video_without_buffering(monkeypatch, tmp_path):
    frontend_server = _load_frontend_server()
    _configure_frontend_server(frontend_server, tmp_path, _server_config(auth_enabled=False))

    calls = []
    stream_response = FakeStreamingResponse(
        [b"video-", b"chunk"],
        status_code=206,
        headers={
            "content-type": "video/mp4",
            "content-length": "11",
            "content-range": "bytes 0-10/100",
            "accept-ranges": "bytes",
        },
    )

    def fake_get(url, **kwargs):
        calls.append({"url": url, "kwargs": kwargs})
        return stream_response

    monkeypatch.setattr(frontend_server.requests, "get", fake_get)

    app = frontend_server.create_app()
    client = app.test_client()
    response = client.get(
        "/api/v1/video/local-stream/VIDEO001",
        headers={"Range": "bytes=0-"},
    )

    assert response.status_code == 206
    assert response.data == b"video-chunk"
    assert response.headers["Content-Range"] == "bytes 0-10/100"
    assert response.headers["Accept-Ranges"] == "bytes"
    assert stream_response.closed is True
    assert calls[-1]["kwargs"]["stream"] is True
    assert calls[-1]["kwargs"]["headers"]["range"] == "bytes=0-"


def test_frontend_proxy_streams_missav_proxy2_without_buffering(monkeypatch, tmp_path):
    frontend_server = _load_frontend_server()
    _configure_frontend_server(frontend_server, tmp_path, _server_config(auth_enabled=False))

    stream_response = FakeStreamingResponse(
        [b"#EXTM3U\n", b"#EXTINF:1,\nseg.ts\n"],
        status_code=200,
        headers={"content-type": "application/vnd.apple.mpegurl"},
    )

    def fake_get(url, **kwargs):
        return stream_response

    monkeypatch.setattr(frontend_server.requests, "get", fake_get)

    app = frontend_server.create_app()
    client = app.test_client()
    response = client.get("/api/v1/video/proxy2?url=https%3A%2F%2Fmissav.example%2Findex.m3u8")

    assert response.status_code == 200
    assert response.data == b"#EXTM3U\n#EXTINF:1,\nseg.ts\n"
    assert response.headers["Content-Type"] == "application/vnd.apple.mpegurl"
    assert stream_response.closed is True
