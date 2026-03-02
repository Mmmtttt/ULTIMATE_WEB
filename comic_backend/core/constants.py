import os

DATA_DIR = "data"
PICTURES_DIR = "data/pictures"
META_DIR = "data/meta_data"
STATIC_DIR = "static"
COVER_DIR = "static/cover"
LOGS_DIR = "logs"

JM_PICTURES_DIR = "data/pictures/JM"
PK_PICTURES_DIR = "data/pictures/PK"
JM_COVER_DIR = "static/cover/JM"
PK_COVER_DIR = "static/cover/PK"
JM_AUTHOR_COVER_CACHE_DIR = "static/cover/JM/author_cache"
PK_AUTHOR_COVER_CACHE_DIR = "static/cover/PK/author_cache"
JM_RECOMMENDATION_CACHE_DIR = "data/recommendation_cache/JM"
PK_RECOMMENDATION_CACHE_DIR = "data/recommendation_cache/PK"

COVER_WIDTH = 800
COVER_QUALITY = 95
SUPPORTED_FORMATS = ['.jpg', '.jpeg', '.png', '.webp']

JSON_FILE = "data/meta_data/comics_database.json"
RECOMMENDATION_JSON_FILE = "data/meta_data/recommendations_database.json"
BACKUP_SUFFIX = ".bkp"

DEFAULT_PAGE_MODE = "left_right"
DEFAULT_BACKGROUND = "white"
DEFAULT_PRELOAD_NUM = 3

MIN_SCORE = 1
MAX_SCORE = 12
SCORE_PRECISION = 0.5

CACHE_MAX_AGE = 300


def ensure_platform_dirs():
    dirs = [
        JM_PICTURES_DIR, PK_PICTURES_DIR,
        JM_COVER_DIR, PK_COVER_DIR,
        JM_AUTHOR_COVER_CACHE_DIR, PK_AUTHOR_COVER_CACHE_DIR,
        JM_RECOMMENDATION_CACHE_DIR, PK_RECOMMENDATION_CACHE_DIR
    ]
    for d in dirs:
        os.makedirs(d, exist_ok=True)
