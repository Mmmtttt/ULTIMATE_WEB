import os
from core.config_paths import *  # noqa: F401,F403
from core.storage_layout import (  # noqa: F401
    get_data_dir, get_meta_dir, get_static_dir, get_cover_dir,
    get_logs_dir, get_cache_root_dir, get_recommendation_cache_dir,
    get_comic_dir, get_video_dir, get_pictures_dir,
    get_comic_pictures_dir, get_comic_recommendation_cache_dir,
    get_comic_cache_dir, get_video_pictures_dir,
    get_video_recommendation_cache_dir, get_video_cache_dir,
    get_local_pictures_dir, get_local_video_pictures_dir,
    get_local_video_cover_dir,
    set_current_space_mode, get_current_space_mode,
    SPACE_MODE_NORMAL, SPACE_MODE_PRIVATE,
    ensure_storage_layout, normalize_to_data_dir,
)


COVER_WIDTH = 800
COVER_QUALITY = 95
SUPPORTED_FORMATS = ['.jpg', '.jpeg', '.png', '.webp']

BACKUP_SUFFIX = ".bkp"

DEFAULT_PAGE_MODE = "up_down"
DEFAULT_BACKGROUND = "white"
DEFAULT_PRELOAD_NUM = 3

MIN_SCORE = 1
MAX_SCORE = 12
SCORE_PRECISION = 0.5

CACHE_MAX_AGE = 300


def _get_json_file(name):
    return os.path.join(get_meta_dir(), name)


_DYNAMIC_JSON_FILES = {
    "JSON_FILE": "comics_database.json",
    "RECOMMENDATION_JSON_FILE": "recommendations_database.json",
    "VIDEO_JSON_FILE": "videos_database.json",
    "VIDEO_RECOMMENDATION_JSON_FILE": "video_recommendations_database.json",
    "ACTOR_JSON_FILE": "actors_database.json",
    "AUTHOR_JSON_FILE": "authors_database.json",
    "TAGS_JSON_FILE": "tags_database.json",
    "LISTS_JSON_FILE": "lists_database.json",
    "USER_CONFIG_JSON_FILE": "user_config.json",
    "IMPORT_TASKS_JSON_FILE": "import_tasks.json",
    "RECOMMENDATION_CACHE_INDEX_FILE": "recommendation_cache_index.json",
    "UI_STATE_JSON_FILE": "ui_state_database.json",
}


_DYNAMIC_PROXY_NAMES = [
    "DATA_DIR", "META_DIR", "STATIC_DIR", "COVER_DIR", "LOGS_DIR",
    "CACHE_ROOT_DIR", "RECOMMENDATION_CACHE_DIR",
    "COMIC_DIR", "VIDEO_DIR", "PICTURES_DIR",
    "COMIC_PICTURES_DIR", "COMIC_RECOMMENDATION_CACHE_DIR", "COMIC_CACHE_DIR",
    "VIDEO_PICTURES_DIR", "VIDEO_RECOMMENDATION_CACHE_DIR", "VIDEO_CACHE_DIR",
    "LOCAL_PICTURES_DIR", "LOCAL_VIDEO_PICTURES_DIR", "LOCAL_VIDEO_COVER_DIR",
]


def __getattr__(name):
    """模块级动态属性访问 - JSON 文件路径和 storage 常量自动适配当前空间"""
    if name in _DYNAMIC_JSON_FILES:
        return _get_json_file(_DYNAMIC_JSON_FILES[name])
    if name in _DYNAMIC_PROXY_NAMES:
        from core import storage_layout
        return getattr(storage_layout, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
