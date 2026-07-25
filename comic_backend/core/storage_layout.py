import os
import threading

from core.config_paths import resolve_configured_data_dir, _load_server_config


# ========== 空间模式常量 ==========
SPACE_MODE_PRIVATE = "private"
SPACE_MODE_NORMAL = "normal"

# 线程局部存储 - 当前线程的空间模式
_thread_local = threading.local()


def get_current_space_mode() -> str:
    """获取当前线程的空间模式，默认 normal"""
    return getattr(_thread_local, "space_mode", SPACE_MODE_NORMAL)


def set_current_space_mode(mode: str):
    """设置当前线程的空间模式"""
    _thread_local.space_mode = mode


# ========== 各空间的根目录配置 ==========
# 正常空间（默认/主空间）- 启动时解析
_NORMAL_DATA_DIR = resolve_configured_data_dir()

# 隐私空间目录 - 从配置读取，默认在正常空间旁边
def _resolve_private_data_dir() -> str:
    try:
        auth_cfg = (_load_server_config() or {}).get("auth", {}) or {}
        private_dir = str(auth_cfg.get("private_data_dir", "")).strip()
        if private_dir:
            if os.path.isabs(private_dir):
                return os.path.abspath(private_dir)
            parent = os.path.dirname(_NORMAL_DATA_DIR)
            return os.path.abspath(os.path.join(parent, private_dir))
    except Exception:
        pass
    parent = os.path.dirname(_NORMAL_DATA_DIR)
    base = os.path.basename(_NORMAL_DATA_DIR)
    return os.path.join(parent, f"{base}_private")


_PRIVATE_DATA_DIR = None


def _get_private_data_dir() -> str:
    global _PRIVATE_DATA_DIR
    if _PRIVATE_DATA_DIR is None:
        _PRIVATE_DATA_DIR = _resolve_private_data_dir()
    return _PRIVATE_DATA_DIR


# ========== 动态获取函数 ==========

def get_data_dir(mode: str = None) -> str:
    if mode is None:
        mode = get_current_space_mode()
    if mode == SPACE_MODE_PRIVATE:
        return _get_private_data_dir()
    return _NORMAL_DATA_DIR


def get_meta_dir(mode: str = None) -> str:
    return os.path.join(get_data_dir(mode), "meta_data")


def get_static_dir(mode: str = None) -> str:
    return os.path.join(get_data_dir(mode), "static")


def get_cover_dir(mode: str = None) -> str:
    return os.path.join(get_static_dir(mode), "cover")


def get_logs_dir(mode: str = None) -> str:
    return os.path.join(get_data_dir(mode), "logs")


def get_cache_root_dir(mode: str = None) -> str:
    return os.path.join(get_data_dir(mode), "cache")


def get_recommendation_cache_dir(mode: str = None) -> str:
    return os.path.join(get_data_dir(mode), "recommendation_cache")


def get_comic_dir(mode: str = None) -> str:
    return os.path.join(get_data_dir(mode), "comic")


def get_video_dir(mode: str = None) -> str:
    return os.path.join(get_data_dir(mode), "video")


def get_pictures_dir(mode: str = None) -> str:
    return get_comic_dir(mode)


def get_comic_pictures_dir(mode: str = None) -> str:
    return get_comic_dir(mode)


def get_comic_recommendation_cache_dir(mode: str = None) -> str:
    return os.path.join(get_recommendation_cache_dir(mode), "comic")


def get_comic_cache_dir(mode: str = None) -> str:
    return os.path.join(get_cache_root_dir(mode), "comic")


def get_video_pictures_dir(mode: str = None) -> str:
    return get_video_dir(mode)


def get_video_recommendation_cache_dir(mode: str = None) -> str:
    return os.path.join(get_recommendation_cache_dir(mode), "video")


def get_video_cache_dir(mode: str = None) -> str:
    return os.path.join(get_cache_root_dir(mode), "video")


def get_local_pictures_dir(mode: str = None) -> str:
    return os.path.join(get_comic_dir(mode), "local")


def get_local_video_pictures_dir(mode: str = None) -> str:
    return os.path.join(get_video_dir(mode), "LOCAL")


def get_local_video_cover_dir(mode: str = None) -> str:
    return os.path.join(get_cover_dir(mode), "LOCAL")


# ========== 向后兼容的"动态常量" ==========
# 通过模块级 __getattr__ 实现动态访问：
# 当代码访问 storage_layout.DATA_DIR 时，会自动返回当前线程对应空间的路径
# 这样所有现有代码无需修改，自动适配当前空间模式

_DYNAMIC_NAMES = {
    "DATA_DIR": get_data_dir,
    "META_DIR": get_meta_dir,
    "STATIC_DIR": get_static_dir,
    "COVER_DIR": get_cover_dir,
    "LOGS_DIR": get_logs_dir,
    "CACHE_ROOT_DIR": get_cache_root_dir,
    "RECOMMENDATION_CACHE_DIR": get_recommendation_cache_dir,
    "COMIC_DIR": get_comic_dir,
    "VIDEO_DIR": get_video_dir,
    "PICTURES_DIR": get_pictures_dir,
    "COMIC_PICTURES_DIR": get_comic_pictures_dir,
    "COMIC_RECOMMENDATION_CACHE_DIR": get_comic_recommendation_cache_dir,
    "COMIC_CACHE_DIR": get_comic_cache_dir,
    "VIDEO_PICTURES_DIR": get_video_pictures_dir,
    "VIDEO_RECOMMENDATION_CACHE_DIR": get_video_recommendation_cache_dir,
    "VIDEO_CACHE_DIR": get_video_cache_dir,
    "LOCAL_PICTURES_DIR": get_local_pictures_dir,
    "LOCAL_VIDEO_PICTURES_DIR": get_local_video_pictures_dir,
    "LOCAL_VIDEO_COVER_DIR": get_local_video_cover_dir,
}


