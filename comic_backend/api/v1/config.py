import json
import os
import shutil
import sys
import threading
import time

from flask import Blueprint, jsonify, request, send_from_directory

from application.config_app_service import ConfigAppService
from core.constants import (
    CACHE_ROOT_DIR,
    COMIC_RECOMMENDATION_CACHE_DIR,
    DATA_DIR,
    JM_PICTURES_DIR,
    PK_PICTURES_DIR,
    SERVER_CONFIG_PATH,
    VIDEO_RECOMMENDATION_CACHE_DIR,
    VIDEO_RECOMMENDATION_JSON_FILE,
)
from core.runtime_profile import is_third_party_enabled, runtime_capabilities
from infrastructure.logger import app_logger, error_logger
from infrastructure.persistence.json_storage import JsonStorage
from infrastructure.recommendation_cache_manager import recommendation_cache_manager


config_bp = Blueprint('config', __name__)
config_service = ConfigAppService()

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
_STATIC_PAGE_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', '..', 'static_pages')
)
_JAVDB_PLAYER_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', '..', 'third_party', 'javdb-api-scraper', 'player')
)
_JAVDB_STATIC_SCREENSHOTS_DIR = os.path.abspath(
    os.path.join(_STATIC_PAGE_DIR, 'screenshots')
)
_JAVDB_LIB_SCREENSHOTS_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', '..', 'third_party', 'javdb-api-scraper', 'lib', 'screenshots')
)
_VIDEO_PREVIEW_CACHE_DIR = VIDEO_RECOMMENDATION_CACHE_DIR
_VIDEO_LOCAL_ASSET_FIELDS = ("cover_path_local", "thumbnail_images_local", "preview_video_local")


def success_response(data=None, msg="成功"):
    return jsonify({
        "code": 200,
        "msg": msg,
        "data": data,
    })


def error_response(code, msg):
    return jsonify({
        "code": code,
        "msg": msg,
        "data": None,
    })


def _default_server_config():
    return {
        "backend": {"host": "0.0.0.0", "port": 5000},
        "frontend": {"host": "0.0.0.0", "port": 5173},
        "storage": {"data_dir": "./comic_backend/data"},
    }


