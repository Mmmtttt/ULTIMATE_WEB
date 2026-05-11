from __future__ import annotations

import os
import re
from copy import deepcopy
from typing import Any, Dict, Iterable


_INVALID_FS_CHARS_PATTERN = re.compile(r'[\\/:*?"<>|]')

_HOST_VIDEO_PLUGIN_PLATFORM_MAP = {
    "video.javdb": "JAVDB",
    "video.javbus": "JAVBUS",
    "video.missav": "MISSAV",
}

_HOST_VIDEO_DEFAULT_DISPLAY = {
    "aspect_ratio": "16 / 9",
    "mobile_aspect_ratio": "16 / 9",
    "fit": "cover",
}

_HOST_VIDEO_DISPLAY_DEFAULTS = {
    "JAVDB": {
        "aspect_ratio": "16 / 9",
        "mobile_aspect_ratio": "3 / 2",
        "fit": "cover",
    },
    "JAVBUS": {
        "aspect_ratio": "2 / 3",
        "mobile_aspect_ratio": "2 / 3",
        "fit": "contain",
    },
}


def _normalize_fs_name(name: str) -> str:
    normalized = str(name or "").strip().rstrip(".")
    normalized = _INVALID_FS_CHARS_PATTERN.sub("_", normalized)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized


def _generate_name_variants(name: str) -> list[str]:
    raw = str(name or "").strip().rstrip(".")
    if not raw:
        return []

    variants = {
        raw,
        _normalize_fs_name(raw),
        raw.replace("\u3000", " "),
        raw.replace("  ", " "),
        raw.replace(" ", ""),
    }
    if " | " in raw:
        variants.add(raw.replace(" | ", " _ "))
        variants.add(raw.replace(" | ", "_"))
    if "|" in raw:
        variants.add(raw.replace("|", " _ "))
        variants.add(raw.replace("|", "_"))

    return [item for item in variants if item]


def _iter_child_dirs(base_dir: str) -> list[str]:
    if not base_dir or not os.path.isdir(base_dir):
        return []
    try:
        return [
            entry
            for entry in os.listdir(base_dir)
            if os.path.isdir(os.path.join(base_dir, entry))
        ]
    except Exception:
        return []


def _find_matching_child_dir(base_dir: str, target_name: str) -> str:
    target = str(target_name or "").strip()
    if not target:
        return ""

    child_dirs = _iter_child_dirs(base_dir)
    if not child_dirs:
        return ""

    target_lower = target.lower()
    for entry in child_dirs:
        if entry.lower() == target_lower:
            return entry

    variants = _generate_name_variants(target)
    lowered_variants = {item.lower() for item in variants}
    for entry in child_dirs:
        if entry.lower() in lowered_variants:
            return entry

    for entry in child_dirs:
        entry_lower = entry.lower()
        if target_lower in entry_lower or entry_lower in target_lower:
            common_chars = set(target_lower) & set(entry_lower)
            denominator = max(len(set(target_lower)), len(set(entry_lower)))
            if denominator > 0 and (len(common_chars) / denominator) > 0.8:
                return entry

    return ""


def _strip_known_prefix(value: str, prefix: str) -> str:
    raw = str(value or "").strip()
    normalized_prefix = str(prefix or "").strip().upper()
    if not raw or not normalized_prefix:
        return raw
    if raw.upper().startswith(normalized_prefix):
        return raw[len(normalized_prefix):]
    return raw


def infer_host_comic_platform(comic_id: str, comic_record: Dict[str, Any] | None = None) -> str:
    raw_id = str(comic_id or "").strip()
    upper_id = raw_id.upper()
    for prefix in ("LOCAL", "JM", "PK"):
        if upper_id.startswith(prefix):
            return prefix

    record = dict(comic_record or {})
    platform = str(record.get("platform") or "").strip().upper()
    if platform in {"LOCAL", "JM", "PK"}:
        return platform

    cover_path = str(record.get("cover_path") or "").strip().upper()
    for prefix in ("JM", "PK"):
        marker = f"/STATIC/COVER/{prefix}/"
        if marker in cover_path:
            return prefix

    relative_path = str(record.get("storage_path_relative") or "").strip().replace("\\", "/")
    for prefix in ("JM", "PK", "local"):
        marker = f"comic/{prefix}/"
        if relative_path.startswith(marker):
            return prefix.upper()

    return ""


