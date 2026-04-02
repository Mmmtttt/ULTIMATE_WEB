import json
import os
import shutil
import sys

# Mmmtttt


DEFAULT_SERVER_CONFIG = {
    "backend": {"host": "0.0.0.0", "port": 5000},
    "frontend": {"host": "0.0.0.0", "port": 5173},
    "storage": {"data_dir": "./../UltimateData"},
}

DEFAULT_THIRD_PARTY_CONFIG = {
    "default_adapter": "jmcomic",
    "adapters": {
        "jmcomic": {
            "enabled": True,
            "config_path": "JMComic-Crawler-Python/config.json",
            "username": "请输入账号",
            "password": "请输入密码",
            "download_dir": "./comic_backend/data/comic/JM",
            "output_json": "comics_database.json",
            "progress_file": "download_progress.json",
            "favorite_list_file": "favorite_comics.txt",
            "consecutive_hit_threshold": 10,
            "collection_name": "我的最爱",
        },
        "picacomic": {
            "enabled": True,
            "account": "请输入账号",
            "password": "请输入密码",
            "base_dir": "./comic_backend/data/comic/PK",
        },
        "javdb": {
            "enabled": True,
            "domain_index": 0,
            "timeout": 30,
            "retry_times": 3,
            "sleep_time": 0.5,
            "cookies": {
                "_jdb_session": "请输入cookie",
                "list_mode": "h",
                "theme": "auto",
                "over18": "1",
                "locale": "zh",
            },
        },
    },
}


SOURCE_BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SOURCE_PROJECT_ROOT = os.path.abspath(os.path.join(SOURCE_BACKEND_ROOT, ".."))
CONFIG_TEMPLATES_DIR = os.path.join(SOURCE_PROJECT_ROOT, "config_templates")
SERVER_CONFIG_TEMPLATE_PATH = os.path.join(CONFIG_TEMPLATES_DIR, "server_config.template.json")
THIRD_PARTY_CONFIG_TEMPLATE_PATH = os.path.join(CONFIG_TEMPLATES_DIR, "third_party_config.template.json")


def _expand_path(path_value: str) -> str:
    return os.path.abspath(os.path.expandvars(os.path.expanduser(str(path_value or "").strip())))


def _resolve_project_root() -> str:
    if not getattr(sys, "frozen", False):
        return SOURCE_PROJECT_ROOT
    exe_dir = os.path.abspath(os.path.dirname(sys.executable))
    if os.path.basename(exe_dir).lower() == "bin":
        return os.path.abspath(os.path.join(exe_dir, ".."))
    return exe_dir


PROJECT_ROOT = _resolve_project_root()


def _is_same_path(path_a: str, path_b: str) -> bool:
    return os.path.normcase(os.path.abspath(path_a)) == os.path.normcase(os.path.abspath(path_b))


def _resolve_platform_default_config_dir() -> str:
    runtime_profile = str(os.environ.get("BACKEND_RUNTIME_PROFILE", "")).strip().lower()
    android_files_dir = str(os.environ.get("ANDROID_APP_FILES_DIR", "")).strip()
    if runtime_profile == "android" or android_files_dir:
        if android_files_dir:
            return os.path.abspath(os.path.join(_expand_path(android_files_dir), "config"))
        return os.path.abspath(os.path.join(os.path.expanduser("~"), ".config", "ULTIMATE_WEB"))

    if sys.platform.startswith("win"):
        base = str(os.environ.get("APPDATA", "")).strip() or str(os.environ.get("LOCALAPPDATA", "")).strip()
        if base:
            return os.path.abspath(os.path.join(_expand_path(base), "ULTIMATE_WEB"))
        return os.path.abspath(os.path.join(os.path.expanduser("~"), "AppData", "Roaming", "ULTIMATE_WEB"))

    if sys.platform == "darwin":
        return os.path.abspath(os.path.join(os.path.expanduser("~"), "Library", "Application Support", "ULTIMATE_WEB"))

    xdg_config_home = str(os.environ.get("XDG_CONFIG_HOME", "")).strip()
    if xdg_config_home:
        return os.path.abspath(os.path.join(_expand_path(xdg_config_home), "ULTIMATE_WEB"))
    return os.path.abspath(os.path.join(os.path.expanduser("~"), ".config", "ULTIMATE_WEB"))


