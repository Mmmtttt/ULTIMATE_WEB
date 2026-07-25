import atexit
import copy
import json
import os
import sys
import threading

# Ultimate Web - Mmmtttt

from flask import Flask, make_response, send_from_directory, g, request, session, jsonify
from flask_cors import CORS

from api import register_blueprints
from application.list_app_service import ListAppService
from core.constants import (
    CACHE_ROOT_DIR,
    COMIC_DIR,
    COVER_DIR,
    DATA_DIR,
    DEFAULT_SERVER_CONFIG,
    SERVER_CONFIG_PATH,
    STATIC_DIR,
    VIDEO_DIR,
    ensure_storage_layout,
)
from core.storage_layout import (
    SPACE_MODE_NORMAL,
    SPACE_MODE_PRIVATE,
    set_current_space_mode,
    get_data_dir,
    get_static_dir,
    get_cover_dir,
    get_cache_root_dir,
    get_comic_dir,
    get_video_dir,
    get_recommendation_cache_dir,
)
from core.ssl_cert import get_ssl_context_tuple
from infrastructure.archive import ensure_rar_backend_configured, probe_7z_encryption_capability
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
    return copy.deepcopy(DEFAULT_SERVER_CONFIG)


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


def _is_android_runtime() -> bool:
    runtime_profile = str(os.environ.get("BACKEND_RUNTIME_PROFILE", "")).strip().lower()
    android_files_dir = str(os.environ.get("ANDROID_APP_FILES_DIR", "")).strip()
    return runtime_profile == "android" or bool(android_files_dir)


# ========== Auth 配置 ==========

def _resolve_auth_enabled() -> bool:
    env_auth = os.environ.get("BACKEND_AUTH_ENABLED")
    if env_auth is not None:
        return _as_bool(env_auth, default=False)
    return _as_bool(
        SERVER_CONFIG.get("auth", {}).get("enabled", False),
        default=False,
    )


def _resolve_auth_password() -> str:
    env_pwd = str(os.environ.get("BACKEND_AUTH_PASSWORD", "")).strip()
    if env_pwd:
        return env_pwd
    return str(SERVER_CONFIG.get("auth", {}).get("password", "") or "").strip()


def _resolve_private_port() -> int:
    env_port = str(os.environ.get("BACKEND_PRIVATE_PORT", "")).strip()
    if env_port:
        try:
            return int(env_port)
        except Exception:
            pass
    return int(SERVER_CONFIG.get("auth", {}).get("private_port", 5000))


def _resolve_normal_port() -> int:
    env_port = str(os.environ.get("BACKEND_NORMAL_PORT", "")).strip()
    if env_port:
        try:
            return int(env_port)
        except Exception:
            pass
    return int(SERVER_CONFIG.get("auth", {}).get("normal_port", 5001))


def _resolve_secret_key() -> str:
    env_key = str(os.environ.get("BACKEND_SECRET_KEY", "")).strip()
    if env_key:
        return env_key
    cfg_key = str(SERVER_CONFIG.get("auth", {}).get("secret_key", "") or "").strip()
    if cfg_key:
        return cfg_key
    return "ultimate-web-default-secret-key-change-me"


# ========== 后端 host/ssl 配置 ==========

def _resolve_backend_host():
    env_host = str(os.environ.get("BACKEND_HOST", "")).strip()
    if env_host:
        return env_host
    return SERVER_CONFIG.get("backend", {}).get("host", "0.0.0.0")


def _resolve_backend_port():
    """auth 未启用时的默认端口"""
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


def _resolve_ssl_enabled() -> bool:
    env_ssl = os.environ.get("BACKEND_SSL_ENABLED")
    if env_ssl is not None:
        return _as_bool(env_ssl, default=False)
    if _is_android_runtime():
        return False
    config_val = SERVER_CONFIG.get("backend", {}).get("ssl_enabled")
    if config_val is None:
        return not _is_android_runtime()
    return _as_bool(config_val, default=not _is_android_runtime())


def _resolve_ssl_auto_generate() -> bool:
    env_auto = os.environ.get("BACKEND_SSL_AUTO_GENERATE")
    if env_auto is not None:
        return _as_bool(env_auto, default=True)
    return _as_bool(
        SERVER_CONFIG.get("backend", {}).get("ssl_auto_generate", True),
        default=True,
    )


