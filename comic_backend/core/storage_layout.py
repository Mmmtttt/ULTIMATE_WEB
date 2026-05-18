import os

from core.config_paths import resolve_configured_data_dir


DATA_DIR = resolve_configured_data_dir()
META_DIR = os.path.join(DATA_DIR, "meta_data")
STATIC_DIR = os.path.join(DATA_DIR, "static")
COVER_DIR = os.path.join(STATIC_DIR, "cover")
LOGS_DIR = os.path.join(DATA_DIR, "logs")
CACHE_ROOT_DIR = os.path.join(DATA_DIR, "cache")
RECOMMENDATION_CACHE_DIR = os.path.join(DATA_DIR, "recommendation_cache")

COMIC_DIR = os.path.join(DATA_DIR, "comic")
VIDEO_DIR = os.path.join(DATA_DIR, "video")
PICTURES_DIR = COMIC_DIR

COMIC_PICTURES_DIR = COMIC_DIR
COMIC_RECOMMENDATION_CACHE_DIR = os.path.join(RECOMMENDATION_CACHE_DIR, "comic")
COMIC_CACHE_DIR = os.path.join(CACHE_ROOT_DIR, "comic")

VIDEO_PICTURES_DIR = VIDEO_DIR
VIDEO_RECOMMENDATION_CACHE_DIR = os.path.join(RECOMMENDATION_CACHE_DIR, "video")
VIDEO_CACHE_DIR = os.path.join(CACHE_ROOT_DIR, "video")

LOCAL_PICTURES_DIR = os.path.join(COMIC_DIR, "local")
LOCAL_VIDEO_PICTURES_DIR = os.path.join(VIDEO_DIR, "LOCAL")
LOCAL_VIDEO_COVER_DIR = os.path.join(COVER_DIR, "LOCAL")


def normalize_to_data_dir(path_value, default_relative=""):
    if path_value is None or str(path_value).strip() == "":
        path_value = default_relative

    raw = os.path.expandvars(os.path.expanduser(str(path_value).strip()))
    if os.path.isabs(raw):
        return os.path.abspath(raw)

    normalized = raw.replace("\\", "/")
    parts = [p for p in normalized.split("/") if p and p not in (".", "..")]
    lowered = [p.lower() for p in parts]

    if "data" in lowered:
        data_idx = lowered.index("data")
        parts = parts[data_idx + 1 :]

    return os.path.abspath(os.path.join(DATA_DIR, *parts))


def _iter_protocol_platform_specs():
    try:
        from protocol.gateway import get_protocol_gateway
    except Exception:
        return []

    try:
        manifests = list(get_protocol_gateway().list_manifests())
    except Exception:
        return []

    specs = []
    seen = set()
    for manifest in manifests:
        identity = dict(getattr(manifest, "identity", {}) or {})
        host_prefix = str(
            identity.get("host_id_prefix")
            or identity.get("platform_label")
            or getattr(manifest, "config_key", "")
            or getattr(manifest, "name", "")
            or ""
        ).strip().upper()
        media_types = {
            str(item or "").strip().lower()
            for item in (getattr(manifest, "media_types", []) or [])
            if str(item or "").strip()
        }
        if not host_prefix or not media_types:
            continue
        key = (host_prefix, tuple(sorted(media_types)))
        if key in seen:
            continue
        seen.add(key)
        specs.append(
            {
                "host_prefix": host_prefix,
                "media_types": sorted(media_types),
                "plugin_id": str(getattr(manifest, "plugin_id", "") or "").strip(),
            }
        )
    return specs


def list_protocol_platform_storage_dirs():
    dirs = []
    for spec in _iter_protocol_platform_specs():
        host_prefix = str(spec.get("host_prefix") or "").strip().upper()
        media_types = {str(item or "").strip().lower() for item in (spec.get("media_types") or [])}
        if not host_prefix:
            continue
        if "comic" in media_types:
            dirs.extend(
                [
                    os.path.join(COMIC_DIR, host_prefix),
                    os.path.join(COVER_DIR, host_prefix),
                    os.path.join(COMIC_RECOMMENDATION_CACHE_DIR, host_prefix),
                ]
            )
        if "video" in media_types:
            dirs.extend(
                [
                    os.path.join(VIDEO_DIR, host_prefix),
                    os.path.join(COVER_DIR, host_prefix),
                    os.path.join(VIDEO_RECOMMENDATION_CACHE_DIR, host_prefix),
                ]
            )
    return dirs


