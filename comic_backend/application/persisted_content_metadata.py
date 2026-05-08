from __future__ import annotations

import os
from copy import deepcopy
from typing import Any, Dict

from core.constants import DATA_DIR
from protocol.presentation import annotate_item


def normalize_data_relative_path(path: str) -> str:
    raw_path = str(path or "").strip()
    if not raw_path:
        return ""

    if raw_path.startswith("/media/"):
        return raw_path[len("/media/") :].lstrip("/").replace("\\", "/")

    try:
        expanded = os.path.abspath(os.path.expandvars(os.path.expanduser(raw_path)))
    except Exception:
        return ""

    data_root = os.path.abspath(DATA_DIR)
    try:
        if os.path.commonpath([data_root, expanded]) != data_root:
            return ""
    except Exception:
        return ""

    relative = os.path.relpath(expanded, data_root).replace("\\", "/").strip("/")
    if relative in {"", "."}:
        return ""
    return relative


def resolve_data_relative_path(relative_path: str) -> str:
    relative = str(relative_path or "").strip().lstrip("/").replace("/", os.sep)
    if not relative:
        return ""

    candidate = os.path.abspath(os.path.join(DATA_DIR, relative))
    data_root = os.path.abspath(DATA_DIR)
    try:
        if os.path.commonpath([data_root, candidate]) != data_root:
            return ""
    except Exception:
        return ""
    return candidate


def extract_persisted_annotation(item: Dict[str, Any] | None) -> Dict[str, Any]:
    raw_item = dict(item or {})
    persisted: Dict[str, Any] = {}

    for key in ("platform", "plugin_id", "plugin_name"):
        value = str(raw_item.get(key) or "").strip()
        if value:
            persisted[key] = value

    display = raw_item.get("display")
    if isinstance(display, dict) and display:
        persisted["display"] = deepcopy(display)

    return persisted


def build_persisted_annotation(
    item: Dict[str, Any] | None,
    *,
    media_type: str,
    plugin_id: str | None = None,
    platform_name: str | None = None,
    capability: str | None = None,
) -> Dict[str, Any]:
    annotated = annotate_item(
        item or {},
        plugin_id=str(plugin_id or "").strip() or None,
        platform_name=str(platform_name or "").strip() or None,
        media_type=str(media_type or "").strip() or None,
        capability=str(capability or "").strip() or None,
    )
    return extract_persisted_annotation(annotated)