def _resolve_ssl_cert_path() -> str:
    env_cert = str(os.environ.get("BACKEND_SSL_CERT_PATH", "")).strip()
    if env_cert:
        return os.path.abspath(os.path.expanduser(env_cert))
    config_cert = str(SERVER_CONFIG.get("backend", {}).get("ssl_cert_path", "")).strip()
    if config_cert:
        return os.path.abspath(os.path.expanduser(config_cert))
    return ""


def _resolve_ssl_key_path() -> str:
    env_key = str(os.environ.get("BACKEND_SSL_KEY_PATH", "")).strip()
    if env_key:
        return os.path.abspath(os.path.expanduser(env_key))
    config_key = str(SERVER_CONFIG.get("backend", {}).get("ssl_key_path", "")).strip()
    if config_key:
        return os.path.abspath(os.path.expanduser(config_key))
    return ""


def _resolve_ssl_context():
    if not _resolve_ssl_enabled():
        return None
    cert_path = _resolve_ssl_cert_path()
    key_path = _resolve_ssl_key_path()
    auto_generate = _resolve_ssl_auto_generate()
    try:
        result = get_ssl_context_tuple(
            cert_path=cert_path or None,
            key_path=key_path or None,
            auto_generate=auto_generate,
        )
        if result:
            app_logger.info(
                f"SSL enabled: cert={result[0]}, key={result[1]}"
            )
            return result
        app_logger.warning("SSL enabled but certificate unavailable, falling back to HTTP")
    except Exception as e:
        app_logger.warning(f"SSL setup failed, falling back to HTTP: {e}")
    return None


HOST = _resolve_backend_host()
DEBUG = _resolve_backend_debug()


# ========== App 工厂函数 ==========

def resolve_frontend_dist_dir() -> str:
    env_path = str(os.environ.get("FRONTEND_DIST_DIR", "")).strip()
    if env_path and os.path.isdir(env_path):
        return os.path.abspath(env_path)

    project_dist = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "comic_frontend", "dist")
    )
    if os.path.isdir(project_dist):
        return project_dist

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


def success_response(data=None):
    return {
        "code": 200,
        "msg": "success",
        "data": data
    }


