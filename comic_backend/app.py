import atexit
import json
import os

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
    STATIC_DIR,
    VIDEO_DIR,
    ensure_storage_layout,
)
from infrastructure.backup_manager import init_backup_system, shutdown_backup_system
from infrastructure.logger import app_logger
from infrastructure.persistence.json_storage import JsonStorage


def load_server_config():
    config_path = os.path.join(os.path.dirname(__file__), '..', 'server_config.json')
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "backend": {"host": "0.0.0.0", "port": 5000},
        "frontend": {"host": "0.0.0.0", "port": 5173},
        "storage": {"data_dir": "./comic_backend/data"}
    }


SERVER_CONFIG = load_server_config()
HOST = SERVER_CONFIG.get("backend", {}).get("host", "0.0.0.0")
PORT = SERVER_CONFIG.get("backend", {}).get("port", 5000)
DEBUG = True

app = Flask(__name__)
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 300

CORS(app)

ensure_storage_layout()
register_blueprints(app)

app.static_folder = STATIC_DIR


@app.route('/')
def index():
    return "Comic Backend API"


@app.route('/health')
def health():
    return success_response({"status": "ok"})

@app.route('/static/cover/<path:filename>')
def serve_cover(filename):
    """提供封面图片，并设置正确的 Content-Type"""
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
    """提供作者更新作品的封面图片"""
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
        app_logger.info("默认清单初始化完成")
    except Exception as e:
        app_logger.error(f"初始化默认清单失败: {e}")


def init_backup():
    """初始化定时备份系统"""
    try:
        init_backup_system()
        # 注册退出时关闭备份系统
        atexit.register(shutdown_backup_system)
        app_logger.info("定时备份系统初始化完成")
    except Exception as e:
        app_logger.error(f"初始化定时备份系统失败: {e}")


def init_temp_file_cleanup():
    """清理残留的 json 临时文件，避免 .tmp 持续增长"""
    try:
        cleaned = JsonStorage().cleanup_stale_meta_temp_files()
        if cleaned > 0:
            app_logger.info(f"启动时已清理残留 .tmp 文件: {cleaned} 个")
    except Exception as e:
        app_logger.warning(f"启动清理 .tmp 文件失败: {e}")


def success_response(data=None):
    return {
        "code": 200,
        "msg": "成功",
        "data": data
    }


if __name__ == '__main__':
    init_temp_file_cleanup()
    init_default_data()
    init_backup()
    app_logger.info(f"启动服务器，地址: {HOST}:{PORT}")
    app.run(host=HOST, port=PORT, debug=DEBUG)