def infer_existing_host_comic_dir(
    comic_id: str,
    comic_record: Dict[str, Any] | None = None,
    *,
    comic_root: str,
    local_root: str,
) -> str:
    record = dict(comic_record or {})
    platform = infer_host_comic_platform(comic_id, record)
    raw_id = str(comic_id or "").strip()

    if platform == "LOCAL":
        stored_dir_name = str(record.get("local_asset_dir_name") or "").strip()
        candidates = []
        if stored_dir_name:
            candidates.append(os.path.join(local_root, stored_dir_name))
            candidates.append(os.path.join(local_root, _normalize_fs_name(stored_dir_name)))
        if raw_id:
            candidates.append(os.path.join(local_root, raw_id))

        for candidate in candidates:
            if candidate and os.path.isdir(candidate):
                return os.path.abspath(candidate)
        return ""

    if platform == "JM":
        original_id = _strip_known_prefix(raw_id, "JM")
        if not original_id:
            return ""
        candidate = os.path.join(comic_root, "JM", original_id)
        if os.path.isdir(candidate):
            return os.path.abspath(candidate)
        return ""

    if platform == "PK":
        author = str(record.get("author") or record.get("creator") or "").strip()
        title = str(record.get("title") or "").strip()
        if not author or not title:
            return ""

        root_candidates = [
            os.path.join(comic_root, "PK"),
            os.path.join(comic_root, "PK", "comics"),
        ]
        for root_dir in root_candidates:
            if not os.path.isdir(root_dir):
                continue

            direct_candidates = [
                os.path.join(root_dir, author, title),
                os.path.join(root_dir, _normalize_fs_name(author), _normalize_fs_name(title)),
            ]
            for candidate in direct_candidates:
                if os.path.isdir(candidate):
                    return os.path.abspath(candidate)

            matched_author = _find_matching_child_dir(root_dir, author)
            if not matched_author:
                continue
            author_dir = os.path.join(root_dir, matched_author)
            matched_title = _find_matching_child_dir(author_dir, title)
            if not matched_title:
                continue
            resolved = os.path.join(author_dir, matched_title)
            if os.path.isdir(resolved):
                return os.path.abspath(resolved)

        return ""

    return ""


def build_host_recommendation_cache_dir(
    comic_id: str,
    comic_record: Dict[str, Any] | None = None,
    *,
    cache_root: str,
) -> str:
    record = dict(comic_record or {})
    platform = infer_host_comic_platform(comic_id, record)
    raw_id = str(comic_id or "").strip()

    if platform == "JM":
        original_id = _strip_known_prefix(raw_id, "JM")
        if not original_id:
            return ""
        return os.path.abspath(os.path.join(cache_root, "JM", original_id))

    if platform == "PK":
        author = str(record.get("author") or record.get("creator") or "").strip()
        title = str(record.get("title") or "").strip()
        if not author or not title:
            return ""
        return os.path.abspath(
            os.path.join(
                cache_root,
                "PK",
                _normalize_fs_name(author),
                _normalize_fs_name(title),
            )
        )

    return ""


