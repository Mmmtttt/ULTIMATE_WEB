import os
from typing import Any, List, Optional, Tuple


def _normalize_platform_name(platform: Any) -> str:
    return str(getattr(platform, "value", platform) or "").strip().upper()


def _list_manifest_platform_entries(media_type: Optional[str] = None) -> List[Tuple[str, str]]:
    try:
        from protocol.gateway import get_protocol_gateway
    except Exception:
        return []

    try:
        manifests = get_protocol_gateway().list_manifests(
            media_type=str(media_type or "").strip().lower() or None
        )
    except Exception:
        return []

    entries: List[Tuple[str, str]] = []
    seen = set()
    for manifest in manifests:
        identity = dict(getattr(manifest, "identity", {}) or {})
        prefix = str(
            identity.get("host_id_prefix")
            or identity.get("platform_label")
            or getattr(manifest, "config_key", "")
            or getattr(manifest, "name", "")
            or ""
        ).strip().upper()
        label = str(
            identity.get("platform_label")
            or identity.get("host_id_prefix")
            or getattr(manifest, "config_key", "")
            or getattr(manifest, "name", "")
            or ""
        ).strip().upper()
        if not prefix or not label:
            continue
        entry = (prefix, label)
        if entry in seen:
            continue
        seen.add(entry)
        entries.append(entry)
    return entries


def _list_platform_labels(media_type: Optional[str] = None) -> List[str]:
    labels: List[str] = []
    seen = set()
    for _prefix, label in _list_manifest_platform_entries(media_type=media_type):
        if label and label not in seen:
            seen.add(label)
            labels.append(label)
    return labels


def _resolve_platform_prefix(platform_name: Any, media_type: Optional[str] = None) -> str:
    normalized = _normalize_platform_name(platform_name)
    if not normalized:
        return ""

    for prefix, label in _list_manifest_platform_entries(media_type=media_type):
        if normalized in {prefix, label}:
            return prefix
    return normalized


def add_platform_prefix(platform: Any, original_id: str) -> str:
    normalized_original = str(original_id or "").strip()
    if not normalized_original:
        return normalized_original

    prefix = _resolve_platform_prefix(platform)
    if not prefix:
        return normalized_original
    if normalized_original.upper().startswith(prefix):
        return normalized_original
    return f"{prefix}{normalized_original}"


def remove_platform_prefix(content_id: str) -> Tuple[Optional[str], str]:
    normalized_id = str(content_id or "").strip()
    if not normalized_id:
        return None, normalized_id

    upper_id = normalized_id.upper()
    if upper_id.startswith("LOCAL"):
        default_labels = _list_platform_labels(media_type="comic")
        return (default_labels[0] if default_labels else None), normalized_id

    manifest_entries = sorted(
        _list_manifest_platform_entries(),
        key=lambda item: len(item[0]),
        reverse=True,
    )
    for prefix, label in manifest_entries:
        if upper_id.startswith(prefix):
            return label, normalized_id[len(prefix):]

    return None, normalized_id


def get_platform_from_id(content_id: str) -> Optional[str]:
    platform, _ = remove_platform_prefix(content_id)
    return platform


def get_original_id(content_id: str) -> str:
    _, original_id = remove_platform_prefix(content_id)
    return original_id


def get_platform_download_dir(platform: Any, base_dir: str) -> str:
    platform_dir = _resolve_platform_prefix(platform)
    if not platform_dir:
        return base_dir
    return os.path.join(base_dir, platform_dir)


def get_platform_cover_url(platform: Any, original_id: str) -> Optional[str]:
    return None


def get_platform_image_url(platform: Any, original_id: str, page: int) -> Optional[str]:
    return None


def is_platform_supported(platform_name: str) -> bool:
    return _normalize_platform_name(platform_name) in set(_list_platform_labels())


def get_supported_platforms() -> list:
    return _list_platform_labels()


def get_comic_platforms() -> list:
    return _list_platform_labels(media_type="comic")


def get_video_platforms() -> list:
    return _list_platform_labels(media_type="video")


def is_comic_platform(platform_name: str) -> bool:
    return _normalize_platform_name(platform_name) in set(get_comic_platforms())


def is_video_platform(platform_name: str) -> bool:
    return _normalize_platform_name(platform_name) in set(get_video_platforms())
