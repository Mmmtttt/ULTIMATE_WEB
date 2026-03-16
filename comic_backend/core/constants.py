import json
import os
import shutil


BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PROJECT_ROOT = os.path.abspath(os.path.join(BACKEND_ROOT, ".."))
SERVER_CONFIG_PATH = os.path.join(PROJECT_ROOT, "server_config.json")
LEGACY_DATA_DIR = os.path.join(BACKEND_ROOT, "data")
LEGACY_STATIC_DIR = os.path.join(BACKEND_ROOT, "static")


def _load_server_config():
    if os.path.exists(SERVER_CONFIG_PATH):
        try:
            with open(SERVER_CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "backend": {"host": "0.0.0.0", "port": 5000},
        "frontend": {"host": "0.0.0.0", "port": 5173},
        "storage": {"data_dir": "./comic_backend/data"}
    }


def _resolve_data_dir():
    config = _load_server_config()
    storage = config.get("storage", {}) if isinstance(config, dict) else {}
    configured_data_dir = storage.get("data_dir", "./comic_backend/data")
    configured_data_dir = str(configured_data_dir or "./comic_backend/data").strip()
    configured_data_dir = os.path.expandvars(os.path.expanduser(configured_data_dir))

    if os.path.isabs(configured_data_dir):
        return os.path.abspath(configured_data_dir)
    return os.path.abspath(os.path.join(PROJECT_ROOT, configured_data_dir))


def normalize_to_data_dir(path_value, default_relative=""):
    """Normalize non-absolute storage path values into DATA_DIR."""
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
        parts = parts[data_idx + 1:]

    return os.path.abspath(os.path.join(DATA_DIR, *parts))


DATA_DIR = _resolve_data_dir()
PICTURES_DIR = os.path.join(DATA_DIR, "pictures")
META_DIR = os.path.join(DATA_DIR, "meta_data")
STATIC_DIR = os.path.join(DATA_DIR, "static")
COVER_DIR = os.path.join(STATIC_DIR, "cover")
LOGS_DIR = os.path.join(BACKEND_ROOT, "logs")
CACHE_ROOT_DIR = os.path.join(DATA_DIR, "cache")
RECOMMENDATION_CACHE_DIR = os.path.join(DATA_DIR, "recommendation_cache")

COMIC_PICTURES_DIR = os.path.join(PICTURES_DIR, "comic")
COMIC_COVER_DIR = os.path.join(COVER_DIR, "comic")
COMIC_AUTHOR_COVER_CACHE_DIR = os.path.join(COMIC_COVER_DIR, "author_cache")
COMIC_RECOMMENDATION_CACHE_DIR = os.path.join(RECOMMENDATION_CACHE_DIR, "comic")
COMIC_CACHE_DIR = os.path.join(CACHE_ROOT_DIR, "comic")

VIDEO_PICTURES_DIR = os.path.join(PICTURES_DIR, "video")
VIDEO_COVER_DIR = os.path.join(COVER_DIR, "video")
VIDEO_ACTOR_COVER_CACHE_DIR = os.path.join(VIDEO_COVER_DIR, "actor_cache")
VIDEO_RECOMMENDATION_CACHE_DIR = os.path.join(RECOMMENDATION_CACHE_DIR, "video")
VIDEO_CACHE_DIR = os.path.join(CACHE_ROOT_DIR, "video")

JM_PICTURES_DIR = os.path.join(PICTURES_DIR, "JM")
PK_PICTURES_DIR = os.path.join(PICTURES_DIR, "PK")
JAV_PICTURES_DIR = os.path.join(PICTURES_DIR, "JAV")
JM_COVER_DIR = os.path.join(COVER_DIR, "JM")
PK_COVER_DIR = os.path.join(COVER_DIR, "PK")
JAV_COVER_DIR = os.path.join(COVER_DIR, "JAV")
JM_AUTHOR_COVER_CACHE_DIR = os.path.join(JM_COVER_DIR, "author_cache")
PK_AUTHOR_COVER_CACHE_DIR = os.path.join(PK_COVER_DIR, "author_cache")
JAV_ACTOR_COVER_CACHE_DIR = os.path.join(JAV_COVER_DIR, "actor_cache")
JM_RECOMMENDATION_CACHE_DIR = os.path.join(RECOMMENDATION_CACHE_DIR, "JM")
PK_RECOMMENDATION_CACHE_DIR = os.path.join(RECOMMENDATION_CACHE_DIR, "PK")
JAV_RECOMMENDATION_CACHE_DIR = os.path.join(RECOMMENDATION_CACHE_DIR, "JAV")