DEFAULT_APP_CONFIG_DIR = _resolve_platform_default_config_dir()
CONFIG_DIR_OVERRIDE_FILE = os.path.join(DEFAULT_APP_CONFIG_DIR, "config_dir.override.json")


def _load_persisted_config_dir() -> str:
    try:
        with open(CONFIG_DIR_OVERRIDE_FILE, "r", encoding="utf-8") as f:
            payload = json.load(f)
        configured = str((payload or {}).get("config_dir", "")).strip()
        if configured:
            return _expand_path(configured)
    except Exception:
        pass
    return ""


def _write_persisted_config_dir(config_dir: str) -> None:
    os.makedirs(DEFAULT_APP_CONFIG_DIR, exist_ok=True)
    with open(CONFIG_DIR_OVERRIDE_FILE, "w", encoding="utf-8") as f:
        json.dump({"config_dir": config_dir}, f, ensure_ascii=False, indent=2)


def _clear_persisted_config_dir() -> None:
    if os.path.exists(CONFIG_DIR_OVERRIDE_FILE):
        try:
            os.remove(CONFIG_DIR_OVERRIDE_FILE)
        except Exception:
            pass


def _resolve_platform_config_dir():
    env_override = str(os.environ.get("ULTIMATE_CONFIG_DIR", "")).strip()
    if env_override:
        return _expand_path(env_override), "env"

    persisted = _load_persisted_config_dir()
    if persisted:
        return persisted, "persisted"

    return DEFAULT_APP_CONFIG_DIR, "default"


APP_CONFIG_DIR, APP_CONFIG_DIR_SOURCE = _resolve_platform_config_dir()


def _load_json_template(template_path: str, fallback: dict) -> dict:
    try:
        with open(template_path, "r", encoding="utf-8") as f:
            loaded = json.load(f)
            if isinstance(loaded, dict):
                return loaded
    except Exception:
        pass
    return dict(fallback)


def _create_config_from_template(path: str, template_path: str, fallback: dict) -> None:
    parent_dir = os.path.dirname(path) or "."
    os.makedirs(parent_dir, exist_ok=True)
    payload = _load_json_template(template_path, fallback)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def _resolve_or_init_config_path(
    filename: str,
    env_key: str,
    template_path: str,
    fallback: dict,
    legacy_candidates,
) -> str:
    env_override = str(os.environ.get(env_key, "")).strip()
    if env_override:
        target_path = _expand_path(env_override)
        if not os.path.exists(target_path):
            _create_config_from_template(target_path, template_path, fallback)
        return target_path

    target_path = os.path.abspath(os.path.join(APP_CONFIG_DIR, filename))
    if os.path.exists(target_path):
        return target_path

    for candidate in legacy_candidates:
        if not candidate:
            continue
        source_path = os.path.abspath(candidate)
        if source_path == target_path:
            continue
        if os.path.exists(source_path):
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            try:
                shutil.copy2(source_path, target_path)
            except Exception:
                _create_config_from_template(target_path, template_path, fallback)
            return target_path

    _create_config_from_template(target_path, template_path, fallback)
    return target_path


def get_config_directory_info() -> dict:
    runtime_config_dir = os.path.abspath(os.path.dirname(SERVER_CONFIG_PATH))
    selected_config_dir = os.path.abspath(APP_CONFIG_DIR)
    return {
        "runtime_config_dir": runtime_config_dir,
        "selected_config_dir": selected_config_dir,
        "default_config_dir": os.path.abspath(DEFAULT_APP_CONFIG_DIR),
        "source": APP_CONFIG_DIR_SOURCE,
        "override_file_path": os.path.abspath(CONFIG_DIR_OVERRIDE_FILE),
        "server_config_path": os.path.abspath(SERVER_CONFIG_PATH),
        "third_party_config_path": os.path.abspath(THIRD_PARTY_CONFIG_PATH),
        "env_override": bool(str(os.environ.get("ULTIMATE_CONFIG_DIR", "")).strip()),
        "requires_restart": not _is_same_path(runtime_config_dir, selected_config_dir),
    }


