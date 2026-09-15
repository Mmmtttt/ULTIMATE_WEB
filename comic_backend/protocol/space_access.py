"""Space-level access policy for protocol plugins.

Plugin code is shared by the two runtime listeners.  Only the normal space
can change the policy; the private space consumes the persisted allowlist.
"""

from __future__ import annotations

import json
import os
import threading
from typing import Any, Iterable

from core.config_paths import THIRD_PARTY_CONFIG_PATH
from core.storage_layout import SPACE_MODE_PRIVATE, get_current_space_mode


PRIVATE_ENABLED_PLUGIN_IDS_KEY = "private_enabled_plugin_ids"
_CACHE_LOCK = threading.Lock()
_PRIVATE_ALLOWLIST_SIGNATURE: tuple[int, int] | None = None
_PRIVATE_ALLOWLIST: frozenset[str] = frozenset()


def _normalize_plugin_ids(values: Iterable[Any] | None) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values or []:
        plugin_id = str(value or "").strip()
        if not plugin_id or plugin_id in seen:
            continue
        seen.add(plugin_id)
        result.append(plugin_id)
    return result


def _load_normal_config() -> dict[str, Any]:
    try:
        with open(THIRD_PARTY_CONFIG_PATH, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
        return payload if isinstance(payload, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}


def _config_signature() -> tuple[int, int] | None:
    try:
        stat = os.stat(THIRD_PARTY_CONFIG_PATH)
        return stat.st_mtime_ns, stat.st_size
    except OSError:
        return None


def get_private_enabled_plugin_ids() -> set[str]:
    global _PRIVATE_ALLOWLIST_SIGNATURE, _PRIVATE_ALLOWLIST

    signature = _config_signature()
    with _CACHE_LOCK:
        if signature == _PRIVATE_ALLOWLIST_SIGNATURE:
            return set(_PRIVATE_ALLOWLIST)

        access = _load_normal_config().get("space_access") or {}
        if not isinstance(access, dict):
            enabled_ids: set[str] = set()
        else:
            enabled_ids = set(_normalize_plugin_ids(access.get(PRIVATE_ENABLED_PLUGIN_IDS_KEY) or []))
        _PRIVATE_ALLOWLIST_SIGNATURE = signature
        _PRIVATE_ALLOWLIST = frozenset(enabled_ids)
        return set(enabled_ids)


def invalidate_private_access_cache() -> None:
    global _PRIVATE_ALLOWLIST_SIGNATURE, _PRIVATE_ALLOWLIST
    with _CACHE_LOCK:
        _PRIVATE_ALLOWLIST_SIGNATURE = None
        _PRIVATE_ALLOWLIST = frozenset()


def is_plugin_available_in_current_space(plugin_id: str) -> bool:
    normalized = str(plugin_id or "").strip()
    if not normalized or get_current_space_mode() != SPACE_MODE_PRIVATE:
        return True
    return normalized in get_private_enabled_plugin_ids()


def normalize_private_enabled_plugin_ids(values: Iterable[Any] | None) -> list[str]:
    return _normalize_plugin_ids(values)