def _load_server_config():
    if os.path.exists(SERVER_CONFIG_PATH):
        try:
            with open(SERVER_CONFIG_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            error_logger.error(f"读取 server_config.json 失败: {e}")
    return _default_server_config()


def _save_server_config(config):
    os.makedirs(os.path.dirname(SERVER_CONFIG_PATH), exist_ok=True)
    with open(SERVER_CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def _resolve_data_dir(path_value):
    raw = str(path_value or '').strip() or './comic_backend/data'
    expanded = os.path.expandvars(os.path.expanduser(raw))
    if os.path.isabs(expanded):
        return os.path.abspath(expanded)
    return os.path.abspath(os.path.join(_PROJECT_ROOT, expanded))


def _is_same_path(path_a, path_b):
    return os.path.normcase(os.path.abspath(path_a)) == os.path.normcase(os.path.abspath(path_b))


def _is_sub_path(parent, child):
    parent_abs = os.path.normcase(os.path.abspath(parent))
    child_abs = os.path.normcase(os.path.abspath(child))
    try:
        return os.path.commonpath([parent_abs, child_abs]) == parent_abs
    except ValueError:
        return False


def _count_files(root_dir):
    if not os.path.exists(root_dir):
        return 0

    total = 0
    for _, _, files in os.walk(root_dir):
        total += len(files)
    return total


def _get_directory_file_count_and_size(root_dir):
    if not os.path.exists(root_dir):
        return 0, 0

    file_count = 0
    total_size = 0
    for dirpath, _, filenames in os.walk(root_dir):
        file_count += len(filenames)
        for filename in filenames:
            filepath = os.path.join(dirpath, filename)
            if os.path.isfile(filepath):
                try:
                    total_size += os.path.getsize(filepath)
                except OSError:
                    continue
    return file_count, total_size


def _clear_directory_keep_root(dir_path):
    file_count, size_bytes = _get_directory_file_count_and_size(dir_path)
    existed = os.path.exists(dir_path)
    if existed:
        shutil.rmtree(dir_path, ignore_errors=True)
    os.makedirs(dir_path, exist_ok=True)
    return {
        "existed": existed,
        "file_count": file_count,
        "size_bytes": size_bytes,
    }


def _clear_preview_video_local_fields():
    storage = JsonStorage(VIDEO_RECOMMENDATION_JSON_FILE)
    raw_data = storage.read() or {}
    video_recommendations = raw_data.get("video_recommendations", [])
    if not isinstance(video_recommendations, list):
        return {"updated_count": 0, "removed_field_count": 0}

    updated_count = 0
    removed_field_count = 0

    for item in video_recommendations:
        if not isinstance(item, dict):
            continue
        changed = False
        for field_name in _VIDEO_LOCAL_ASSET_FIELDS:
            if field_name in item:
                item.pop(field_name, None)
                removed_field_count += 1
                changed = True
        if changed:
            updated_count += 1

    if removed_field_count > 0:
        raw_data["video_recommendations"] = video_recommendations
        if not storage.write(raw_data):
            raise RuntimeError("写入预览库数据库失败")

    return {
        "updated_count": updated_count,
        "removed_field_count": removed_field_count,
    }


def _build_storage_info(dir_path, label, description=""):
    exists = os.path.exists(dir_path)
    file_count, size_bytes = _get_directory_file_count_and_size(dir_path)
    return {
        "label": label,
        "exists": exists,
        "file_count": file_count,
        "size_bytes": size_bytes,
        "size_mb": round(size_bytes / (1024 * 1024), 2),
        "description": description or label,
    }


def _move_data_dir(src_dir, dst_dir):
    src_abs = os.path.abspath(src_dir)
    dst_abs = os.path.abspath(dst_dir)

    if _is_same_path(src_abs, dst_abs):
        return {
            "migrated": False,
            "moved_files": 0,
            "source": src_abs,
            "target": dst_abs,
            "message": "data_dir 未变化，无需迁移",
        }

    if not os.path.exists(src_abs):
        os.makedirs(dst_abs, exist_ok=True)
        return {
            "migrated": False,
            "moved_files": 0,
            "source": src_abs,
            "target": dst_abs,
            "message": "当前 data 目录不存在，已创建目标目录",
        }

    if _is_sub_path(src_abs, dst_abs) or _is_sub_path(dst_abs, src_abs):
        raise ValueError("目标路径不能与当前 data 目录互为父子目录")

    moved_files = _count_files(src_abs)

    if not os.path.exists(dst_abs):
        os.makedirs(os.path.dirname(dst_abs), exist_ok=True)
        shutil.move(src_abs, dst_abs)
    else:
        if any(os.scandir(dst_abs)):
            raise ValueError("目标 data 目录非空，请选择空目录或新目录")

        for entry in os.listdir(src_abs):
            shutil.move(os.path.join(src_abs, entry), os.path.join(dst_abs, entry))
        try:
            os.rmdir(src_abs)
        except OSError:
            pass

    return {
        "migrated": True,
        "moved_files": moved_files,
        "source": src_abs,
        "target": dst_abs,
        "message": "data 目录迁移完成",
    }


def _should_rebase_to_new_data_dir(path_value, old_data_dir):
    raw = str(path_value or '').strip()
    if not raw:
        return True

    expanded = os.path.expandvars(os.path.expanduser(raw))
    if os.path.isabs(expanded):
        abs_path = os.path.abspath(expanded)
        old_abs = os.path.abspath(old_data_dir)
        return _is_sub_path(old_abs, abs_path)

    # Relative path should continue to follow configured data_dir.
    return True


def _update_third_party_storage_paths(old_data_dir, new_data_dir):
    if not is_third_party_enabled():
        app_logger.info("skip third-party storage path update: third-party integration disabled")
        return

    try:
        from third_party.adapter_factory import AdapterConfig, AdapterFactory
        from third_party.external_api import reset_config_manager

        config_manager = AdapterConfig()
        data_root = os.path.abspath(DATA_DIR)
        new_data_root = os.path.abspath(new_data_dir)

        def _rebase_from_runtime_data(path_value):
            rel = os.path.relpath(os.path.abspath(path_value), data_root)
            return os.path.abspath(os.path.join(new_data_root, rel))

        jm_config = config_manager.get_adapter_config('jmcomic') or {}
        if _should_rebase_to_new_data_dir(jm_config.get('download_dir'), old_data_dir):
            config_manager.set_adapter_config('jmcomic', {
                'download_dir': _rebase_from_runtime_data(JM_PICTURES_DIR)
            })

        pk_config = config_manager.get_adapter_config('picacomic') or {}
        if _should_rebase_to_new_data_dir(pk_config.get('base_dir'), old_data_dir):
            config_manager.set_adapter_config('picacomic', {
                'base_dir': _rebase_from_runtime_data(PK_PICTURES_DIR)
            })

        for adapter_name in AdapterFactory.list_adapters():
            AdapterFactory.reset_instance(adapter_name)
        reset_config_manager()
    except Exception as e:
        error_logger.error(f"更新第三方下载路径失败: {e}")
        raise


def _restart_backend_later(delay_seconds=1.0):
    def _restart_process():
        try:
            time.sleep(delay_seconds)
            python_exe = sys.executable
            argv = [python_exe] + sys.argv
            app_logger.info("检测到 data_dir 变更，后端进程即将重启以应用新配置")
            os.execv(python_exe, argv)
        except Exception as e:
            error_logger.error(f"自动重启后端失败，请手动重启服务: {e}")

    thread = threading.Thread(target=_restart_process, daemon=True)
    thread.start()


@config_bp.route('', methods=['GET'])
def get_config():
    try:
        result = config_service.get_config()
        if result.success:
            cache_stats = recommendation_cache_manager.get_cache_stats()
            config_data = result.data
            config_data['cache_stats'] = cache_stats
            app_logger.info("获取配置成功")
            return success_response(config_data)
        return error_response(500, result.message)
    except Exception as e:
        error_logger.error(f"获取配置失败: {e}")
        return error_response(500, "服务器内部错误")


@config_bp.route('', methods=['PUT'])
def update_config():
    try:
        data = request.json
        if not data:
            return error_response(400, "缺少参数")

        result = config_service.update_config(**data)
        if result.success:
            cache_config = data.get('cache_config', {})
            if cache_config:
                max_size_mb = cache_config.get('recommendation_cache_max_size_mb')
                if max_size_mb:
                    recommendation_cache_manager.update_max_size(max_size_mb)
                    app_logger.info(f"更新推荐缓存最大容量: {max_size_mb}MB")

            app_logger.info(f"更新配置成功: {data}")
            return success_response(result.data)
        return error_response(400, result.message)
    except Exception as e:
        error_logger.error(f"更新配置失败: {e}")
        return error_response(500, "服务器内部错误")


@config_bp.route('/reset', methods=['POST'])
def reset_config():
    try:
        result = config_service.reset_config()
        if result.success:
            recommendation_cache_manager.update_max_size(5120)
            app_logger.info("重置配置成功")
            return success_response(result.data)
        return error_response(500, result.message)
    except Exception as e:
        error_logger.error(f"重置配置失败: {e}")
        return error_response(500, "服务器内部错误")


@config_bp.route('/system', methods=['GET'])
def get_system_config():
    try:
        server_config = _load_server_config()
        configured_data_dir = (
            server_config.get('storage', {}).get('data_dir')
            if isinstance(server_config, dict)
            else './comic_backend/data'
        )
        configured_data_dir = str(configured_data_dir or './comic_backend/data')
        resolved_data_dir = _resolve_data_dir(configured_data_dir)

        return success_response({
            'configured_data_dir': configured_data_dir,
            'resolved_data_dir': resolved_data_dir,
            'current_runtime_data_dir': os.path.abspath(DATA_DIR),
            'requires_restart': not _is_same_path(resolved_data_dir, DATA_DIR),
            'runtime': runtime_capabilities(),
        })
    except Exception as e:
        error_logger.error(f"获取系统配置失败: {e}")
        return error_response(500, "服务器内部错误")


@config_bp.route('/system', methods=['PUT'])
def update_system_config():
    try:
        data = request.json or {}
        data_dir = str(data.get('data_dir', '')).strip()
        if not data_dir:
            return error_response(400, "data_dir 不能为空")

        migrate_data = bool(data.get('migrate_data', True))
        restart_now = bool(data.get('restart_now', True))

        old_runtime_data_dir = os.path.abspath(DATA_DIR)
        new_resolved_data_dir = _resolve_data_dir(data_dir)

        if (not _is_same_path(old_runtime_data_dir, new_resolved_data_dir)) and (
            _is_sub_path(old_runtime_data_dir, new_resolved_data_dir) or _is_sub_path(new_resolved_data_dir, old_runtime_data_dir)
        ):
            return error_response(400, "目标路径不能与当前 data 目录互为父子目录")

        migration_result = {
            'migrated': False,
            'moved_files': 0,
            'source': old_runtime_data_dir,
            'target': new_resolved_data_dir,
            'message': '未执行迁移',
        }

        if migrate_data:
            migration_result = _move_data_dir(old_runtime_data_dir, new_resolved_data_dir)
        else:
            os.makedirs(new_resolved_data_dir, exist_ok=True)
            migration_result['message'] = '未迁移数据，仅创建目标目录'

        server_config = _load_server_config()
        storage_config = server_config.setdefault('storage', {})
        storage_config['data_dir'] = data_dir
        _save_server_config(server_config)

        _update_third_party_storage_paths(old_runtime_data_dir, new_resolved_data_dir)

        changed = not _is_same_path(old_runtime_data_dir, new_resolved_data_dir)
        if changed and restart_now:
            _restart_backend_later(delay_seconds=1.0)

        app_logger.info(
            f"系统配置更新成功: data_dir={data_dir}, resolved={new_resolved_data_dir}, "
            f"migrate_data={migrate_data}, restart_now={restart_now}"
        )

        return success_response({
            'configured_data_dir': data_dir,
            'resolved_data_dir': new_resolved_data_dir,
            'previous_runtime_data_dir': old_runtime_data_dir,
            'requires_restart': changed,
            'restart_scheduled': changed and restart_now,
            'migration': migration_result,
        }, "系统配置更新成功")
    except ValueError as e:
        return error_response(400, str(e))
    except Exception as e:
        error_logger.error(f"更新系统配置失败: {e}")
        return error_response(500, "服务器内部错误")


@config_bp.route('/javdb-cookie-guide', methods=['GET'])
def javdb_cookie_guide():
    try:
        guide_file = 'javdb_cookie_guide.html'
        if os.path.exists(os.path.join(_STATIC_PAGE_DIR, guide_file)):
            return send_from_directory(_STATIC_PAGE_DIR, guide_file)

        fallback_file = 'index.html'
        if os.path.exists(os.path.join(_JAVDB_PLAYER_DIR, fallback_file)):
            return send_from_directory(_JAVDB_PLAYER_DIR, fallback_file)

        return error_response(404, '未找到 JAVDB Cookie 教学页面')
    except Exception as e:
        error_logger.error(f"打开 JAVDB Cookie 教学页面失败: {e}")
        return error_response(500, "服务器内部错误")


@config_bp.route('/javdb-cookie-guide/screenshots/<path:filename>', methods=['GET'])
def javdb_cookie_guide_screenshot(filename):
    for base_dir in (_JAVDB_STATIC_SCREENSHOTS_DIR, _JAVDB_LIB_SCREENSHOTS_DIR):
        file_path = os.path.join(base_dir, filename)
        if os.path.isfile(file_path):
            return send_from_directory(base_dir, filename)
    return error_response(404, 'JAVDB teaching screenshot not found')


@config_bp.route('/cache/stats', methods=['GET'])
def get_cache_stats():
    try:
        stats = recommendation_cache_manager.get_cache_stats()
        return success_response(stats)
    except Exception as e:
        error_logger.error(f"获取缓存统计失败: {e}")
        return error_response(500, "服务器内部错误")


@config_bp.route('/cache/clear', methods=['DELETE'])
def clear_cache():
    try:
        count, freed_size = recommendation_cache_manager.clear_cache()
        freed_mb = freed_size / (1024 * 1024)
        app_logger.info(f"清除缓存完成: 清理 {count} 个目录, 释放 {freed_mb:.2f} MB")
        return success_response({
            "deleted_count": count,
            "freed_size_bytes": freed_size,
            "freed_size_mb": round(freed_mb, 2),
        }, "缓存清除成功")
    except Exception as e:
        error_logger.error(f"清除缓存失败: {e}")
        return error_response(500, "服务器内部错误")


@config_bp.route('/cache/orphan', methods=['DELETE'])
def clean_orphan_cache():
    try:
        count = recommendation_cache_manager.clean_orphan_cache()
        app_logger.info(f"清理孤立缓存完成: 清理 {count} 个目录")
        return success_response({
            "deleted_count": count,
        }, "孤立缓存清理成功")
    except Exception as e:
        error_logger.error(f"清理孤立缓存失败: {e}")
        return error_response(500, "服务器内部错误")


@config_bp.route('/cache/clear-specific', methods=['DELETE'])
def clear_specific_cache():
    try:
        data = request.json or {}
        raw_cache_type = str(data.get('cache_type', 'all') or 'all').strip().lower()
        cache_type = 'comic_preview_cache' if raw_cache_type == 'recommendation_cache' else raw_cache_type

        supported_types = {
            'all',
            'cache',
            'comic_preview_cache',
            'video_preview_page_cache',
        }
        if cache_type not in supported_types:
            return error_response(400, f"不支持的缓存类型: {cache_type}")

        deleted_count = 0
        deleted_file_count = 0
        freed_size_bytes = 0

        def clear_directory(dir_path):
            nonlocal deleted_count, deleted_file_count, freed_size_bytes
            result = _clear_directory_keep_root(dir_path)
            deleted_count += 1
            deleted_file_count += result["file_count"]
            freed_size_bytes += result["size_bytes"]

        if cache_type in ('all', 'cache'):
            clear_directory(CACHE_ROOT_DIR)

        if cache_type in ('all', 'comic_preview_cache'):
            clear_directory(COMIC_RECOMMENDATION_CACHE_DIR)

        local_field_reset = {
            "updated_count": 0,
            "removed_field_count": 0,
        }
        if cache_type in ('all', 'video_preview_page_cache'):
            clear_directory(_VIDEO_PREVIEW_CACHE_DIR)
            local_field_reset = _clear_preview_video_local_fields()

        freed_mb = freed_size_bytes / (1024 * 1024)
        app_logger.info(
            "清除特定缓存完成: "
            f"类型={cache_type}, 清理 {deleted_count} 个目录, 删除 {deleted_file_count} 个文件, "
            f"释放 {freed_mb:.2f} MB, 清理预览库 local 字段={local_field_reset}"
        )
        return success_response({
            "cache_type": cache_type,
            "deleted_count": deleted_count,
            "deleted_file_count": deleted_file_count,
            "freed_size_bytes": freed_size_bytes,
            "freed_size_mb": round(freed_mb, 2),
            "preview_local_fields": local_field_reset,
        }, "缓存清除成功")
    except Exception as e:
        error_logger.error(f"清除特定缓存失败: {e}")
        return error_response(500, "服务器内部错误")


@config_bp.route('/cache/info', methods=['GET'])
def get_cache_info():
    try:
        cache_info = _build_storage_info(
            CACHE_ROOT_DIR,
            "数据缓存",
            "订阅页封面和数据临时缓存",
        )
        comic_preview_cache_info = _build_storage_info(
            COMIC_RECOMMENDATION_CACHE_DIR,
            "漫画预览页缓存",
            "漫画预览页相关缓存资源",
        )
        video_preview_cache_info = _build_storage_info(
            _VIDEO_PREVIEW_CACHE_DIR,
            "视频预览页缓存",
            "视频详情预览视频与高清图缓存",
        )
        data_storage_info = _build_storage_info(
            DATA_DIR,
            "data 总存储",
            "data 目录总占用（含全部子目录）",
        )

        return success_response({
            "cache": cache_info,
            "comic_preview_cache": comic_preview_cache_info,
            "recommendation_cache": comic_preview_cache_info,
            "video_preview_page_cache": video_preview_cache_info,
            "data_storage": data_storage_info,
        })
    except Exception as e:
        error_logger.error(f"获取缓存信息失败: {e}")
        return error_response(500, "服务器内部错误")