def _prepare_config_file(target_dir: str, filename: str, source_path: str, template_path: str, fallback: dict, migrate_existing: bool) -> str:
    os.makedirs(target_dir, exist_ok=True)
    target_path = os.path.abspath(os.path.join(target_dir, filename))

    if migrate_existing and source_path and os.path.exists(source_path):
        try:
            if not _is_same_path(source_path, target_path):
                shutil.copy2(source_path, target_path)
            elif not os.path.exists(target_path):
                shutil.copy2(source_path, target_path)
        except Exception:
            pass

    if not os.path.exists(target_path):
        _create_config_from_template(target_path, template_path, fallback)

    return target_path


def set_app_config_dir(new_dir: str, migrate_existing: bool = True) -> dict:
    global APP_CONFIG_DIR, APP_CONFIG_DIR_SOURCE

    info = get_config_directory_info()
    if info.get("source") == "env":
        raise RuntimeError("当前配置目录由环境变量 ULTIMATE_CONFIG_DIR 控制，无法在页面中修改")

    target_dir = _expand_path(new_dir)
    if not str(target_dir or "").strip():
        raise ValueError("配置目录不能为空")

    previous_selected_dir = os.path.abspath(APP_CONFIG_DIR)

    next_server_path = _prepare_config_file(
        target_dir,
        "server_config.json",
        SERVER_CONFIG_PATH,
        SERVER_CONFIG_TEMPLATE_PATH,
        DEFAULT_SERVER_CONFIG,
        migrate_existing,
    )
    next_third_path = _prepare_config_file(
        target_dir,
        "third_party_config.json",
        THIRD_PARTY_CONFIG_PATH,
        THIRD_PARTY_CONFIG_TEMPLATE_PATH,
        DEFAULT_THIRD_PARTY_CONFIG,
        migrate_existing,
    )

    if _is_same_path(target_dir, DEFAULT_APP_CONFIG_DIR):
        _clear_persisted_config_dir()
        APP_CONFIG_DIR_SOURCE = "default"
    else:
        _write_persisted_config_dir(target_dir)
        APP_CONFIG_DIR_SOURCE = "persisted"

    APP_CONFIG_DIR = os.path.abspath(target_dir)
    changed = not _is_same_path(previous_selected_dir, APP_CONFIG_DIR)
    runtime_config_dir = os.path.abspath(os.path.dirname(SERVER_CONFIG_PATH))

    return {
        "changed": changed,
        "runtime_config_dir": runtime_config_dir,
        "selected_config_dir": APP_CONFIG_DIR,
        "default_config_dir": os.path.abspath(DEFAULT_APP_CONFIG_DIR),
        "source": APP_CONFIG_DIR_SOURCE,
        "override_file_path": os.path.abspath(CONFIG_DIR_OVERRIDE_FILE),
        "next_server_config_path": next_server_path,
        "next_third_party_config_path": next_third_path,
        "requires_restart": not _is_same_path(runtime_config_dir, APP_CONFIG_DIR),
    }


def _resolve_backend_root() -> str:
    if not getattr(sys, "frozen", False):
        return SOURCE_BACKEND_ROOT

    candidates = (
        os.path.join(PROJECT_ROOT, "backend_source"),
        os.path.join(PROJECT_ROOT, "comic_backend"),
    )
    for candidate in candidates:
        if os.path.isdir(candidate):
            return os.path.abspath(candidate)
    return os.path.abspath(PROJECT_ROOT)


BACKEND_ROOT = _resolve_backend_root()


