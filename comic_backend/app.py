import atexit
import json
import os
import sys

from flask import Flask, make_response, send_from_directory
from flask_cors import CORS

from api import register_blueprints
from application.list_app_service import ListAppService
from core.constants import (
    CACHE_ROOT_DIR,
    COMIC_DIR,
    COVER_DIR,
    DATA_DIR,
    RECOMMENDATION_CACHE_DIR,
    SERVER_CONFIG_PATH,
    STATIC_DIR,
    VIDEO_DIR,
    ensure_storage_layout,
)
from infrastructure.backup_manager import init_backup_system, shutdown_backup_system
from infrastructure.logger import app_logger
from infrastructure.persistence.json_storage import JsonStorage
from infrastructure.persistence.repositories.tag_repository_impl import TagJsonRepository


def load_server_config():
    if os.path.exists(SERVER_CONFIG_PATH):
        try:
            with open(SERVER_CONFIG_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "backend": {"host": "0.0.0.0", "port": 5000},
        "frontend": {"host": "0.0.0.0", "port": 5173},
        "storage": {"data_dir": "./comic_backend/data"}
    }


SERVER_CONFIG = load_server_config()


def _as_bool(value, default=False):
    if value is None:
        return default
    text = str(value).strip().lower()
    if text in ("1", "true", "yes", "on"):
        return True
    if text in ("0", "false", "no", "off"):
        return False
    return default


def _resolve_backend_host():
    env_host = str(os.environ.get("BACKEND_HOST", "")).strip()
    if env_host:
        return env_host
    return SERVER_CONFIG.get("backend", {}).get("host", "0.0.0.0")


def _resolve_backend_port():
    env_port = str(os.environ.get("BACKEND_PORT", "")).strip()
    if env_port:
        try:
            return int(env_port)
        except Exception:
            pass
    return int(SERVER_CONFIG.get("backend", {}).get("port", 5000))


def _resolve_backend_debug():
    env_debug = os.environ.get("BACKEND_DEBUG")
    if env_debug is not None:
        return _as_bool(env_debug, default=False)
    return not getattr(sys, "frozen", False)


HOST = _resolve_backend_host()
PORT = _resolve_backend_port()
DEBUG = _resolve_backend_debug()

app = Flask(__name__)
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 300

CORS(app)

ensure_storage_layout()
register_blueprints(app)

app.static_folder = STATIC_DIR


def resolve_frontend_dist_dir() -> str:
    # Priority:
    # 1) explicit env for packaged desktop bundle
    # 2) project frontend dist for source run
    # 3) adjacent frontend_dist (fallback)
    env_path = str(os.environ.get("FRONTEND_DIST_DIR", "")).strip()
    if env_path and os.path.isdir(env_path):
        return os.path.abspath(env_path)

    project_dist = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "comic_frontend", "dist")
    )
    if os.path.isdir(project_dist):
        return project_dist

    # Check relative to app.py directory for bundled desktop
    bundled_dist = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "frontend_dist")
    )
    if os.path.isdir(bundled_dist):
        return bundled_dist

    adjacent = os.path.abspath(os.path.join(os.getcwd(), "frontend_dist"))
    if os.path.isdir(adjacent):
        return adjacent
    return ""


FRONTEND_DIST_DIR = resolve_frontend_dist_dir()
FRONTEND_ENABLED = bool(FRONTEND_DIST_DIR and os.path.isdir(FRONTEND_DIST_DIR))


@app.route('/')
def index():
    if FRONTEND_ENABLED:
        return send_from_directory(FRONTEND_DIST_DIR, "index.html")
    return "Comic Backend API"


@app.route('/health')
def health():
    return success_response({"status": "ok"})


@app.route('/<path:path>')
def frontend_fallback(path):
    """
    Serve frontend static assets and SPA routes when frontend_dist is available.
    Keep API/media/static routes handled by their dedicated endpoints.
    """
    if not FRONTEND_ENABLED:
        return make_response("Not Found", 404)

    normalized = str(path or "").lstrip("/")
    if not normalized:
        return send_from_directory(FRONTEND_DIST_DIR, "index.html")

    reserved_prefixes = ("api/", "static/", "media/")
    if normalized.startswith(reserved_prefixes) or normalized in ("api", "static", "media", "health"):
        return make_response("Not Found", 404)

    candidate = os.path.abspath(os.path.join(FRONTEND_DIST_DIR, normalized))
    frontend_root = os.path.abspath(FRONTEND_DIST_DIR)
    try:
        if os.path.commonpath([frontend_root, candidate]) != frontend_root:
            return make_response("Not Found", 404)
    except Exception:
        return make_response("Not Found", 404)

    if os.path.isfile(candidate):
        return send_from_directory(FRONTEND_DIST_DIR, normalized)
    return send_from_directory(FRONTEND_DIST_DIR, "index.html")

@app.route('/static/cover/<path:filename>')
def serve_cover(filename):
    """鎻愪緵灏侀潰鍥剧墖锛屽苟璁剧疆姝ｇ‘鐨?Content-Type"""
    response = make_response(send_from_directory(COVER_DIR, filename))
    if filename.endswith('.jpg') or filename.endswith('.jpeg'):
        response.headers['Content-Type'] = 'image/jpeg'
    elif filename.endswith('.png'):
        response.headers['Content-Type'] = 'image/png'
    elif filename.endswith('.webp'):
        response.headers['Content-Type'] = 'image/webp'
    return response

