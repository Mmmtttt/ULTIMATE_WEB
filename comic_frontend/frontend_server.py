#!/usr/bin/env python3
"""
Frontend server for production use.

Serves static frontend files and proxies /api requests to backend instances.
Acts as the only externally-facing entry point; backends bind to 127.0.0.1 only.
"""

from __future__ import annotations

import os
import sys
import threading
import json
from pathlib import Path

import requests
from flask import Flask, Response, request, make_response, send_from_directory, abort, stream_with_context

# Add backend source to path so we can reuse config & SSL modules
_BACKEND_SRC = Path(__file__).resolve().parents[1] / "comic_backend"
if str(_BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(_BACKEND_SRC))

import copy  # noqa: E402
from core.config_paths import (  # noqa: E402
    DEFAULT_SERVER_CONFIG,
    SERVER_CONFIG_PATH,
    APP_CONFIG_DIR,
)
from core.ssl_cert import get_ssl_context_tuple  # noqa: E402


def _load_server_config():
    if os.path.exists(SERVER_CONFIG_PATH):
        try:
            with open(SERVER_CONFIG_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return copy.deepcopy(DEFAULT_SERVER_CONFIG)


def _get_server_config_mtime():
    try:
        return os.path.getmtime(SERVER_CONFIG_PATH)
    except Exception:
        return None


SERVER_CONFIG = _load_server_config()
_SERVER_CONFIG_MTIME = _get_server_config_mtime()
SPACE_COOKIE_NAME = "ultimate_space_mode"
SPACE_MODE_NORMAL = "normal"
SPACE_MODE_PRIVATE = "private"


def _refresh_server_config_if_changed() -> None:
    global SERVER_CONFIG, _SERVER_CONFIG_MTIME
    current_mtime = _get_server_config_mtime()
    if current_mtime == _SERVER_CONFIG_MTIME:
        return
    SERVER_CONFIG = _load_server_config()
    _SERVER_CONFIG_MTIME = current_mtime


# ---------- config ----------

def _as_bool(value, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    text = str(value).strip().lower()
    if text in ("1", "true", "yes", "on", "y", "t"):
        return True
    if text in ("0", "false", "no", "off", "n", "f", ""):
        return False
    return default


def _is_auth_enabled() -> bool:
    return _as_bool(SERVER_CONFIG.get("auth", {}).get("enabled", False), default=False)


def _resolve_frontend_host() -> str:
    env_host = str(os.environ.get("FRONTEND_HOST", "")).strip()
    if env_host:
        return env_host
    return SERVER_CONFIG.get("frontend", {}).get("host", "0.0.0.0")


def _resolve_frontend_port() -> int:
    env_port = str(os.environ.get("FRONTEND_PORT", "")).strip()
    if env_port:
        try:
            return int(env_port)
        except Exception:
            pass
    return int(SERVER_CONFIG.get("frontend", {}).get("port", 5173))


def _resolve_ssl_enabled() -> bool:
    env_ssl = os.environ.get("FRONTEND_SSL_ENABLED")
    if env_ssl is not None:
        return _as_bool(env_ssl, default=False)
    if _is_android_runtime():
        return False
    config_val = SERVER_CONFIG.get("frontend", {}).get("ssl_enabled")
    if config_val is None:
        return not _is_android_runtime()
    return _as_bool(config_val, default=not _is_android_runtime())


def _is_android_runtime() -> bool:
    if "ANDROID_APP_FILES_DIR" in os.environ:
        return True
    try:
        from java import dynamic_proxy  # noqa: F401
        return True
    except Exception:
        return False


def _resolve_ssl_auto_generate() -> bool:
    env_auto = os.environ.get("FRONTEND_SSL_AUTO_GENERATE")
    if env_auto is not None:
        return _as_bool(env_auto, default=True)
    return _as_bool(
        SERVER_CONFIG.get("frontend", {}).get("ssl_auto_generate", True),
        default=True,
    )


def _resolve_ssl_cert_path() -> str:
    env_cert = str(os.environ.get("FRONTEND_SSL_CERT_PATH", "")).strip()
    if env_cert:
        return os.path.abspath(os.path.expanduser(env_cert))
    config_cert = str(SERVER_CONFIG.get("frontend", {}).get("ssl_cert_path", "")).strip()
    if config_cert:
        return os.path.abspath(os.path.expanduser(config_cert))
    return ""


def _resolve_ssl_key_path() -> str:
    env_key = str(os.environ.get("FRONTEND_SSL_KEY_PATH", "")).strip()
    if env_key:
        return os.path.abspath(os.path.expanduser(env_key))
    config_key = str(SERVER_CONFIG.get("frontend", {}).get("ssl_key_path", "")).strip()
    if config_key:
        return os.path.abspath(os.path.expanduser(config_key))
    return ""


def _resolve_ssl_context():
    if not _resolve_ssl_enabled():
        return None
    cert_path = _resolve_ssl_cert_path()
    key_path = _resolve_ssl_key_path()
    auto_generate = _resolve_ssl_auto_generate()
    try:
        result = get_ssl_context_tuple(
            cert_path=cert_path or None,
            key_path=key_path or None,
            auto_generate=auto_generate,
        )
        if result:
            return result
    except Exception as e:
        print(f"[frontend] SSL setup failed, falling back to HTTP: {e}")
    return None


def _resolve_frontend_dist_dir() -> str:
    env_path = str(os.environ.get("FRONTEND_DIST_DIR", "")).strip()
    if env_path and os.path.isdir(env_path):
        return os.path.abspath(env_path)

    candidates = [
        os.path.abspath(os.path.join(os.path.dirname(__file__), "dist")),
        os.path.abspath(os.path.join(os.getcwd(), "frontend_dist")),
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend_dist")),
    ]
    for candidate in candidates:
        if os.path.isdir(candidate):
            return candidate
    return ""


def _resolve_normal_backend_base() -> str:
    """Base URL for the normal (auth-required) backend."""
    host = "127.0.0.1"
    port = int(SERVER_CONFIG.get("auth", {}).get("normal_port", 5001))
    ssl = _as_bool(SERVER_CONFIG.get("backend", {}).get("ssl_enabled", True), default=True)
    protocol = "https" if ssl else "http"
    return f"{protocol}://{host}:{port}"


def _resolve_private_backend_base() -> str:
    """Base URL for the private (no auth) backend."""
    host = "127.0.0.1"
    port = int(SERVER_CONFIG.get("auth", {}).get("private_port", 5000))
    ssl = _as_bool(SERVER_CONFIG.get("backend", {}).get("ssl_enabled", True), default=True)
    protocol = "https" if ssl else "http"
    return f"{protocol}://{host}:{port}"


def _resolve_single_backend_base() -> str:
    """Base URL for legacy/single-backend mode."""
    host = "127.0.0.1"
    port = int(SERVER_CONFIG.get("backend", {}).get("port", 5000))
    ssl = _as_bool(SERVER_CONFIG.get("backend", {}).get("ssl_enabled", True), default=True)
    protocol = "https" if ssl else "http"
    return f"{protocol}://{host}:{port}"


# ---------- proxy helpers ----------

_PROXY_HEADERS_PASS = (
    "accept",
    "accept-encoding",
    "accept-language",
    "content-type",
    "content-length",
    "cookie",
    "referer",
    "user-agent",
    "cache-control",
    "pragma",
    "if-modified-since",
    "if-none-match",
    "range",
    "x-sync-token",
)

_RESPONSE_HEADERS_PASS = (
    "content-type",
    "content-length",
    "content-encoding",
    "content-disposition",
    "cache-control",
    "etag",
    "last-modified",
    "set-cookie",
    "location",
    "accept-ranges",
    "content-range",
)

_STREAM_PROXY_PATH_PREFIXES = (
    "/api/v1/video/local-stream/",
    "/api/v1/video/proxy/",
    "/api/v1/video/proxy2",
    "/api/v1/teledrive/files/",
    "/media/",
)

_STREAM_PROXY_CONTENT_TYPES = (
    "application/octet-stream",
    "application/vnd.apple.mpegurl",
    "audio/",
    "video/",
)


def _build_proxy_headers() -> dict:
    headers = {}
    for header_name in _PROXY_HEADERS_PASS:
        value = request.headers.get(header_name)
        if value is not None:
            headers[header_name] = value
    x_forwarded_for = request.headers.get("X-Forwarded-For", "")
    if x_forwarded_for:
        headers["X-Forwarded-For"] = f"{x_forwarded_for}, {request.remote_addr}"
    else:
        headers["X-Forwarded-For"] = request.remote_addr or ""
    headers["X-Forwarded-Proto"] = request.scheme
    headers["X-Forwarded-Host"] = request.host
    return headers


def _copy_proxy_response_headers(response, proxy_resp) -> None:
    for header_name in _RESPONSE_HEADERS_PASS:
        header_value = proxy_resp.headers.get(header_name)
        if header_value is not None:
            if header_name.lower() == "set-cookie":
                # set-cookie may have multiple values; handle carefully
                response.headers.set(header_name, header_value)
            else:
                response.headers[header_name] = header_value


def _build_flask_response(proxy_resp) -> make_response:
    response = make_response(proxy_resp.content, proxy_resp.status_code)
    _copy_proxy_response_headers(response, proxy_resp)
    return response


def _is_stream_proxy_response(path: str, proxy_resp) -> bool:
    if request.method == "HEAD":
        return False
    if not hasattr(proxy_resp, "iter_content"):
        return False

    normalized_path = f"/{str(path or '').lstrip('/')}"
    if normalized_path.startswith(_STREAM_PROXY_PATH_PREFIXES):
        return True

    content_type = str(proxy_resp.headers.get("content-type", "") or "").lower()
    if any(content_type.startswith(prefix) for prefix in _STREAM_PROXY_CONTENT_TYPES):
        return True

    return bool(proxy_resp.headers.get("content-range") or proxy_resp.headers.get("accept-ranges"))


def _build_streaming_flask_response(proxy_resp) -> Response:
    def generate():
        try:
            for chunk in proxy_resp.iter_content(chunk_size=1024 * 256):
                if chunk:
                    yield chunk
        finally:
            proxy_resp.close()

    response = Response(
        stream_with_context(generate()),
        status=proxy_resp.status_code,
    )
    _copy_proxy_response_headers(response, proxy_resp)
    return response


def _read_requested_space_mode() -> str:
    mode = request.args.get("space_mode", "").strip().lower()
    if not mode:
        mode = request.cookies.get(SPACE_COOKIE_NAME, "").strip().lower()
    if mode == SPACE_MODE_NORMAL:
        return SPACE_MODE_NORMAL
    return SPACE_MODE_PRIVATE


def _set_space_mode_cookie(response, mode: str) -> None:
    normalized = SPACE_MODE_NORMAL if str(mode or "").strip().lower() == SPACE_MODE_NORMAL else SPACE_MODE_PRIVATE
    response.set_cookie(
        SPACE_COOKIE_NAME,
        normalized,
        httponly=True,
        secure=bool(request.is_secure),
        samesite="Lax",
        path="/",
    )


def _apply_space_cookie_from_auth_response(response, proxy_resp, path: str) -> None:
    normalized_path = f"/{str(path or '').lstrip('/')}"
    if normalized_path.startswith("/api/v1/auth/") or normalized_path == "/api/v1/auth":
        try:
            payload = json.loads(proxy_resp.content.decode("utf-8") or "{}")
            data = payload.get("data") if isinstance(payload, dict) else {}
            mode = data.get("mode") if isinstance(data, dict) else ""
            if mode:
                _set_space_mode_cookie(response, mode)
                return
        except Exception:
            pass

    if int(getattr(proxy_resp, "status_code", 0) or 0) == 401:
        _set_space_mode_cookie(response, SPACE_MODE_PRIVATE)


def _proxy_to_backend(backend_base: str, path: str):
    url = f"{backend_base.rstrip('/')}/{path.lstrip('/')}"
    headers = _build_proxy_headers()
    params = request.args.to_dict(flat=False)
    timeout = 300

    method = request.method.lower()
    kwargs = {
        "headers": headers,
        "params": params,
        "timeout": timeout,
        "verify": False,
        "stream": True,
    }

    if method in ("post", "put", "patch", "delete"):
        if request.is_json:
            kwargs["json"] = request.get_json(silent=True)
        elif request.files:
            files = []
            for field_name, storage in request.files.items(multi=True):
                storage.stream.seek(0)
                files.append((
                    field_name,
                    (
                        storage.filename,
                        storage.stream,
                        storage.mimetype or "application/octet-stream",
                    ),
                ))
            kwargs["files"] = files
            if request.form:
                kwargs["data"] = request.form.to_dict(flat=False)
        elif request.form:
            kwargs["data"] = request.form.to_dict(flat=False)
        elif request.data:
            kwargs["data"] = request.data

    try:
        resp = getattr(requests, method)(url, **kwargs)
    except requests.exceptions.SSLError as e:
        print(f"[frontend proxy] SSL error connecting to {url}: {e}")
        return make_response({"error": "backend SSL error", "detail": str(e)}, 502)
    except requests.exceptions.ConnectionError as e:
        print(f"[frontend proxy] connection error connecting to {url}: {e}")
        return make_response({"error": "backend unreachable", "detail": str(e)}, 502)
    except Exception as e:
        print(f"[frontend proxy] error proxying to {url}: {e}")
        return make_response({"error": "proxy error", "detail": str(e)}, 502)

    if _is_stream_proxy_response(path, resp):
        response = _build_streaming_flask_response(resp)
        if int(getattr(resp, "status_code", 0) or 0) == 401:
            _set_space_mode_cookie(response, SPACE_MODE_PRIVATE)
        return response

    response = _build_flask_response(resp)
    close_response = getattr(resp, "close", None)
    if callable(close_response):
        close_response()
    _apply_space_cookie_from_auth_response(response, resp, path)
    return response


# ---------- app factory ----------

def create_app() -> Flask:
    app = Flask(__name__)

    dist_dir = _resolve_frontend_dist_dir()
    print(f"[frontend] dist_dir: {dist_dir}")
    print(f"[frontend] single backend: {_resolve_single_backend_base()}")
    print(f"[frontend] normal backend: {_resolve_normal_backend_base()}")
    print(f"[frontend] private backend: {_resolve_private_backend_base()}")
    print(f"[frontend] auth enabled: {_is_auth_enabled()}")

    def _resolve_backend_for_request() -> str:
        _refresh_server_config_if_changed()
        auth_enabled = _is_auth_enabled()
        if not auth_enabled:
            return _resolve_single_backend_base()

        # Auth-related endpoints always go to normal backend (the one that holds the real session)
        path = request.path or ""
        if path.startswith("/api/v1/auth/") or path == "/api/v1/auth":
            return _resolve_normal_backend_base()

        mode = _read_requested_space_mode()
        if mode == SPACE_MODE_NORMAL:
            return _resolve_normal_backend_base()
        return _resolve_private_backend_base()

    # ---- API proxy ----

    @app.route("/api/<path:subpath>", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"])
    def api_proxy(subpath):
        if request.method == "OPTIONS":
            return make_response("", 204)
        backend_base = _resolve_backend_for_request()
        return _proxy_to_backend(backend_base, f"/api/{subpath}")

    # ---- Static / media proxy ----

    @app.route("/static/cover/<path:subpath>", methods=["GET"])
    def cover_proxy(subpath):
        backend_base = _resolve_backend_for_request()
        return _proxy_to_backend(backend_base, f"/static/cover/{subpath}")

    @app.route("/media/<path:subpath>", methods=["GET", "HEAD"])
    def media_proxy(subpath):
        backend_base = _resolve_backend_for_request()
        return _proxy_to_backend(backend_base, f"/media/{subpath}")

    # ---- Health ----

    @app.route("/health")
    def health():
        return {"status": "ok", "role": "frontend-proxy"}

    # ---- Frontend static files ----

    if dist_dir and os.path.isdir(dist_dir):

        @app.route("/")
        def index_root():
            return send_from_directory(dist_dir, "index.html")

        @app.route("/<path:path>")
        def frontend_fallback(path):
            reserved_prefixes = ("api/", "static/", "media/")
            normalized = path.strip("/")
            if normalized.startswith(reserved_prefixes) or normalized in (
                "api",
                "static",
                "media",
                "health",
            ):
                abort(404)

            candidate = os.path.abspath(os.path.join(dist_dir, path))
            frontend_root = os.path.abspath(dist_dir)
            if os.path.commonpath([frontend_root, candidate]) != frontend_root:
                abort(403)

            if os.path.isfile(candidate):
                return send_from_directory(dist_dir, path)

            return send_from_directory(dist_dir, "index.html")

    return app


# ---------- entrypoint ----------

def run_frontend_server():
    host = _resolve_frontend_host()
    port = _resolve_frontend_port()
    ssl_context = _resolve_ssl_context()

    protocol = "https" if ssl_context else "http"
    print(f"[frontend] starting on {protocol}://{host}:{port}")

    app = create_app()
    app.run(host=host, port=port, ssl_context=ssl_context, debug=False, use_reloader=False)


if __name__ == "__main__":
    run_frontend_server()
