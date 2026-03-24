import json
import os
import sys

# Mmmtttt


DEFAULT_SERVER_CONFIG = {
    "backend": {"host": "0.0.0.0", "port": 5000},
    "frontend": {"host": "0.0.0.0", "port": 5173},
    "storage": {"data_dir": "./comic_backend/data"},
}


def _expand_path(path_value: str) -> str:
    return os.path.abspath(os.path.expandvars(os.path.expanduser(str(path_value or "").strip())))


def _default_server_config_path() -> str:
    if getattr(sys, "frozen", False):
        exe_dir = os.path.abspath(os.path.dirname(sys.executable))
        if os.path.basename(exe_dir).lower() == "bin":
            return os.path.abspath(os.path.join(exe_dir, "..", "server_config.json"))
        return os.path.abspath(os.path.join(exe_dir, "server_config.json"))

    source_backend_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    source_project_root = os.path.abspath(os.path.join(source_backend_root, ".."))
    return os.path.abspath(os.path.join(source_project_root, "server_config.json"))


def resolve_server_config_path() -> str:
    env_override = str(os.environ.get("SERVER_CONFIG_PATH", "")).strip()
    source_backend_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    source_project_root = os.path.abspath(os.path.join(source_backend_root, ".."))
    candidates = []

    if env_override:
        candidates.append(_expand_path(env_override))

    if getattr(sys, "frozen", False):
        exe_dir = os.path.abspath(os.path.dirname(sys.executable))
        candidates.append(os.path.abspath(os.path.join(exe_dir, "server_config.json")))
        candidates.append(os.path.abspath(os.path.join(exe_dir, "..", "server_config.json")))

    candidates.append(os.path.abspath(os.path.join(source_project_root, "server_config.json")))
    candidates.append(os.path.abspath(os.path.join(os.getcwd(), "server_config.json")))

    for candidate in candidates:
        if candidate and os.path.exists(candidate):
            return candidate

    if env_override:
        return _expand_path(env_override)
    return _default_server_config_path()


SERVER_CONFIG_PATH = resolve_server_config_path()
PROJECT_ROOT = os.path.abspath(os.path.dirname(SERVER_CONFIG_PATH))


def _resolve_backend_root() -> str:
    source_backend_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    if not getattr(sys, "frozen", False):
        return source_backend_root

    candidates = (
        os.path.join(PROJECT_ROOT, "backend_source"),
        os.path.join(PROJECT_ROOT, "comic_backend"),
    )
    for candidate in candidates:
        if os.path.isdir(candidate):
            return os.path.abspath(candidate)
    return os.path.abspath(PROJECT_ROOT)


BACKEND_ROOT = _resolve_backend_root()


def resolve_third_party_config_path() -> str:
    env_override = str(os.environ.get("THIRD_PARTY_CONFIG_PATH", "")).strip()
    candidates = []

    if env_override:
        candidates.append(_expand_path(env_override))

    candidates.extend(
        [
            os.path.abspath(os.path.join(BACKEND_ROOT, "third_party_config.json")),
            os.path.abspath(os.path.join(PROJECT_ROOT, "backend_source", "third_party_config.json")),
            os.path.abspath(os.path.join(PROJECT_ROOT, "comic_backend", "third_party_config.json")),
            os.path.abspath(os.path.join(PROJECT_ROOT, "third_party_config.json")),
            os.path.abspath(os.path.join(os.getcwd(), "backend_source", "third_party_config.json")),
            os.path.abspath(os.path.join(os.getcwd(), "comic_backend", "third_party_config.json")),
            os.path.abspath(os.path.join(os.getcwd(), "third_party_config.json")),
        ]
    )

    for candidate in candidates:
        if candidate and os.path.exists(candidate):
            return candidate

    if env_override:
        return _expand_path(env_override)
    return os.path.abspath(os.path.join(BACKEND_ROOT, "third_party_config.json"))


THIRD_PARTY_CONFIG_PATH = resolve_third_party_config_path()