def __getattr__(name):
    """模块级动态属性访问 - 让常量自动适配当前线程的空间模式"""
    if name in _DYNAMIC_NAMES:
        return _DYNAMIC_NAMES[name]()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


# ========== 工具函数 ==========

def normalize_to_data_dir(path_value, default_relative="", mode: str = None):
    if path_value is None or str(path_value).strip() == "":
        path_value = default_relative

    data_dir = get_data_dir(mode)
    raw = os.path.expandvars(os.path.expanduser(str(path_value).strip()))
    if os.path.isabs(raw):
        return os.path.abspath(raw)

    normalized = raw.replace("\\", "/")
    parts = [p for p in normalized.split("/") if p and p not in (".", "..")]
    lowered = [p.lower() for p in parts]

    if "data" in lowered:
        data_idx = lowered.index("data")
        parts = parts[data_idx + 1 :]

    return os.path.abspath(os.path.join(data_dir, *parts))


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


def list_protocol_platform_storage_dirs(mode: str = None):
    dirs = []
    comic_dir = get_comic_dir(mode)
    video_dir = get_video_dir(mode)
    cover_dir = get_cover_dir(mode)
    comic_rec_cache_dir = get_comic_recommendation_cache_dir(mode)
    video_rec_cache_dir = get_video_recommendation_cache_dir(mode)

    for spec in _iter_protocol_platform_specs():
        host_prefix = str(spec.get("host_prefix") or "").strip().upper()
        media_types = {str(item or "").strip().lower() for item in (spec.get("media_types") or [])}
        if not host_prefix:
            continue
        if "comic" in media_types:
            dirs.extend(
                [
                    os.path.join(comic_dir, host_prefix),
                    os.path.join(cover_dir, host_prefix),
                    os.path.join(comic_rec_cache_dir, host_prefix),
                ]
            )
        if "video" in media_types:
            dirs.extend(
                [
                    os.path.join(video_dir, host_prefix),
                    os.path.join(cover_dir, host_prefix),
                    os.path.join(video_rec_cache_dir, host_prefix),
                ]
            )
    return dirs


def list_platform_cover_dirs(media_type: str = "", mode: str = None):
    normalized_media_type = str(media_type or "").strip().lower()
    cover_dirs = []
    seen = set()
    cover_dir = get_cover_dir(mode)
    local_video_cover_dir = get_local_video_cover_dir(mode)

    for spec in _iter_protocol_platform_specs():
        host_prefix = str(spec.get("host_prefix") or "").strip().upper()
        media_types = {str(item or "").strip().lower() for item in (spec.get("media_types") or [])}
        if not host_prefix:
            continue
        if normalized_media_type and normalized_media_type not in media_types:
            continue
        cd = os.path.join(cover_dir, host_prefix)
        if cd in seen:
            continue
        seen.add(cd)
        cover_dirs.append(cd)

    if normalized_media_type in {"", "video"} and local_video_cover_dir not in seen:
        seen.add(local_video_cover_dir)
        cover_dirs.append(local_video_cover_dir)

    if cover_dirs:
        return cover_dirs

    if os.path.isdir(cover_dir):
        for entry in os.listdir(cover_dir):
            candidate = os.path.join(cover_dir, entry)
            if not os.path.isdir(candidate):
                continue
            if candidate in seen:
                continue
            seen.add(candidate)
            cover_dirs.append(candidate)

    if normalized_media_type in {"", "video"} and local_video_cover_dir not in seen:
        cover_dirs.append(local_video_cover_dir)

    return cover_dirs


def ensure_base_dirs(mode: str = None):
    dirs = [
        get_data_dir(mode),
        get_meta_dir(mode),
        get_comic_dir(mode),
        get_video_dir(mode),
        get_static_dir(mode),
        get_cover_dir(mode),
        get_cache_root_dir(mode),
        get_recommendation_cache_dir(mode),
        get_logs_dir(mode),
    ]
    for directory in dirs:
        os.makedirs(directory, exist_ok=True)


def ensure_platform_dirs(mode: str = None):
    protocol_dirs = list_protocol_platform_storage_dirs(mode)
    dirs = [
        get_local_pictures_dir(mode),
        get_local_video_pictures_dir(mode),
        get_local_video_cover_dir(mode),
    ]
    if protocol_dirs:
        dirs.extend(protocol_dirs)
    else:
        for root in (
            get_comic_pictures_dir(mode),
            get_video_pictures_dir(mode),
            get_cover_dir(mode),
            get_comic_recommendation_cache_dir(mode),
            get_video_recommendation_cache_dir(mode),
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


def ensure_content_type_dirs(mode: str = None):
    dirs = [
        get_comic_pictures_dir(mode),
        get_comic_recommendation_cache_dir(mode),
        get_comic_cache_dir(mode),
        get_video_pictures_dir(mode),
        get_video_recommendation_cache_dir(mode),
        get_video_cache_dir(mode),
    ]
    for directory in dirs:
        os.makedirs(directory, exist_ok=True)


def ensure_storage_layout(mode: str = None):
    ensure_base_dirs(mode)
    ensure_platform_dirs(mode)
    ensure_content_type_dirs(mode)
