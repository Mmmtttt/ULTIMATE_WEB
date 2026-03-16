"""
Wrapper for the third-party Missav sub-repository.
"""

import os
import sys
from functools import lru_cache


_MISSAV_PATH = os.path.join(os.path.dirname(__file__), "Missav")


def _ensure_missav_path():
    if _MISSAV_PATH in sys.path:
        return
    sys.path.insert(0, _MISSAV_PATH)


@lru_cache(maxsize=4)
def get_client(proxy_base_path="/api/v1/video"):
    _ensure_missav_path()
    from missav import MissavClient

    return MissavClient(proxy_base_path=proxy_base_path)


__all__ = ["get_client"]
