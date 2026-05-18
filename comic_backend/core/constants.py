import os
from core.config_paths import *  # noqa: F401,F403
from core.storage_layout import *  # noqa: F401,F403

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
UI_STATE_JSON_FILE = os.path.join(META_DIR, "ui_state_database.json")
BACKUP_SUFFIX = ".bkp"

DEFAULT_PAGE_MODE = "up_down"
DEFAULT_BACKGROUND = "white"
DEFAULT_PRELOAD_NUM = 3

MIN_SCORE = 1
MAX_SCORE = 12
SCORE_PRECISION = 0.5

CACHE_MAX_AGE = 300


