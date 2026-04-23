from enum import Enum
import os
from typing import Any, Dict, List, Optional, Tuple


class Platform(Enum):
    """Legacy compatibility enum.

    Runtime code should prefer protocol platform strings from plugin manifests.
    """

    JM = "JM"
    PK = "PK"
    JAVDB = "JAVDB"
    JAVBUS = "JAVBUS"


LEGACY_PLATFORM_PREFIXES: Dict[str, str] = {
    "JM": "JM",
    "PK": "PK",
    "JAVDB": "JAVDB",
    "JAVBUS": "JAVBUS",
}

LEGACY_PLATFORM_NAMES: Dict[str, str] = {
    "JM": "JMComic",
    "PK": "PK",
    "JAVDB": "JAVDB",
    "JAVBUS": "JavBus",
}

LEGACY_PLATFORM_DOWNLOAD_DIRS: Dict[str, str] = {
    "JM": "JM",
    "PK": "PK",
    "JAVDB": "JAVDB",
    "JAVBUS": "JAVBUS",
}

LEGACY_PLATFORM_COVER_URLS: Dict[str, Optional[str]] = {
    "JM": "https://cdn-msp3.18comic.vip/media/albums/{original_id}.jpg",
    "PK": None,
    "JAVDB": None,
    "JAVBUS": None,
}

LEGACY_PLATFORM_IMAGE_URLS: Dict[str, Optional[str]] = {
    "JM": "https://cdn-msp.jmapinodeudzn.net/media/photos/{original_id}/{page:05d}.webp",
    "PK": None,
    "JAVDB": None,
    "JAVBUS": None,
}

LEGACY_COMIC_PLATFORM_LABELS = ["JM", "PK"]
LEGACY_VIDEO_PLATFORM_LABELS = ["JAVDB", "JAVBUS"]

# Legacy aliases kept for backwards-compatible imports.
PLATFORM_PREFIXES = {
    Platform.JM: LEGACY_PLATFORM_PREFIXES["JM"],
    Platform.PK: LEGACY_PLATFORM_PREFIXES["PK"],
    Platform.JAVDB: LEGACY_PLATFORM_PREFIXES["JAVDB"],
    Platform.JAVBUS: LEGACY_PLATFORM_PREFIXES["JAVBUS"],
}

PLATFORM_NAMES = {
    Platform.JM: LEGACY_PLATFORM_NAMES["JM"],
    Platform.PK: LEGACY_PLATFORM_NAMES["PK"],
    Platform.JAVDB: LEGACY_PLATFORM_NAMES["JAVDB"],
    Platform.JAVBUS: LEGACY_PLATFORM_NAMES["JAVBUS"],
}

PLATFORM_DOWNLOAD_DIRS = {
    Platform.JM: LEGACY_PLATFORM_DOWNLOAD_DIRS["JM"],
    Platform.PK: LEGACY_PLATFORM_DOWNLOAD_DIRS["PK"],
    Platform.JAVDB: LEGACY_PLATFORM_DOWNLOAD_DIRS["JAVDB"],
    Platform.JAVBUS: LEGACY_PLATFORM_DOWNLOAD_DIRS["JAVBUS"],
}

PLATFORM_COVER_URLS = {
    Platform.JM: LEGACY_PLATFORM_COVER_URLS["JM"],
    Platform.PK: LEGACY_PLATFORM_COVER_URLS["PK"],
    Platform.JAVDB: LEGACY_PLATFORM_COVER_URLS["JAVDB"],
    Platform.JAVBUS: LEGACY_PLATFORM_COVER_URLS["JAVBUS"],
}

PLATFORM_IMAGE_URLS = {
    Platform.JM: LEGACY_PLATFORM_IMAGE_URLS["JM"],
    Platform.PK: LEGACY_PLATFORM_IMAGE_URLS["PK"],
    Platform.JAVDB: LEGACY_PLATFORM_IMAGE_URLS["JAVDB"],
    Platform.JAVBUS: LEGACY_PLATFORM_IMAGE_URLS["JAVBUS"],
}

COMIC_PLATFORMS = [Platform.JM, Platform.PK]
VIDEO_PLATFORMS = [Platform.JAVDB, Platform.JAVBUS]


def _normalize_platform_name(platform: Any) -> str:
    return str(getattr(platform, "value", platform) or "").strip().upper()


def _coerce_platform(platform_name: Any) -> Optional[Platform]:
    normalized = _normalize_platform_name(platform_name)
    if not normalized:
        return None
    try:
        return Platform(normalized)
    except Exception:
        return None