def _load_server_config():
    if os.path.exists(SERVER_CONFIG_PATH):
        try:
            with open(SERVER_CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return dict(DEFAULT_SERVER_CONFIG)


def _resolve_data_dir():
    config = _load_server_config()
    storage = config.get("storage", {}) if isinstance(config, dict) else {}
    configured_data_dir = storage.get("data_dir", "./comic_backend/data")
    configured_data_dir = str(configured_data_dir or "./comic_backend/data").strip()
    configured_data_dir = os.path.expandvars(os.path.expanduser(configured_data_dir))
    runtime_profile = str(os.environ.get("BACKEND_RUNTIME_PROFILE", "")).strip().lower()
    android_files_dir = str(os.environ.get("ANDROID_APP_FILES_DIR", "")).strip()

    if runtime_profile == "android" and android_files_dir:
        default_values = {
            "",
            ".",
            "./comic_backend/data",
            "comic_backend/data",
            "./data",
            "data",
        }
        if configured_data_dir.replace("\\", "/").strip().lower() in default_values:
            return os.path.abspath(os.path.join(android_files_dir, "app_data"))
        if not os.path.isabs(configured_data_dir):
            return os.path.abspath(os.path.join(android_files_dir, configured_data_dir))

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
META_DIR = os.path.join(DATA_DIR, "meta_data")
STATIC_DIR = os.path.join(DATA_DIR, "static")
COVER_DIR = os.path.join(STATIC_DIR, "cover")
LOGS_DIR = os.path.join(BACKEND_ROOT, "logs")
CACHE_ROOT_DIR = os.path.join(DATA_DIR, "cache")
RECOMMENDATION_CACHE_DIR = os.path.join(DATA_DIR, "recommendation_cache")

COMIC_DIR = os.path.join(DATA_DIR, "comic")
VIDEO_DIR = os.path.join(DATA_DIR, "video")
# Backward-compatible alias: legacy code expects PICTURES_DIR.
PICTURES_DIR = COMIC_DIR

COMIC_PICTURES_DIR = COMIC_DIR
COMIC_RECOMMENDATION_CACHE_DIR = os.path.join(RECOMMENDATION_CACHE_DIR, "comic")
COMIC_CACHE_DIR = os.path.join(CACHE_ROOT_DIR, "comic")

VIDEO_PICTURES_DIR = VIDEO_DIR
VIDEO_RECOMMENDATION_CACHE_DIR = os.path.join(RECOMMENDATION_CACHE_DIR, "video")
VIDEO_CACHE_DIR = os.path.join(CACHE_ROOT_DIR, "video")

JM_PICTURES_DIR = os.path.join(COMIC_DIR, "JM")
PK_PICTURES_DIR = os.path.join(COMIC_DIR, "PK")
JAVDB_PICTURES_DIR = os.path.join(VIDEO_DIR, "JAVDB")
JAVBUS_PICTURES_DIR = os.path.join(VIDEO_DIR, "JAVBUS")

JM_COVER_DIR = os.path.join(COVER_DIR, "JM")
PK_COVER_DIR = os.path.join(COVER_DIR, "PK")
JAVDB_COVER_DIR = os.path.join(COVER_DIR, "JAVDB")
JAVBUS_COVER_DIR = os.path.join(COVER_DIR, "JAVBUS")

JM_RECOMMENDATION_CACHE_DIR = os.path.join(COMIC_RECOMMENDATION_CACHE_DIR, "JM")
PK_RECOMMENDATION_CACHE_DIR = os.path.join(COMIC_RECOMMENDATION_CACHE_DIR, "PK")
JAVDB_RECOMMENDATION_CACHE_DIR = os.path.join(VIDEO_RECOMMENDATION_CACHE_DIR, "JAVDB")
JAVBUS_RECOMMENDATION_CACHE_DIR = os.path.join(VIDEO_RECOMMENDATION_CACHE_DIR, "JAVBUS")

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
        LOGS_DIR
    ]
    for d in dirs:
        os.makedirs(d, exist_ok=True)


def ensure_platform_dirs():
    dirs = [
        JM_PICTURES_DIR, PK_PICTURES_DIR, JAVDB_PICTURES_DIR, JAVBUS_PICTURES_DIR,
        JM_COVER_DIR, PK_COVER_DIR, JAVDB_COVER_DIR, JAVBUS_COVER_DIR,
        JM_RECOMMENDATION_CACHE_DIR, PK_RECOMMENDATION_CACHE_DIR,
        JAVDB_RECOMMENDATION_CACHE_DIR, JAVBUS_RECOMMENDATION_CACHE_DIR
    ]
    for d in dirs:
        os.makedirs(d, exist_ok=True)


def ensure_content_type_dirs():
    dirs = [
        COMIC_PICTURES_DIR,
        COMIC_RECOMMENDATION_CACHE_DIR,
        COMIC_CACHE_DIR,
        VIDEO_PICTURES_DIR,
        VIDEO_RECOMMENDATION_CACHE_DIR,
        VIDEO_CACHE_DIR
    ]
    for d in dirs:
        os.makedirs(d, exist_ok=True)


def ensure_storage_layout():
    ensure_base_dirs()
    ensure_platform_dirs()
    ensure_content_type_dirs()