COVER_WIDTH = 800
COVER_QUALITY = 95
SUPPORTED_FORMATS = ['.jpg', '.jpeg', '.png', '.webp']

JSON_FILE = os.path.join(META_DIR, "comics_database.json")
RECOMMENDATION_JSON_FILE = os.path.join(META_DIR, "recommendations_database.json")
VIDEO_JSON_FILE = os.path.join(META_DIR, "videos_database.json")
VIDEO_RECOMMENDATION_JSON_FILE = os.path.join(META_DIR, "video_recommendations_database.json")
ACTOR_JSON_FILE = os.path.join(META_DIR, "actors_database.json")
AUTHOR_JSON_FILE = os.path.join(META_DIR, "authors_database.json")
TAGS_JSON_FILE = os.path.join(META_DIR, "tags_database.json")
LISTS_JSON_FILE = os.path.join(META_DIR, "lists_database.json")
USER_CONFIG_JSON_FILE = os.path.join(META_DIR, "user_config.json")
IMPORT_TASKS_JSON_FILE = os.path.join(META_DIR, "import_tasks.json")
RECOMMENDATION_CACHE_INDEX_FILE = os.path.join(META_DIR, "recommendation_cache_index.json")
BACKUP_SUFFIX = ".bkp"

DEFAULT_PAGE_MODE = "left_right"
DEFAULT_BACKGROUND = "white"
DEFAULT_PRELOAD_NUM = 3

MIN_SCORE = 1
MAX_SCORE = 12
SCORE_PRECISION = 0.5

CACHE_MAX_AGE = 300


def _move_or_merge_directory(src_dir, dest_dir):
    if not os.path.exists(src_dir):
        return

    os.makedirs(dest_dir, exist_ok=True)
    for root, _, files in os.walk(src_dir):
        rel_root = os.path.relpath(root, src_dir)
        target_root = dest_dir if rel_root == "." else os.path.join(dest_dir, rel_root)
        os.makedirs(target_root, exist_ok=True)
        for filename in files:
            src_file = os.path.join(root, filename)
            dest_file = os.path.join(target_root, filename)
            if os.path.exists(dest_file):
                continue
            try:
                shutil.move(src_file, dest_file)
            except Exception:
                pass


def migrate_legacy_static_dir():
    """Migrate legacy comic_backend/static to <DATA_DIR>/static."""
    if os.path.abspath(LEGACY_STATIC_DIR) == os.path.abspath(STATIC_DIR):
        return

    legacy_cover_dir = os.path.join(LEGACY_STATIC_DIR, "cover")
    if not os.path.exists(legacy_cover_dir):
        return

    _move_or_merge_directory(legacy_cover_dir, COVER_DIR)


def ensure_base_dirs():
    dirs = [
        DATA_DIR,
        META_DIR,
        PICTURES_DIR,
        STATIC_DIR,
        COVER_DIR,
        CACHE_ROOT_DIR,
        RECOMMENDATION_CACHE_DIR,
        LOGS_DIR
    ]
    for d in dirs:
        os.makedirs(d, exist_ok=True)


def ensure_platform_dirs():
    dirs = [
        JM_PICTURES_DIR, PK_PICTURES_DIR, JAV_PICTURES_DIR,
        JM_COVER_DIR, PK_COVER_DIR, JAV_COVER_DIR,
        JM_AUTHOR_COVER_CACHE_DIR, PK_AUTHOR_COVER_CACHE_DIR, JAV_ACTOR_COVER_CACHE_DIR,
        JM_RECOMMENDATION_CACHE_DIR, PK_RECOMMENDATION_CACHE_DIR, JAV_RECOMMENDATION_CACHE_DIR
    ]
    for d in dirs:
        os.makedirs(d, exist_ok=True)


def ensure_content_type_dirs():
    dirs = [
        COMIC_PICTURES_DIR, COMIC_COVER_DIR,
        COMIC_AUTHOR_COVER_CACHE_DIR, COMIC_RECOMMENDATION_CACHE_DIR,
        COMIC_CACHE_DIR,
        VIDEO_PICTURES_DIR, VIDEO_COVER_DIR,
        VIDEO_ACTOR_COVER_CACHE_DIR, VIDEO_RECOMMENDATION_CACHE_DIR,
        VIDEO_CACHE_DIR
    ]
    for d in dirs:
        os.makedirs(d, exist_ok=True)


def ensure_storage_layout():
    ensure_base_dirs()
    migrate_legacy_static_dir()
    ensure_platform_dirs()
    ensure_content_type_dirs()