@app.route('/static/cover/<platform>/author_cache/<filename>')
def serve_author_cover(platform, filename):
    """鎻愪緵浣滆€呮洿鏂颁綔鍝佺殑灏侀潰鍥剧墖"""
    platform_key = str(platform or "").strip().upper() or "JM"
    new_cache_dir = os.path.join(CACHE_ROOT_DIR, "author_cover", platform_key)
    response = make_response(send_from_directory(new_cache_dir, filename))
    if filename.endswith('.jpg') or filename.endswith('.jpeg'):
        response.headers['Content-Type'] = 'image/jpeg'
    elif filename.endswith('.png'):
        response.headers['Content-Type'] = 'image/png'
    return response


@app.route('/media/<path:filename>')
def serve_media(filename):
    """Serve media assets stored under DATA_DIR using /media URLs."""
    relative_path = str(filename or "").replace("\\", "/").lstrip("/")
    if not relative_path:
        return make_response("Not Found", 404)

    allowed_prefixes = []
    for root_dir in (RECOMMENDATION_CACHE_DIR, VIDEO_DIR, COMIC_DIR):
        rel_dir = os.path.relpath(os.path.abspath(root_dir), os.path.abspath(DATA_DIR)).replace("\\", "/").strip("/")
        if rel_dir and rel_dir != ".":
            allowed_prefixes.append(rel_dir)

    if not any(relative_path == prefix or relative_path.startswith(f"{prefix}/") for prefix in allowed_prefixes):
        return make_response("Not Found", 404)

    target_path = os.path.abspath(os.path.join(DATA_DIR, relative_path.replace("/", os.sep)))
    data_root = os.path.abspath(DATA_DIR)
    try:
        if os.path.commonpath([data_root, target_path]) != data_root:
            return make_response("Not Found", 404)
    except Exception:
        return make_response("Not Found", 404)

    if not os.path.isfile(target_path):
        return make_response("Not Found", 404)

    response = make_response(send_from_directory(DATA_DIR, relative_path))
    lowered = relative_path.lower()
    if lowered.endswith(".m3u8"):
        response.headers["Content-Type"] = "application/vnd.apple.mpegurl"
    elif lowered.endswith(".ts"):
        response.headers["Content-Type"] = "video/mp2t"
    elif lowered.endswith(".mp4"):
        response.headers["Content-Type"] = "video/mp4"
    elif lowered.endswith(".webm"):
        response.headers["Content-Type"] = "video/webm"
    elif lowered.endswith(".jpg") or lowered.endswith(".jpeg"):
        response.headers["Content-Type"] = "image/jpeg"
    elif lowered.endswith(".png"):
        response.headers["Content-Type"] = "image/png"
    elif lowered.endswith(".webp"):
        response.headers["Content-Type"] = "image/webp"
    return response


def init_default_data():
    try:
        list_service = ListAppService()
        list_service.ensure_default_list()
        app_logger.info("Default list initialized")
    except Exception as e:
        app_logger.error(f"Failed to initialize default list: {e}")


def init_backup():
    """Initialize backup scheduler."""
    try:
        init_backup_system()
        # Shutdown backup scheduler when process exits.
        atexit.register(shutdown_backup_system)
        app_logger.info("Backup scheduler initialized")
    except Exception as e:
        app_logger.error(f"Failed to initialize backup scheduler: {e}")


def init_temp_file_cleanup():
    """Clean stale JSON temp files on startup."""
    try:
        cleaned = JsonStorage().cleanup_stale_meta_temp_files()
        if cleaned > 0:
            app_logger.info(f"Cleaned stale .tmp files on startup: {cleaned}")
    except Exception as e:
        app_logger.warning(f"Failed to clean stale .tmp files on startup: {e}")


def init_tag_schema():
    """Backfill missing tag content_type to keep tag schema consistent."""
    try:
        result = TagJsonRepository().ensure_content_type_schema()
        updated_count = int((result or {}).get("updated_count", 0))
        if updated_count > 0:
            app_logger.info(f"Tag schema normalized: updated {updated_count} tags with missing content_type")
    except Exception as e:
        app_logger.warning(f"Failed to normalize tag schema on startup: {e}")


def success_response(data=None):
    return {
        "code": 200,
        "msg": "success",
        "data": data
    }


def run_backend_server(host=None, port=None, debug=None):
    resolved_host = str(host or HOST).strip() or HOST
    try:
        resolved_port = int(port if port is not None else PORT)
    except Exception:
        resolved_port = PORT
    resolved_debug = DEBUG if debug is None else bool(debug)

    init_temp_file_cleanup()
    init_tag_schema()
    init_default_data()
    init_backup()
    app_logger.info(f"Starting backend service at {resolved_host}:{resolved_port}")
    app.run(
        host=resolved_host,
        port=resolved_port,
        debug=resolved_debug,
        use_reloader=False,
        threaded=True,
    )


if __name__ == '__main__':
    run_backend_server()