def create_app(space_mode: str = SPACE_MODE_NORMAL, require_auth: bool = False) -> Flask:
    """
    创建一个 Flask app 实例

    Args:
        space_mode: 空间模式 - normal 或 private
        require_auth: 是否需要密码认证才能访问
    """
    # 设置当前线程的空间模式（用于初始化阶段）
    set_current_space_mode(space_mode)

    # 确保该空间的目录结构存在
    ensure_storage_layout(space_mode)

    app = Flask(__name__)
    app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 300
    app.config['SECRET_KEY'] = _resolve_secret_key()
    app.config['SPACE_MODE'] = space_mode
    app.config['REQUIRE_AUTH'] = require_auth

    CORS(app, supports_credentials=True)

    # 注册蓝图
    register_blueprints(app)

    # 静态文件目录 - 动态获取
    app.static_folder = get_static_dir(space_mode)

    # before_request: 设置当前线程的空间模式 + 认证检查
    @app.before_request
    def set_space_mode_on_request():
        set_current_space_mode(space_mode)
        g.space_mode = space_mode

        # 认证检查（仅 normal 空间需要）
        if require_auth:
            # 白名单：登录接口、健康检查、静态资源不需要认证
            path = request.path
            public_paths = (
                '/api/v1/auth/login',
                '/api/v1/auth/status',
                '/health',
            )
            if path in public_paths or path.startswith('/static/') or path.startswith('/media/'):
                return
            if not session.get('authenticated', False):
                return jsonify({
                    "code": 401,
                    "msg": "Authentication required",
                    "data": {"authenticated": False, "mode": "private"}
                }), 401

    # ========== 路由 ==========

    @app.route('/')
    def index():
        if FRONTEND_ENABLED:
            return send_from_directory(FRONTEND_DIST_DIR, "index.html")
        return f"Comic Backend API ({space_mode})"

    @app.route('/health')
    def health():
        return success_response({"status": "ok", "mode": space_mode})

    @app.route('/<path:path>')
    def frontend_fallback(path):
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
        cover_dir = get_cover_dir(space_mode)
        response = make_response(send_from_directory(cover_dir, filename))
        if filename.endswith('.jpg') or filename.endswith('.jpeg'):
            response.headers['Content-Type'] = 'image/jpeg'
        elif filename.endswith('.png'):
            response.headers['Content-Type'] = 'image/png'
        elif filename.endswith('.webp'):
            response.headers['Content-Type'] = 'image/webp'
        return response

    @app.route('/static/cover/<platform>/author_cache/<filename>')
    def serve_author_cover(platform, filename):
        platform_key = str(platform or "").strip().upper()
        if not platform_key:
            return make_response("Not Found", 404)
        cache_dir = os.path.join(get_cache_root_dir(space_mode), "author_cover", platform_key)
        response = make_response(send_from_directory(cache_dir, filename))
        if filename.endswith('.jpg') or filename.endswith('.jpeg'):
            response.headers['Content-Type'] = 'image/jpeg'
        elif filename.endswith('.png'):
            response.headers['Content-Type'] = 'image/png'
        return response

    @app.route('/media/<path:filename>')
    def serve_media(filename):
        data_dir = get_data_dir(space_mode)
        recommendation_cache_dir = get_recommendation_cache_dir(space_mode)
        video_dir = get_video_dir(space_mode)
        comic_dir = get_comic_dir(space_mode)

        relative_path = str(filename or "").replace("\\", "/").lstrip("/")
        if not relative_path:
            return make_response("Not Found", 404)

        allowed_prefixes = []
        for root_dir in (recommendation_cache_dir, video_dir, comic_dir):
            rel_dir = os.path.relpath(os.path.abspath(root_dir), os.path.abspath(data_dir)).replace("\\", "/").strip("/")
            if rel_dir and rel_dir != ".":
                allowed_prefixes.append(rel_dir)

        if not any(relative_path == prefix or relative_path.startswith(f"{prefix}/") for prefix in allowed_prefixes):
            return make_response("Not Found", 404)

        target_path = os.path.abspath(os.path.join(data_dir, relative_path.replace("/", os.sep)))
        data_root = os.path.abspath(data_dir)
        try:
            if os.path.commonpath([data_root, target_path]) != data_root:
                return make_response("Not Found", 404)
        except Exception:
            return make_response("Not Found", 404)

        if not os.path.isfile(target_path):
            return make_response("Not Found", 404)

        response = make_response(send_from_directory(data_dir, relative_path))
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

    return app


# ========== 单 app 兼容（旧模式）==========
# 保留全局 app 变量，供外部模块引用（向后兼容）
# 当 auth 未启用时，使用 normal 模式的 app
app = create_app(space_mode=SPACE_MODE_NORMAL, require_auth=False)


# ========== 初始化函数 ==========

def init_default_data_for_mode(mode: str):
    try:
        set_current_space_mode(mode)
        list_service = ListAppService()
        list_service.ensure_default_list()
        app_logger.info(f"Default list initialized for {mode} mode")
    except Exception as e:
        app_logger.error(f"Failed to initialize default list for {mode} mode: {e}")


def init_backup_for_mode(mode: str):
    """Initialize backup scheduler for a space mode."""
    try:
        set_current_space_mode(mode)
        init_backup_system()
        app_logger.info(f"Backup scheduler initialized for {mode} mode")
    except Exception as e:
        app_logger.error(f"Failed to initialize backup for {mode} mode: {e}")


def init_temp_file_cleanup_for_mode(mode: str):
    try:
        set_current_space_mode(mode)
        cleaned = JsonStorage().cleanup_stale_meta_temp_files()
        if cleaned > 0:
            app_logger.info(f"Cleaned {cleaned} stale .tmp files for {mode} mode")
    except Exception as e:
        app_logger.warning(f"Failed to clean .tmp files for {mode} mode: {e}")


def init_tag_schema_for_mode(mode: str):
    try:
        set_current_space_mode(mode)
        result = TagJsonRepository().ensure_content_type_schema()
        updated_count = int((result or {}).get("updated_count", 0))
        if updated_count > 0:
            app_logger.info(f"Tag schema normalized for {mode} mode: {updated_count} tags updated")
    except Exception as e:
        app_logger.warning(f"Failed to normalize tag schema for {mode} mode: {e}")


