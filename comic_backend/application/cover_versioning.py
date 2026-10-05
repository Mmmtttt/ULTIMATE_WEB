from __future__ import annotations

import os
from typing import Any, Dict, Iterable
from urllib.parse import parse_qsl, quote, urlencode, urlsplit, urlunsplit

from core.storage_layout import get_cover_dir, get_data_dir

DEFAULT_COVER_THUMBNAIL_WIDTH = 360


def build_versioned_local_media_url(url: Any) -> str:
    text = str(url or "").strip()
    if not text:
        return ""
    parsed = urlsplit(text)
    if parsed.scheme or parsed.netloc:
        return text

    query_pairs = parse_qsl(parsed.query, keep_blank_values=True)
    if any(key == "v" for key, _value in query_pairs):
        return text

    file_path = resolve_local_media_file(parsed.path)
    if not file_path:
        return text
    try:
        version = str(os.stat(file_path).st_mtime_ns)
    except OSError:
        return text

    query_pairs.append(("v", version))
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(query_pairs), parsed.fragment))


def build_cover_thumbnail_url(url: Any, width: int = DEFAULT_COVER_THUMBNAIL_WIDTH) -> str:
    text = str(url or "").strip()
    if not text:
        return ""
    parsed = urlsplit(text)
    if parsed.scheme or parsed.netloc:
        return ""

    file_path = resolve_local_media_file(parsed.path)
    if not file_path:
        return ""
    try:
        version = str(os.stat(file_path).st_mtime_ns)
    except OSError:
        return ""

    safe_width = int(width or DEFAULT_COVER_THUMBNAIL_WIDTH)
    query = urlencode(
        {
            "src": parsed.path,
            "w": str(safe_width),
            "v": version,
        },
        quote_via=quote,
    )
    return f"/api/v1/performance/cover-thumbnail?{query}"


def annotate_cover_url(payload: Dict[str, Any], preferred_keys: Iterable[str] = ("cover_path_local", "cover_path")) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        return payload
    original_cover_url = str(payload.get("cover_url") or "").strip()
    for key in preferred_keys:
        candidate = str(payload.get(key) or "").strip()
        if not candidate:
            continue
        payload["cover_url"] = build_versioned_local_media_url(candidate)
        payload["cover_thumbnail_url"] = build_cover_thumbnail_url(candidate)
        return payload
    payload["cover_url"] = build_versioned_local_media_url(original_cover_url) if original_cover_url else ""
    payload["cover_thumbnail_url"] = build_cover_thumbnail_url(original_cover_url) if original_cover_url else ""
    return payload


def resolve_local_media_file(path: str) -> str:
    normalized = str(path or "").replace("\\", "/").strip()
    if normalized.startswith("/static/cover/"):
        relative = normalized[len("/static/cover/") :].lstrip("/")
        return _safe_join(get_cover_dir(), relative)
    if normalized.startswith("/media/"):
        relative = normalized[len("/media/") :].lstrip("/")
        return _safe_join(get_data_dir(), relative)
    return ""


def _safe_join(base_dir: str, relative_path: str) -> str:
    base_abs = os.path.abspath(base_dir)
    candidate = os.path.abspath(os.path.join(base_abs, *relative_path.split("/")))
    try:
        common = os.path.commonpath([base_abs, candidate])
    except ValueError:
        return ""
    if common != base_abs:
        return ""
    return candidate