def infer_existing_host_recommendation_cache_dir(
    comic_id: str,
    comic_record: Dict[str, Any] | None = None,
    *,
    cache_root: str,
) -> str:
    record = dict(comic_record or {})
    platform = infer_host_comic_platform(comic_id, record)
    canonical = build_host_recommendation_cache_dir(
        comic_id,
        record,
        cache_root=cache_root,
    )
    if platform == "JM":
        if canonical and os.path.isdir(canonical):
            return canonical
        return ""

    if platform == "PK":
        author = str(record.get("author") or record.get("creator") or "").strip()
        title = str(record.get("title") or "").strip()
        if not author or not title:
            return ""

        root_candidates = [
            os.path.join(cache_root, "PK"),
            os.path.join(cache_root, "PK", "comics"),
        ]
        for root_dir in root_candidates:
            if not os.path.isdir(root_dir):
                continue

            direct_candidates = [
                os.path.join(root_dir, author, title),
                os.path.join(root_dir, _normalize_fs_name(author), _normalize_fs_name(title)),
            ]
            for candidate in direct_candidates:
                if os.path.isdir(candidate):
                    return os.path.abspath(candidate)

            matched_author = _find_matching_child_dir(root_dir, author)
            if not matched_author:
                continue
            author_dir = os.path.join(root_dir, matched_author)
            matched_title = _find_matching_child_dir(author_dir, title)
            if not matched_title:
                continue
            resolved = os.path.join(author_dir, matched_title)
            if os.path.isdir(resolved):
                return os.path.abspath(resolved)
        return ""

    return ""


def infer_host_video_platform(video_data: Dict[str, Any] | None = None) -> str:
    raw = dict(video_data or {})

    plugin_id = str(raw.get("plugin_id") or "").strip().lower()
    if plugin_id in _HOST_VIDEO_PLUGIN_PLATFORM_MAP:
        return _HOST_VIDEO_PLUGIN_PLATFORM_MAP[plugin_id]

    platform = str(raw.get("platform") or "").strip().upper()
    if platform in {"JAVDB", "JAVBUS", "MISSAV", "LOCAL"}:
        return platform

    candidate_values: Iterable[str] = (
        str(raw.get("id") or "").strip(),
        str(raw.get("cover_path") or "").strip(),
        str(raw.get("storage_path_relative") or "").strip(),
    )
    upper_values = [value.upper() for value in candidate_values if value]

    for value in upper_values:
        if value.startswith("JAVDB") or "/STATIC/COVER/JAVDB/" in value or value.startswith("VIDEO/JAVDB/"):
            return "JAVDB"
        if value.startswith("JAVBUS") or "/STATIC/COVER/JAVBUS/" in value or value.startswith("VIDEO/JAVBUS/"):
            return "JAVBUS"
        if value.startswith("MISSAV") or "/STATIC/COVER/MISSAV/" in value or value.startswith("VIDEO/MISSAV/"):
            return "MISSAV"
        if value.startswith("LOCAL") or value.startswith("VIDEO/LOCAL/"):
            return "LOCAL"

    return ""


def merge_host_video_display(video_data: Dict[str, Any] | None = None) -> Dict[str, Any]:
    raw = dict(video_data or {})
    platform = infer_host_video_platform(raw)
    defaults = _HOST_VIDEO_DISPLAY_DEFAULTS.get(platform) or _HOST_VIDEO_DEFAULT_DISPLAY
    if not defaults:
        return {}

    display = deepcopy(raw.get("display") or {})
    cover = dict(display.get("cover") or {})
    changed = False

    if not str(cover.get("aspect_ratio") or "").strip():
        cover["aspect_ratio"] = defaults["aspect_ratio"]
        changed = True
    if not str(cover.get("mobile_aspect_ratio") or "").strip():
        cover["mobile_aspect_ratio"] = defaults.get("mobile_aspect_ratio") or cover.get("aspect_ratio")
        changed = True
    if not str(cover.get("fit") or "").strip() and str(defaults.get("fit") or "").strip():
        cover["fit"] = defaults["fit"]
        changed = True
    if changed:
        display["cover"] = cover

    badge = dict(display.get("badge") or {})
    if platform and not str(badge.get("label") or "").strip():
        badge["label"] = platform
        badge.setdefault("show_platform_label", True)
        display["badge"] = badge
        changed = True

    return {"display": display} if changed else {}
