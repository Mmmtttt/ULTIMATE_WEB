"""
Minimal flask_cors stub for isolated test runtime.

This avoids hard dependency on flask-cors in local/CI sandboxes where the
package is unavailable. Our integration tests do not validate CORS behavior.
"""

from __future__ import annotations

from typing import Any, Callable


def CORS(app: Any = None, *args: Any, **kwargs: Any) -> Any:
    return app


def cross_origin(*args: Any, **kwargs: Any) -> Callable:
    def decorator(func: Callable) -> Callable:
        return func

    return decorator