def resolve_server_config_path() -> str:
    legacy_candidates = []

    if getattr(sys, "frozen", False):
        exe_dir = os.path.abspath(os.path.dirname(sys.executable))
        legacy_candidates.append(os.path.abspath(os.path.join(exe_dir, "server_config.json")))
        legacy_candidates.append(os.path.abspath(os.path.join(exe_dir, "..", "server_config.json")))

    legacy_candidates.append(os.path.abspath(os.path.join(SOURCE_PROJECT_ROOT, "server_config.json")))
    legacy_candidates.append(os.path.abspath(os.path.join(os.getcwd(), "server_config.json")))

    return _resolve_or_init_config_path(
        filename="server_config.json",
        env_key="SERVER_CONFIG_PATH",
        template_path=SERVER_CONFIG_TEMPLATE_PATH,
        fallback=DEFAULT_SERVER_CONFIG,
        legacy_candidates=legacy_candidates,
    )


SERVER_CONFIG_PATH = resolve_server_config_path()


def resolve_third_party_config_path() -> str:
    legacy_candidates = []

    if getattr(sys, "frozen", False):
        exe_dir = os.path.abspath(os.path.dirname(sys.executable))
        legacy_candidates.append(os.path.abspath(os.path.join(exe_dir, "third_party_config.json")))
        legacy_candidates.append(os.path.abspath(os.path.join(exe_dir, "..", "third_party_config.json")))

    legacy_candidates.extend(
        [
            os.path.abspath(os.path.join(BACKEND_ROOT, "third_party_config.json")),
            os.path.abspath(os.path.join(PROJECT_ROOT, "backend_source", "third_party_config.json")),
            os.path.abspath(os.path.join(PROJECT_ROOT, "comic_backend", "third_party_config.json")),
            os.path.abspath(os.path.join(PROJECT_ROOT, "third_party_config.json")),
            os.path.abspath(os.path.join(SOURCE_BACKEND_ROOT, "third_party_config.json")),
            os.path.abspath(os.path.join(SOURCE_PROJECT_ROOT, "third_party_config.json")),
            os.path.abspath(os.path.join(os.getcwd(), "backend_source", "third_party_config.json")),
            os.path.abspath(os.path.join(os.getcwd(), "comic_backend", "third_party_config.json")),
            os.path.abspath(os.path.join(os.getcwd(), "third_party_config.json")),
        ]
    )

    return _resolve_or_init_config_path(
        filename="third_party_config.json",
        env_key="THIRD_PARTY_CONFIG_PATH",
        template_path=THIRD_PARTY_CONFIG_TEMPLATE_PATH,
        fallback=DEFAULT_THIRD_PARTY_CONFIG,
        legacy_candidates=legacy_candidates,
    )


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
LOGS_DIR = os.path.join(DATA_DIR, "logs")
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
LOCAL_PICTURES_DIR = os.path.join(COMIC_DIR, "local")
JAVDB_PICTURES_DIR = os.path.join(VIDEO_DIR, "JAVDB")
JAVBUS_PICTURES_DIR = os.path.join(VIDEO_DIR, "JAVBUS")
LOCAL_VIDEO_PICTURES_DIR = os.path.join(VIDEO_DIR, "LOCAL")

JM_COVER_DIR = os.path.join(COVER_DIR, "JM")
PK_COVER_DIR = os.path.join(COVER_DIR, "PK")
JAVDB_COVER_DIR = os.path.join(COVER_DIR, "JAVDB")
JAVBUS_COVER_DIR = os.path.join(COVER_DIR, "JAVBUS")
LOCAL_VIDEO_COVER_DIR = os.path.join(COVER_DIR, "LOCAL")

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

DEFAULT_PAGE_MODE = "up_down"
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
        JM_PICTURES_DIR, PK_PICTURES_DIR, LOCAL_PICTURES_DIR, JAVDB_PICTURES_DIR, JAVBUS_PICTURES_DIR, LOCAL_VIDEO_PICTURES_DIR,
        JM_COVER_DIR, PK_COVER_DIR, JAVDB_COVER_DIR, JAVBUS_COVER_DIR, LOCAL_VIDEO_COVER_DIR,
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
