import os

DATA_DIR = "data"
PICTURES_DIR = "data/pictures"
META_DIR = "data/meta_data"
STATIC_DIR = "static"
COVER_DIR = "static/cover"
LOGS_DIR = "logs"

COMIC_PICTURES_DIR = "data/pictures/comic"
COMIC_COVER_DIR = "static/cover/comic"
COMIC_AUTHOR_COVER_CACHE_DIR = "static/cover/comic/author_cache"
COMIC_RECOMMENDATION_CACHE_DIR = "data/recommendation_cache/comic"
COMIC_CACHE_DIR = "data/cache/comic"

VIDEO_PICTURES_DIR = "data/pictures/video"
VIDEO_COVER_DIR = "static/cover/video"
VIDEO_ACTOR_COVER_CACHE_DIR = "static/cover/video/actor_cache"
VIDEO_RECOMMENDATION_CACHE_DIR = "data/recommendation_cache/video"
VIDEO_CACHE_DIR = "data/cache/video"

JM_PICTURES_DIR = "data/pictures/JM"
PK_PICTURES_DIR = "data/pictures/PK"
JAV_PICTURES_DIR = "data/pictures/JAV"
JM_COVER_DIR = "static/cover/JM"
PK_COVER_DIR = "static/cover/PK"
JAV_COVER_DIR = "static/cover/JAV"
JM_AUTHOR_COVER_CACHE_DIR = "static/cover/JM/author_cache"
PK_AUTHOR_COVER_CACHE_DIR = "static/cover/PK/author_cache"
JAV_ACTOR_COVER_CACHE_DIR = "static/cover/JAV/actor_cache"
JM_RECOMMENDATION_CACHE_DIR = "data/recommendation_cache/JM"
PK_RECOMMENDATION_CACHE_DIR = "data/recommendation_cache/PK"
JAV_RECOMMENDATION_CACHE_DIR = "data/recommendation_cache/JAV"

COVER_WIDTH = 800
COVER_QUALITY = 95
SUPPORTED_FORMATS = ['.jpg', '.jpeg', '.png', '.webp']

JSON_FILE = "data/meta_data/comics_database.json"
RECOMMENDATION_JSON_FILE = "data/meta_data/recommendations_database.json"
VIDEO_JSON_FILE = "data/meta_data/videos_database.json"
VIDEO_RECOMMENDATION_JSON_FILE = "data/meta_data/video_recommendations_database.json"
ACTOR_JSON_FILE = "data/meta_data/actors_database.json"
TAGS_JSON_FILE = "data/meta_data/tags_database.json"
LISTS_JSON_FILE = "data/meta_data/lists_database.json"
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
