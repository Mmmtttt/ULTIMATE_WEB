import json
import copy
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
    DEFAULT_SERVER_CONFIG,
    resolve_configured_data_dir,
    SERVER_CONFIG_PATH,
    VIDEO_RECOMMENDATION_CACHE_DIR,
    VIDEO_RECOMMENDATION_JSON_FILE,
    get_config_directory_info,
    set_app_config_dir,
)
from core.runtime_profile import is_third_party_enabled, runtime_capabilities
from infrastructure.logger import app_logger, error_logger
from infrastructure.persistence.json_storage import JsonStorage
from infrastructure.recommendation_cache_manager import recommendation_cache_manager
from protocol.config_service import get_plugin_config_service
from protocol.gateway import get_protocol_gateway


config_bp = Blueprint('config', __name__)
config_service = ConfigAppService()

_VIDEO_PREVIEW_CACHE_DIR = VIDEO_RECOMMENDATION_CACHE_DIR
_VIDEO_LOCAL_ASSET_FIELDS = ("cover_path_local", "thumbnail_images_local", "preview_video_local")
_RUNTIME_MOVE_SKIP_TOP_LEVELS = {"logs"}
_KNOWN_DATA_DIR_TOP_LEVELS = {
    "meta_data",
    "comic",
    "video",
    "static",
    "cache",
    "recommendation_cache",
    "logs",
}


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
    return copy.deepcopy(DEFAULT_SERVER_CONFIG)


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
    return resolve_configured_data_dir(path_value)


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


def _looks_like_data_dir(root_dir):
    if not os.path.isdir(root_dir):
        return False

    try:
        entries = {
            str(entry.name or "").strip().lower()
            for entry in os.scandir(root_dir)
            if str(entry.name or "").strip()
        }
    except OSError:
        return False

    if "meta_data" in entries:
        return True
    return bool(entries & _KNOWN_DATA_DIR_TOP_LEVELS)

def _validate_target_data_dir(dst_abs):
    if not os.path.exists(dst_abs):
        return
    if not os.path.isdir(dst_abs):
        raise ValueError("目标 data 路径必须是目录")
    if any(os.scandir(dst_abs)) and (not _looks_like_data_dir(dst_abs)):
        raise ValueError("目标 data 目录非空，请选择空目录或合法 data 目录")


def _move_path_merge(src_path, dst_path):
    if not os.path.exists(src_path):
        return 0

    if os.path.isdir(src_path):
        if os.path.exists(dst_path) and (not os.path.isdir(dst_path)):
            raise ValueError(f"目标路径存在同名文件，无法迁移目录: {dst_path}")
        os.makedirs(dst_path, exist_ok=True)
        moved_files = 0
        for entry in os.listdir(src_path):
            moved_files += _move_path_merge(
                os.path.join(src_path, entry),
                os.path.join(dst_path, entry),
            )
        try:
            os.rmdir(src_path)
        except OSError:
            pass
        return moved_files

    os.makedirs(os.path.dirname(dst_path), exist_ok=True)
    if os.path.isdir(dst_path):
        raise ValueError(f"目标路径存在同名目录，无法迁移文件: {dst_path}")
    if os.path.exists(dst_path):
        os.remove(dst_path)
    shutil.move(src_path, dst_path)
    return 1


def _move_data_dir_contents(src_dir, dst_dir, skip_top_level=None):
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

    _validate_target_data_dir(dst_abs)
    os.makedirs(dst_abs, exist_ok=True)

    moved_files = 0
    skipped_entries = []
    skip_names = {
        str(item or "").strip().lower()
        for item in (skip_top_level or [])
        if str(item or "").strip()
    }

    for entry in os.listdir(src_abs):
        if entry.lower() in skip_names:
            skipped_entries.append(entry)
            continue
        moved_files += _move_path_merge(
            os.path.join(src_abs, entry),
            os.path.join(dst_abs, entry),
        )

    try:
        if not any(os.scandir(src_abs)):
            os.rmdir(src_abs)
    except OSError:
        pass

    message = "data 目录迁移完成"
    mode = "move"
    if skipped_entries:
        message = "data 目录迁移完成，日志目录将在重启后切换"
        mode = "runtime_move"

    return {
        "migrated": moved_files > 0,
        "moved_files": moved_files,
        "source": src_abs,
        "target": dst_abs,
        "mode": mode,
        "skipped_top_level": sorted(skipped_entries),
        "message": message,
    }


def _resolve_plugin_helper(config_key: str, helper_key: str):
    manifest = get_protocol_gateway().get_manifest_by_config_key(str(config_key or "").strip())
    if manifest is None:
        return None

    helper = manifest.get_helper(helper_key)
    if not helper:
        return None

    plugin_root = os.path.dirname(manifest.path)
    helper_file = str(helper.get("file") or "").strip()
    helper_root_dir = str(helper.get("root_dir") or "").strip()
    helper_kind = str(helper.get("kind") or "").strip().lower()

    if not helper_file or helper_kind != "static_page":
        return None

    index_path = os.path.abspath(os.path.join(plugin_root, helper_file))
    asset_root = os.path.abspath(
        os.path.join(plugin_root, helper_root_dir or os.path.dirname(helper_file))
    )

    if not os.path.isfile(index_path):
        return None
    if not os.path.isdir(asset_root):
        return None
    if not _is_sub_path(plugin_root, index_path):
        return None
    if not _is_sub_path(plugin_root, asset_root):
        return None

    return {
        "kind": helper_kind,
        "manifest": manifest,
        "index_dir": os.path.dirname(index_path),
        "index_name": os.path.basename(index_path),
        "asset_root": asset_root,
    }


