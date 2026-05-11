from __future__ import annotations

import os
import re
from copy import deepcopy
from typing import Any, Dict, Iterable, List, Optional

from protocol.gateway import get_protocol_gateway
from protocol.platform_meta import (
    resolve_manifest_host_prefix,
    resolve_manifest_platform_label,
    split_prefixed_id,
)


_INVALID_FS_CHARS_PATTERN = re.compile(r'[\\/:*?"<>|]')
_TEMPLATE_FIELD_PATTERN = re.compile(r"{([^{}]+)}")
_VIDEO_DEFAULT_DISPLAY = {
    "aspect_ratio": "16 / 9",
    "mobile_aspect_ratio": "16 / 9",
    "fit": "cover",
}
_COMMON_FIELD_ALIASES = {
    "author": ("author", "creator"),
    "creator": ("creator", "author"),
    "title": ("title", "name"),
    "name": ("name", "title"),
}


def _deep_merge(base: Any, override: Any) -> Any:
    if isinstance(base, dict) and isinstance(override, dict):
        merged = {key: deepcopy(value) for key, value in base.items()}
        for key, value in override.items():
            merged[key] = _deep_merge(merged.get(key), value)
        return merged
    if override is None:
        return deepcopy(base)
    return deepcopy(override)


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


def _stringify(value: Any) -> str:
    return str(value or "").strip()


def _is_local_host_content(content_id: str, record: Dict[str, Any] | None = None) -> bool:
    raw_id = _stringify(content_id)
    if raw_id.upper().startswith("LOCAL"):
        return True

    payload = dict(record or {})
    if _stringify(payload.get("platform")).lower() == "local":
        return True

    relative_path = _stringify(payload.get("storage_path_relative")).replace("\\", "/").lower()
    if relative_path.startswith("comic/local/") or relative_path.startswith("video/local/"):
        return True

    return False


def _iter_manifests(media_type: str) -> list:
    try:
        return list(get_protocol_gateway().list_manifests(media_type=media_type))
    except Exception:
        return []


def _resolve_manifest_by_plugin_id(plugin_id: str):
    normalized_plugin_id = _stringify(plugin_id)
    if not normalized_plugin_id:
        return None
    try:
        return get_protocol_gateway().registry.get_manifest(normalized_plugin_id)
    except Exception:
        return None


def _resolve_manifest_by_lookup(lookup_name: str, media_type: str):
    normalized_lookup = _stringify(lookup_name)
    if not normalized_lookup:
        return None
    try:
        return get_protocol_gateway().get_manifest_by_lookup(
            normalized_lookup,
            media_type=media_type,
        )
    except Exception:
        return None


def _resolve_manifest_from_record(
    media_type: str,
    content_id: str = "",
    record: Dict[str, Any] | None = None,
):
    payload = dict(record or {})

    plugin_id = _stringify(payload.get("plugin_id"))
    manifest = _resolve_manifest_by_plugin_id(plugin_id)
    if manifest is not None:
        return manifest

    explicit_platform = _stringify(payload.get("platform"))
    if explicit_platform and explicit_platform.lower() != "local":
        manifest = _resolve_manifest_by_lookup(explicit_platform, media_type)
        if manifest is not None:
            return manifest

    plugin_name = _stringify(payload.get("plugin_name"))
    manifest = _resolve_manifest_by_lookup(plugin_name, media_type)
    if manifest is not None:
        return manifest

    normalized_id = _stringify(content_id)
    if normalized_id and not normalized_id.upper().startswith("LOCAL"):
        _platform_key, _original_id, parsed_manifest = split_prefixed_id(
            normalized_id,
            media_type=media_type,
        )
        if parsed_manifest is not None:
            return parsed_manifest

    path_candidates: Iterable[str] = (
        _stringify(payload.get("storage_path_relative")),
        _stringify(payload.get("cover_path")),
        _stringify(payload.get("cover_path_local")),
        _stringify(payload.get("local_video_path")),
        normalized_id,
    )
    upper_paths = [candidate.replace("\\", "/").upper() for candidate in path_candidates if candidate]

    prefix_markers: Dict[str, tuple[str, ...]] = {
        "comic": (
            "COMIC/{host_prefix}/",
            "RECOMMENDATION_CACHE/COMIC/{host_prefix}/",
            "/STATIC/COVER/{host_prefix}/",
        ),
        "video": (
            "VIDEO/{host_prefix}/",
            "RECOMMENDATION_CACHE/VIDEO/{host_prefix}/",
            "/STATIC/COVER/{host_prefix}/",
        ),
    }

    for candidate_manifest in _iter_manifests(media_type):
        host_prefix = resolve_manifest_host_prefix(candidate_manifest)
        if not host_prefix:
            continue
        rendered_markers = [
            marker.format(host_prefix=host_prefix.upper())
            for marker in prefix_markers.get(media_type, ())
        ]
        for upper_path in upper_paths:
            if upper_path.startswith(host_prefix.upper()):
                return candidate_manifest
            if any(marker in upper_path or upper_path.startswith(marker) for marker in rendered_markers):
                return candidate_manifest

    return None


