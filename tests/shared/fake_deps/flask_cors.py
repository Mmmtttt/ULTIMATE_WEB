"""
Minimal flask_cors compatibility layer for isolated test runtime.

Goal:
- Avoid hard dependency on `flask-cors` in constrained sandboxes.
- Keep browser-based E2E tests functional by adding permissive CORS headers.
"""

from __future__ import annotations

from functools import wraps
from typing import Any, Callable

from flask import make_response, request


_DEFAULT_ALLOW_METHODS = "GET,POST,PUT,PATCH,DELETE,OPTIONS,HEAD"
_DEFAULT_ALLOW_HEADERS = "Content-Type,Authorization,Range,Accept,Origin,User-Agent"


def _apply_cors_headers(response: Any) -> Any:
    origin = request.headers.get("Origin", "").strip() or "*"
    request_allow_headers = request.headers.get("Access-Control-Request-Headers", "").strip()

    response.headers.setdefault("Access-Control-Allow-Origin", origin)
    response.headers.setdefault("Vary", "Origin")
    response.headers.setdefault("Access-Control-Allow-Credentials", "true")
    response.headers.setdefault("Access-Control-Allow-Methods", _DEFAULT_ALLOW_METHODS)
    response.headers.setdefault(
        "Access-Control-Allow-Headers",
        request_allow_headers or _DEFAULT_ALLOW_HEADERS,
    )
    return response


def _register_app_hook(app: Any) -> Any:
    if getattr(app, "_fake_flask_cors_registered", False):
        return app

    @app.after_request
    def _fake_cors_after_request(response: Any) -> Any:
        return _apply_cors_headers(response)

    setattr(app, "_fake_flask_cors_registered", True)
    return app


class _FakeCORS:
    def __init__(self, app: Any = None, *args: Any, **kwargs: Any) -> None:
        if app is not None:
            self.init_app(app, *args, **kwargs)

    def init_app(self, app: Any, *args: Any, **kwargs: Any) -> Any:
        return _register_app_hook(app)


def CORS(app: Any = None, *args: Any, **kwargs: Any) -> Any:
    if app is None:
        return _FakeCORS()
    return _register_app_hook(app)


def cross_origin(*args: Any, **kwargs: Any) -> Callable:
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*f_args: Any, **f_kwargs: Any) -> Any:
            response = make_response(func(*f_args, **f_kwargs))
            return _apply_cors_headers(response)

        return wrapper

    return decorator