def _serve_plugin_helper(config_key: str, helper_key: str, filename: str = ""):
    try:
        resolved = _resolve_plugin_helper(config_key, helper_key)
        if resolved is None:
            return error_response(404, "未找到插件帮助页")

        relative_filename = str(filename or "").strip().lstrip("/\\")
        if relative_filename:
            file_path = os.path.join(resolved["asset_root"], relative_filename)
            if not os.path.isfile(file_path):
                return error_response(404, "插件帮助页资源不存在")
            return send_from_directory(resolved["asset_root"], relative_filename)

        return send_from_directory(resolved["index_dir"], resolved["index_name"])
    except Exception as e:
        error_logger.error(
            f"打开插件帮助页失败: config_key={config_key}, helper_key={helper_key}, error={e}"
        )
        return error_response(500, "服务器内部错误")


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
    skip_top_level = _RUNTIME_MOVE_SKIP_TOP_LEVELS if _is_same_path(src_abs, DATA_DIR) else None
    return _move_data_dir_contents(src_abs, dst_abs, skip_top_level=skip_top_level)


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


def _resolve_data_dir_binding_path(new_data_root, manifest, binding):
    field_name = str(
        binding.get("config_field")
        or binding.get("field")
        or ""
    ).strip()
    relative_dir = str(binding.get("relative_dir") or "").strip().replace("\\", "/").strip("/")
    identity = dict(getattr(manifest, "identity", {}) or {})
    host_prefix = str(
        binding.get("host_prefix")
        or identity.get("host_id_prefix")
        or identity.get("platform_label")
        or getattr(manifest, "config_key", "")
        or ""
    ).strip()

    if not field_name or not relative_dir:
        return "", ""

    resolved_relative = relative_dir.format(
        host_prefix=host_prefix,
        config_key=str(getattr(manifest, "config_key", "") or "").strip(),
        plugin_id=str(getattr(manifest, "plugin_id", "") or "").strip(),
    ).replace("/", os.sep)
    return field_name, os.path.abspath(os.path.join(new_data_root, resolved_relative))


def _update_third_party_storage_paths(old_data_dir, new_data_dir):
    if not is_third_party_enabled():
        app_logger.info("skip third-party storage path update: third-party integration disabled")
        return

    try:
        plugin_config_service = get_plugin_config_service()
        gateway = get_protocol_gateway()
        current_config = plugin_config_service.build_response().get("adapters", {})
        new_data_root = os.path.abspath(new_data_dir)

        updates = {}
        for manifest in gateway.list_manifests():
            config_key = str(getattr(manifest, "config_key", "") or "").strip()
            if not config_key:
                continue

            plugin_config = current_config.get(config_key) or {}
            plugin_updates = {}
            for binding in manifest.list_data_dir_bindings():
                field_name, rebound_path = _resolve_data_dir_binding_path(
                    new_data_root,
                    manifest,
                    binding,
                )
                if not field_name or not rebound_path:
                    continue
                if not _should_rebase_to_new_data_dir(plugin_config.get(field_name), old_data_dir):
                    continue
                plugin_updates[field_name] = rebound_path

            if plugin_updates:
                updates[config_key] = plugin_updates

        if updates:
            plugin_config_service.save_updates({"adapters": updates})
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


@config_bp.route('/system/config-dir', methods=['GET'])
def get_system_config_dir():
    try:
        info = get_config_directory_info()
        return success_response(info)
    except Exception as e:
        error_logger.error(f"获取配置目录信息失败: {e}")
        return error_response(500, "服务器内部错误")


@config_bp.route('/system/config-dir', methods=['PUT'])
def update_system_config_dir():
    try:
        data = request.json or {}
        config_dir = str(data.get('config_dir', '')).strip()
        if not config_dir:
            return error_response(400, "config_dir 不能为空")

        migrate_configs = bool(data.get('migrate_configs', True))
        restart_now = bool(data.get('restart_now', True))

        result = set_app_config_dir(config_dir, migrate_existing=migrate_configs)

        changed = bool(result.get('changed', False))
        if changed and restart_now:
            _restart_backend_later(delay_seconds=1.0)

        payload = dict(result or {})
        payload['restart_scheduled'] = bool(changed and restart_now)

        app_logger.info(
            f"配置目录更新成功: config_dir={payload.get('selected_config_dir', '')}, "
            f"migrate_configs={migrate_configs}, restart_now={restart_now}"
        )
        return success_response(payload, "配置目录更新成功")
    except (ValueError, RuntimeError) as e:
        return error_response(400, str(e))
    except Exception as e:
        error_logger.error(f"更新配置目录失败: {e}")
        return error_response(500, "服务器内部错误")


@config_bp.route('/plugin-helpers/<config_key>/<helper_key>', methods=['GET'])
@config_bp.route('/plugin-helpers/<config_key>/<helper_key>/', methods=['GET'])
def get_plugin_helper(config_key, helper_key):
    return _serve_plugin_helper(config_key, helper_key)


@config_bp.route('/plugin-helpers/<config_key>/<helper_key>/<path:filename>', methods=['GET'])
def get_plugin_helper_asset(config_key, helper_key, filename):
    return _serve_plugin_helper(config_key, helper_key, filename=filename)


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