def _resolve_content_context(
    media_type: str,
    content_id: str = "",
    record: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    payload = dict(record or {})
    normalized_id = _stringify(content_id)
    local_content = _is_local_host_content(normalized_id, payload)
    manifest = None if local_content else _resolve_manifest_from_record(media_type, normalized_id, payload)
    host_prefix = resolve_manifest_host_prefix(manifest) if manifest is not None else ""
    platform_label = resolve_manifest_platform_label(manifest, fallback=host_prefix) if manifest is not None else ""
    original_id = normalized_id

    if manifest is not None and normalized_id:
        parsed_platform, parsed_original_id, parsed_manifest = split_prefixed_id(
            normalized_id,
            media_type=media_type,
        )
        if parsed_manifest is not None and parsed_manifest.plugin_id == manifest.plugin_id:
            original_id = _stringify(parsed_original_id) or normalized_id
            if not platform_label:
                platform_label = _stringify(parsed_platform).upper()

    return {
        "manifest": manifest,
        "host_prefix": _stringify(host_prefix).upper(),
        "platform_label": _stringify(platform_label).upper(),
        "original_id": _stringify(original_id),
        "local_content": local_content,
    }


def _list_template_values(raw_values: Any) -> list[str]:
    templates: List[str] = []
    for item in (raw_values or []):
        if isinstance(item, dict):
            template = _stringify(item.get("path"))
        else:
            template = _stringify(item)
        if template:
            templates.append(template.replace("\\", "/").strip("/"))
    return templates


def _list_path_templates(entry: Dict[str, Any], *, include_fallback: bool = False) -> list[str]:
    templates: List[str] = []
    primary_template = _stringify(entry.get("template")).replace("\\", "/").strip("/")
    if primary_template:
        templates.append(primary_template)
    templates.extend(_list_template_values(entry.get("path_templates") or []))
    if include_fallback:
        templates.extend(_list_template_values(entry.get("fallback_templates") or []))
    return templates


def _get_storage_resolution_entry(manifest, entry_key: str) -> Dict[str, Any]:
    storage = dict(getattr(manifest, "storage", {}) or {}) if manifest is not None else {}
    host_resolution = storage.get("host_resolution") or {}
    if isinstance(host_resolution, dict):
        entry = host_resolution.get(_stringify(entry_key)) or {}
        if isinstance(entry, dict) and entry:
            return dict(entry)

    if _stringify(entry_key) in {"comic_local_dir", "comic_preview_cache_dir"}:
        comic_dir = storage.get("comic_dir") or {}
        if isinstance(comic_dir, dict):
            normalized = dict(comic_dir)
            normalized.setdefault("_host_base_mode", "host_prefix_subdir")
            return normalized

    return {}


def _resolve_entry_base_root(manifest, base_root: str, entry: Dict[str, Any]) -> str:
    normalized_root = _stringify(base_root)
    if not normalized_root:
        return ""

    base_mode = _stringify((entry or {}).get("_host_base_mode")).lower()
    if base_mode == "host_prefix_subdir":
        host_prefix = resolve_manifest_host_prefix(manifest)
        if host_prefix:
            return os.path.join(normalized_root, host_prefix)

    return normalized_root


def _resolve_field_aliases(entry: Dict[str, Any]) -> Dict[str, tuple[str, ...]]:
    aliases: Dict[str, tuple[str, ...]] = dict(_COMMON_FIELD_ALIASES)
    raw_aliases = entry.get("field_aliases") or {}
    if not isinstance(raw_aliases, dict):
        return aliases

    for field_name, values in raw_aliases.items():
        normalized_field = _stringify(field_name)
        if not normalized_field:
            continue
        if isinstance(values, (list, tuple)):
            alias_values = tuple(_stringify(item) for item in values if _stringify(item))
        else:
            alias_values = tuple([_stringify(values)]) if _stringify(values) else ()
        if alias_values:
            aliases[normalized_field] = alias_values
    return aliases


def _build_template_context(
    content_id: str,
    record: Dict[str, Any] | None,
    manifest,
    entry: Dict[str, Any],
    *,
    media_type: str,
) -> Dict[str, str]:
    payload = dict(record or {})
    context = _resolve_content_context(media_type, content_id, payload)
    values: Dict[str, str] = {
        "id": _stringify(content_id),
        "original_id": _stringify(context.get("original_id")),
        "album_id": _stringify(context.get("original_id")) or _stringify(payload.get("album_id")),
        "host_prefix": _stringify(context.get("host_prefix")),
        "platform_label": _stringify(context.get("platform_label")),
        "plugin_id": _stringify(getattr(manifest, "plugin_id", "")),
        "config_key": _stringify(getattr(manifest, "config_key", "")),
    }

    for key, value in payload.items():
        if isinstance(value, (str, int, float)) and _stringify(value):
            values.setdefault(_stringify(key), _stringify(value))

    aliases = _resolve_field_aliases(entry)
    for field_name, field_aliases in aliases.items():
        if _stringify(values.get(field_name)):
            continue
        for alias in field_aliases:
            alias_value = _stringify(payload.get(alias))
            if alias_value:
                values[field_name] = alias_value
                break

    return values


def _render_template(template: str, values: Dict[str, str], *, normalize_dynamic_segments: bool) -> str:
    rendered = _stringify(template).replace("\\", "/").strip("/")
    if not rendered:
        return ""

    def replace(match: re.Match[str]) -> str:
        field_name = _stringify(match.group(1))
        value = _stringify(values.get(field_name))
        if not value:
            return ""
        if field_name == "host_prefix":
            return value.upper()
        return _normalize_fs_name(value) if normalize_dynamic_segments else value

    rendered = _TEMPLATE_FIELD_PATTERN.sub(replace, rendered)
    rendered = re.sub(r"/{2,}", "/", rendered).strip("/")
    return rendered


def _resolve_existing_dir_from_template(base_root: str, template: str, values: Dict[str, str]) -> str:
    if not base_root or not os.path.isdir(base_root):
        return ""

    for normalize_dynamic_segments in (False, True):
        relative_path = _render_template(
            template,
            values,
            normalize_dynamic_segments=normalize_dynamic_segments,
        )
        if relative_path:
            candidate = os.path.join(base_root, relative_path.replace("/", os.sep))
            if os.path.isdir(candidate):
                return os.path.abspath(candidate)

    current_dir = os.path.abspath(base_root)
    segments = [
        segment
        for segment in _stringify(template).replace("\\", "/").strip("/").split("/")
        if _stringify(segment)
    ]
    if not segments:
        return ""

    for raw_segment in segments:
        literal_segment = _render_template(
            raw_segment,
            values,
            normalize_dynamic_segments=False,
        )
        normalized_segment = _render_template(
            raw_segment,
            values,
            normalize_dynamic_segments=True,
        )

        if not literal_segment and not normalized_segment:
            return ""

        direct_candidates = [
            os.path.join(current_dir, literal_segment),
            os.path.join(current_dir, normalized_segment),
        ]
        matched_dir = ""
        for candidate in direct_candidates:
            if candidate and os.path.isdir(candidate):
                matched_dir = os.path.basename(candidate)
                break

        if not matched_dir:
            matched_dir = _find_matching_child_dir(
                current_dir,
                literal_segment or normalized_segment,
            )
        if not matched_dir:
            return ""
        current_dir = os.path.join(current_dir, matched_dir)

    return os.path.abspath(current_dir) if os.path.isdir(current_dir) else ""


def _build_dir_from_template(base_root: str, template: str, values: Dict[str, str]) -> str:
    if not base_root or not template:
        return ""
    relative_path = _render_template(
        template,
        values,
        normalize_dynamic_segments=True,
    )
    if not relative_path:
        return ""
    return os.path.abspath(os.path.join(base_root, relative_path.replace("/", os.sep)))


def _resolve_existing_manifest_dir(
    content_id: str,
    record: Dict[str, Any] | None,
    *,
    media_type: str,
    base_root: str,
    resolution_key: str,
) -> str:
    context = _resolve_content_context(media_type, content_id, record)
    manifest = context.get("manifest")
    if manifest is None:
        return ""

    entry = _get_storage_resolution_entry(manifest, resolution_key)
    templates = _list_path_templates(entry, include_fallback=True)
    if not templates:
        return ""

    values = _build_template_context(content_id, record, manifest, entry, media_type=media_type)
    resolved_base_root = _resolve_entry_base_root(manifest, base_root, entry)
    for template in templates:
        resolved = _resolve_existing_dir_from_template(resolved_base_root, template, values)
        if resolved:
            return resolved
    return ""


def _build_manifest_dir(
    content_id: str,
    record: Dict[str, Any] | None,
    *,
    media_type: str,
    base_root: str,
    resolution_key: str,
) -> str:
    context = _resolve_content_context(media_type, content_id, record)
    manifest = context.get("manifest")
    if manifest is None:
        return ""

    entry = _get_storage_resolution_entry(manifest, resolution_key)
    templates = _list_path_templates(entry, include_fallback=False)
    if not templates:
        return ""

    values = _build_template_context(content_id, record, manifest, entry, media_type=media_type)
    resolved_base_root = _resolve_entry_base_root(manifest, base_root, entry)
    return _build_dir_from_template(resolved_base_root, templates[0], values)


def infer_existing_host_comic_dir(
    comic_id: str,
    comic_record: Dict[str, Any] | None = None,
    *,
    comic_root: str,
    local_root: str,
) -> str:
    payload = dict(comic_record or {})
    raw_id = _stringify(comic_id)

    if _is_local_host_content(raw_id, payload):
        stored_dir_name = _stringify(payload.get("local_asset_dir_name"))
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

    return _resolve_existing_manifest_dir(
        raw_id,
        payload,
        media_type="comic",
        base_root=comic_root,
        resolution_key="comic_local_dir",
    )


def build_host_recommendation_cache_dir(
    comic_id: str,
    comic_record: Dict[str, Any] | None = None,
    *,
    cache_root: str,
) -> str:
    return _build_manifest_dir(
        comic_id,
        comic_record,
        media_type="comic",
        base_root=cache_root,
        resolution_key="comic_preview_cache_dir",
    )


def infer_existing_host_recommendation_cache_dir(
    comic_id: str,
    comic_record: Dict[str, Any] | None = None,
    *,
    cache_root: str,
) -> str:
    return _resolve_existing_manifest_dir(
        comic_id,
        comic_record,
        media_type="comic",
        base_root=cache_root,
        resolution_key="comic_preview_cache_dir",
    )


def infer_host_video_platform(video_data: Dict[str, Any] | None = None) -> str:
    raw = dict(video_data or {})
    video_id = _stringify(raw.get("id"))

    if _is_local_host_content(video_id, raw):
        return "LOCAL"

    manifest = _resolve_manifest_from_record("video", video_id, raw)
    if manifest is None:
        return ""
    return resolve_manifest_platform_label(manifest, fallback=resolve_manifest_host_prefix(manifest))


def merge_host_video_display(video_data: Dict[str, Any] | None = None) -> Dict[str, Any]:
    raw = dict(video_data or {})
    manifest = _resolve_manifest_from_record("video", _stringify(raw.get("id")), raw)
    display = dict(raw.get("display") or {})
    changed = False

    if manifest is not None:
        merged_display = _deep_merge(
            dict((manifest.presentation or {}).get("media_card") or {}),
            display,
        )
        if merged_display != display:
            display = merged_display if isinstance(merged_display, dict) else {}
            changed = True

    cover = dict(display.get("cover") or {})
    if not _stringify(cover.get("aspect_ratio")):
        cover["aspect_ratio"] = _VIDEO_DEFAULT_DISPLAY["aspect_ratio"]
        changed = True
    if not _stringify(cover.get("mobile_aspect_ratio")):
        cover["mobile_aspect_ratio"] = _stringify(cover.get("aspect_ratio")) or _VIDEO_DEFAULT_DISPLAY["mobile_aspect_ratio"]
        changed = True
    if not _stringify(cover.get("fit")):
        cover["fit"] = _VIDEO_DEFAULT_DISPLAY["fit"]
        changed = True
    if cover:
        display["cover"] = cover

    badge = dict(display.get("badge") or {})
    if not _stringify(badge.get("label")):
        badge_label = ""
        if manifest is not None:
            badge_label = resolve_manifest_platform_label(manifest, fallback=resolve_manifest_host_prefix(manifest))
        if not badge_label:
            badge_label = _stringify(raw.get("platform")) or _stringify(raw.get("plugin_name"))
        if badge_label:
            badge["label"] = badge_label
            badge.setdefault("show_platform_label", True)
            display["badge"] = badge
            changed = True

    return {"display": display} if changed else {}