def run_common_init():
    """运行两个空间都需要的公共初始化（只运行一次）"""
    ensure_rar_backend_configured(logger=app_logger, force=True)
    sevenzip_capability = probe_7z_encryption_capability()
    app_logger.info(
        "7z encrypted archive capability: "
        f"enabled={bool(sevenzip_capability.get('enabled', False))} "
        f"py7zr_installed={bool(sevenzip_capability.get('py7zr_installed', False))} "
        f"py7zr_version={sevenzip_capability.get('py7zr_version', '') or '<unknown>'} "
        f"cryptodome_installed={bool(sevenzip_capability.get('cryptodome_installed', False))}"
    )
    if not bool(sevenzip_capability.get("enabled", False)):
        app_logger.warning(
            "7z encrypted archive capability unavailable: "
            f"{sevenzip_capability.get('error', '') or 'unknown error'}"
        )

    # 注册退出时的清理
    atexit.register(shutdown_backup_system)


def run_space_init(mode: str):
    """运行单个空间的初始化"""
    init_temp_file_cleanup_for_mode(mode)
    init_tag_schema_for_mode(mode)
    init_default_data_for_mode(mode)
    init_backup_for_mode(mode)


# ========== 启动函数 ==========

def _run_app_in_thread(app_instance, port: int, ssl_context):
    """在当前线程运行 app（用于子线程）"""
    protocol = "https" if ssl_context else "http"
    mode = app_instance.config.get('SPACE_MODE', 'unknown')
    app_logger.info(f"Starting {mode} backend at {protocol}://{HOST}:{port}")
    app_instance.run(
        host=HOST,
        port=port,
        debug=False,
        use_reloader=False,
        threaded=True,
        ssl_context=ssl_context,
    )


def run_backend_server(host=None, port=None, debug=None):
    """
    启动后端服务

    - 如果 auth 未启用：启动单个 normal 模式的 app（兼容旧行为）
    - 如果 auth 已启用：启动两个 app，private 端口和 normal 端口
    """
    global HOST, DEBUG
    resolved_host = str(host or HOST).strip() or HOST
    try:
        resolved_port = int(port if port is not None else _resolve_backend_port())
    except Exception:
        resolved_port = _resolve_backend_port()
    resolved_debug = DEBUG if debug is None else bool(debug)

    HOST = resolved_host
    DEBUG = resolved_debug

    ssl_context = _resolve_ssl_context()
    protocol = "https" if ssl_context else "http"

    run_common_init()

    auth_enabled = _resolve_auth_enabled()
    password = _resolve_auth_password()

    if not auth_enabled or not password:
        # 旧模式：单 app 启动
        if auth_enabled and not password:
            app_logger.warning("Auth enabled but password is empty, falling back to single mode")
        run_space_init(SPACE_MODE_NORMAL)
        app_logger.info(f"Starting backend service at {protocol}://{resolved_host}:{resolved_port}")
        app.run(
            host=resolved_host,
            port=resolved_port,
            debug=resolved_debug,
            use_reloader=False,
            threaded=True,
            ssl_context=ssl_context,
        )
        return

    # 双空间模式
    private_port = _resolve_private_port()
    normal_port = _resolve_normal_port()

    # 创建两个 app 实例
    private_app = create_app(space_mode=SPACE_MODE_PRIVATE, require_auth=False)
    normal_app = create_app(space_mode=SPACE_MODE_NORMAL, require_auth=True)

    # 初始化两个空间
    run_space_init(SPACE_MODE_PRIVATE)
    run_space_init(SPACE_MODE_NORMAL)

    app_logger.info("=" * 60)
    app_logger.info(f"Auth enabled - dual space mode")
    app_logger.info(f"  Private mode: {protocol}://{resolved_host}:{private_port} (no auth required)")
    app_logger.info(f"  Normal mode:  {protocol}://{resolved_host}:{normal_port} (auth required)")
    app_logger.info("=" * 60)

    # 在子线程启动 private app
    private_thread = threading.Thread(
        target=_run_app_in_thread,
        args=(private_app, private_port, ssl_context),
        daemon=True,
        name="private-backend",
    )
    private_thread.start()

    # 在主线程运行 normal app
    _run_app_in_thread(normal_app, normal_port, ssl_context)


if __name__ == '__main__':
    run_backend_server()