def _resolve_manifest(platform_name: Any, media_type: Optional[str] = None):
    normalized_platform = _normalize_platform_name(platform_name)
    normalized_media_type = str(media_type or "").strip().lower() or None
    if not normalized_platform:
        return None

    try:
        from protocol.platform_meta import resolve_platform_manifest
    except Exception:
        return None

    try:
        return resolve_platform_manifest(
            normalized_platform,
            media_type=normalized_media_type,
        )
    except Exception:
        return None


def _resolve_platform_label(platform_name: Any, media_type: Optional[str] = None) -> str:
    normalized_platform = _normalize_platform_name(platform_name)
    manifest = _resolve_manifest(normalized_platform, media_type=media_type)
    if manifest is None:
        return normalized_platform

    try:
        from protocol.platform_meta import resolve_manifest_platform_label
    except Exception:
        return normalized_platform

    return resolve_manifest_platform_label(manifest, fallback=normalized_platform)


def _resolve_platform_prefix(platform_name: Any, media_type: Optional[str] = None) -> str:
    normalized_platform = _normalize_platform_name(platform_name)
    manifest = _resolve_manifest(normalized_platform, media_type=media_type)
    if manifest is not None:
        try:
            from protocol.platform_meta import resolve_manifest_host_prefix

            resolved = resolve_manifest_host_prefix(manifest, fallback=normalized_platform)
            if resolved:
                return str(resolved).strip().upper()
        except Exception:
            pass

    if normalized_platform in LEGACY_PLATFORM_PREFIXES:
        return LEGACY_PLATFORM_PREFIXES[normalized_platform]
    return normalized_platform


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

    if media_type == "comic":
        legacy_labels = LEGACY_COMIC_PLATFORM_LABELS
    elif media_type == "video":
        legacy_labels = LEGACY_VIDEO_PLATFORM_LABELS
    else:
        legacy_labels = list(LEGACY_PLATFORM_PREFIXES.keys())

    for label in legacy_labels:
        normalized_label = _normalize_platform_name(label)
        if normalized_label and normalized_label not in seen:
            seen.add(normalized_label)
            labels.append(normalized_label)

    return labels


def add_platform_prefix(platform: Any, original_id: str) -> str:
    normalized_original_id = str(original_id or "").strip()
    if not platform or not normalized_original_id:
        return normalized_original_id

    prefix = _resolve_platform_prefix(platform)
    if not prefix:
        return normalized_original_id

    if normalized_original_id.upper().startswith(prefix):
        return normalized_original_id

    return f"{prefix}{normalized_original_id}"


def remove_platform_prefix(comic_id: str) -> Tuple[Optional[str], str]:
    normalized_id = str(comic_id or "").strip()
    if not normalized_id:
        return None, normalized_id

    upper_id = normalized_id.upper()

    # 本地导入漫画 ID 归入漫画链路处理，默认平台优先读取协议顺序。
    if upper_id.startswith("LOCAL"):
        default_labels = _list_platform_labels(media_type="comic")
        default_platform = default_labels[0] if default_labels else ""
        return default_platform or None, normalized_id

    manifest_entries = sorted(
        _list_manifest_platform_entries(),
        key=lambda item: len(item[0]),
        reverse=True,
    )
    for prefix, label in manifest_entries:
        if upper_id.startswith(prefix):
            original_id = normalized_id[len(prefix):]
            return (label or prefix or None), original_id

    for platform_name, prefix in LEGACY_PLATFORM_PREFIXES.items():
        if upper_id.startswith(prefix):
            original_id = normalized_id[len(prefix):]
            return platform_name, original_id

    return None, normalized_id


def get_platform_from_id(comic_id: str) -> Optional[str]:
    platform, _ = remove_platform_prefix(comic_id)
    return platform


def get_original_id(comic_id: str) -> str:
    _, original_id = remove_platform_prefix(comic_id)
    return original_id


def get_platform_download_dir(platform: Any, base_dir: str) -> str:
    platform_dir = _resolve_platform_prefix(platform)
    if not platform_dir:
        return base_dir
    return os.path.join(base_dir, platform_dir)


def get_platform_cover_url(platform: Any, original_id: str) -> Optional[str]:
    url_template = LEGACY_PLATFORM_COVER_URLS.get(_normalize_platform_name(platform))
    if url_template:
        return url_template.format(original_id=original_id)
    return None


def get_platform_image_url(platform: Any, original_id: str, page: int) -> Optional[str]:
    url_template = LEGACY_PLATFORM_IMAGE_URLS.get(_normalize_platform_name(platform))
    if url_template:
        return url_template.format(original_id=original_id, page=page)
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