def list_platform_cover_dirs(media_type: str = ""):
    normalized_media_type = str(media_type or "").strip().lower()
    cover_dirs = []
    seen = set()

    for spec in _iter_protocol_platform_specs():
        host_prefix = str(spec.get("host_prefix") or "").strip().upper()
        media_types = {str(item or "").strip().lower() for item in (spec.get("media_types") or [])}
        if not host_prefix:
            continue
        if normalized_media_type and normalized_media_type not in media_types:
            continue
        cover_dir = os.path.join(COVER_DIR, host_prefix)
        if cover_dir in seen:
            continue
        seen.add(cover_dir)
        cover_dirs.append(cover_dir)

    if normalized_media_type in {"", "video"} and LOCAL_VIDEO_COVER_DIR not in seen:
        seen.add(LOCAL_VIDEO_COVER_DIR)
        cover_dirs.append(LOCAL_VIDEO_COVER_DIR)

    if cover_dirs:
        return cover_dirs

    if os.path.isdir(COVER_DIR):
        for entry in os.listdir(COVER_DIR):
            candidate = os.path.join(COVER_DIR, entry)
            if not os.path.isdir(candidate):
                continue
            if candidate in seen:
                continue
            seen.add(candidate)
            cover_dirs.append(candidate)

    if normalized_media_type in {"", "video"} and LOCAL_VIDEO_COVER_DIR not in seen:
        cover_dirs.append(LOCAL_VIDEO_COVER_DIR)

    return cover_dirs


def ensure_base_dirs():
    dirs = [
        DATA_DIR,
        META_DIR,
        COMIC_DIR,
        VIDEO_DIR,
        STATIC_DIR,
        COVER_DIR,
        CACHE_ROOT_DIR,
        RECOMMENDATION_CACHE_DIR,
        LOGS_DIR,
    ]
    for directory in dirs:
        os.makedirs(directory, exist_ok=True)


def ensure_platform_dirs():
    protocol_dirs = list_protocol_platform_storage_dirs()
    dirs = [
        LOCAL_PICTURES_DIR,
        LOCAL_VIDEO_PICTURES_DIR,
        LOCAL_VIDEO_COVER_DIR,
    ]
    if protocol_dirs:
        dirs.extend(protocol_dirs)
    else:
        for root in (
            COMIC_PICTURES_DIR,
            VIDEO_PICTURES_DIR,
            COVER_DIR,
            COMIC_RECOMMENDATION_CACHE_DIR,
            VIDEO_RECOMMENDATION_CACHE_DIR,
        ):
            if not os.path.isdir(root):
                continue
            for entry in os.listdir(root):
                candidate = os.path.join(root, entry)
                if os.path.isdir(candidate):
                    dirs.append(candidate)
    deduped_dirs = []
    seen = set()
    for directory in dirs:
        normalized = os.path.abspath(directory)
        if normalized in seen:
            continue
        seen.add(normalized)
        deduped_dirs.append(normalized)
    for directory in deduped_dirs:
        os.makedirs(directory, exist_ok=True)


def ensure_content_type_dirs():
    dirs = [
        COMIC_PICTURES_DIR,
        COMIC_RECOMMENDATION_CACHE_DIR,
        COMIC_CACHE_DIR,
        VIDEO_PICTURES_DIR,
        VIDEO_RECOMMENDATION_CACHE_DIR,
        VIDEO_CACHE_DIR,
    ]
    for directory in dirs:
        os.makedirs(directory, exist_ok=True)


def ensure_storage_layout():
    ensure_base_dirs()
    ensure_platform_dirs()
    ensure_content_type_dirs()

