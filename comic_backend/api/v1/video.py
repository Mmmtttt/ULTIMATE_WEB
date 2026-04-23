"""
视频 API 路由
"""

from flask import Blueprint, request, jsonify, Response, make_response, send_file
from application.video_app_service import VideoAppService
from application.actor_app_service import ActorAppService
from application.config_app_service import ConfigAppService
from application.video_runtime_support import (
    build_video_host_id as runtime_build_video_host_id,
    execute_video_plugin_capability as runtime_execute_video_plugin_capability,
    get_default_video_platform_name as runtime_get_default_video_platform_name,
    get_playback_proxy_client as runtime_get_playback_proxy_client,
    get_video_adapter as runtime_get_video_adapter,
    get_video_platform_query_status as runtime_get_video_platform_query_status,
    resolve_video_manifest_or_error as runtime_resolve_video_manifest_or_error,
    resolve_video_lookup_context as runtime_resolve_video_lookup_context,
)
from infrastructure.common.result import ServiceResult
from infrastructure.logger import app_logger, error_logger
from core.utils import get_current_time
from core.runtime_profile import is_third_party_enabled, get_runtime_profile
from domain.tag.entity import ContentType
import os
import threading
import time
from urllib.parse import parse_qs, urlparse
import mimetypes
from .runtime_guard import require_third_party
from protocol.gateway import get_protocol_gateway
from protocol.presentation import annotate_item, annotate_items

video_bp = Blueprint('video', __name__)
video_service = VideoAppService()
actor_service = ActorAppService()
config_service = ConfigAppService()
_preview_refresh_lock = threading.Lock()
_preview_refresh_last_run = {}
_PREVIEW_REFRESH_COOLDOWN_SECONDS = 180


def success_response(data=None, msg="成功"):
    return jsonify({
        "code": 200,
        "msg": msg,
        "data": data
    })


def error_response(code, msg):
    return jsonify({
        "code": code,
        "msg": msg,
        "data": None
    })


def _get_video_proxy_client():
    """Load a protocol-declared playback proxy client lazily."""
    if not is_third_party_enabled():
        raise RuntimeError(
            f"third-party integration is disabled in current runtime profile: {get_runtime_profile()}"
        )
    return runtime_get_playback_proxy_client(proxy_base_path='/api/v1/video')


def _get_missav_client():
    """Compatibility shim for older tests and callers."""
    return _get_video_proxy_client()


def _build_play_sources(code: str):
    client = _get_missav_client()
    return client.build_sources(code)


@video_bp.route('/list', methods=['GET'])
def video_list():
    try:
        sort_type = request.args.get('sort_type')
        min_score = request.args.get('min_score', type=float)
        max_score = request.args.get('max_score', type=float)
        
        result = video_service.get_video_list(sort_type, min_score, max_score)
        if result.success:
            return success_response(result.data)
        else:
            return error_response(500, result.message)
    except Exception as e:
        error_logger.error(f"获取视频列表失败: {e}")
        return error_response(500, "服务器内部错误")


@video_bp.route('/detail', methods=['GET'])
def video_detail():
    try:
        video_id = request.args.get('video_id')
        if not video_id:
            return error_response(400, "缺少参数")
        
        result = video_service.get_video_detail(video_id)
        if result.success:
            detail = (result.data or {}).copy()
            detail = _ensure_preview_video_detail(detail, source="local")
            _schedule_local_cover_thumbnail_cache(detail, source="local")
            return success_response(detail)
        else:
            return error_response(404, result.message)
    except Exception as e:
        error_logger.error(f"获取视频详情失败: {e}")
        return error_response(500, "服务器内部错误")


@video_bp.route('/preview-video/refresh', methods=['POST'])
@require_third_party(error_response)
def refresh_preview_video():
    """手动刷新预览视频链接并触发下载"""
    try:
        data = request.json or {}
        video_id = str(data.get('video_id') or '').strip()
        source = str(data.get('source') or 'local').strip().lower()
        source = 'preview' if source == 'preview' else 'local'

        if not video_id:
            return error_response(400, "缺少参数: video_id")

        refresh_result = _refresh_preview_video_now(
            video_id=video_id,
            source=source,
            force_download=True
        )
        if not refresh_result.get("success"):
            return error_response(400, refresh_result.get("message", "刷新预览视频失败"))

        return success_response(refresh_result.get("data"), refresh_result.get("message", "预览视频已更新"))
    except Exception as e:
        error_logger.error(f"手动刷新预览视频失败: {e}")
        return error_response(500, "服务端内部错误")


@video_bp.route('/local-metadata/refresh', methods=['POST'])
@require_third_party(error_response)
def refresh_local_video_metadata():
    """Refresh a single LOCAL video metadata from third-party sources."""
    try:
        data = request.json or {}
        video_id = str(data.get('video_id') or '').strip()
        if not video_id:
            return error_response(400, "缺少参数: video_id")

        result = video_service.refresh_local_video_metadata(video_id)
        if result.success:
            return success_response(result.data, result.message or "LOCAL 视频详情已更新")
        return error_response(400, result.message or "LOCAL 视频详情更新失败")
    except Exception as e:
        error_logger.error(f"refresh local video metadata api failed: {e}")
        return error_response(500, "internal server error")


@video_bp.route('/search', methods=['GET'])
def video_search():
    try:
        keyword = request.args.get('keyword')
        if not keyword:
            return error_response(400, "缺少搜索关键词")
        
        result = video_service.search_videos(keyword)
        if result.success:
            return success_response(result.data)
        else:
            return error_response(500, result.message)
    except Exception as e:
        error_logger.error(f"搜索视频失败: {e}")
        return error_response(500, "服务器内部错误")


@video_bp.route('/score', methods=['PUT'])
def update_score():
    try:
        data = request.json
        video_id = data.get('video_id')
        score = data.get('score')
        
        if not video_id or score is None:
            return error_response(400, "缺少参数")
        
        result = video_service.update_video_score(video_id, score)
        if result.success:
            return success_response(result.data)
        else:
            return error_response(400, result.message)
    except Exception as e:
        error_logger.error(f"更新评分失败: {e}")
        return error_response(500, "服务器内部错误")


@video_bp.route('/progress', methods=['PUT'])
def update_progress():
    try:
        data = request.json
        video_id = data.get('video_id')
        unit = data.get('unit')
        
        if not video_id or unit is None:
            return error_response(400, "缺少参数")
        
        result = video_service.update_video_progress(video_id, unit)
        if result.success:
            return success_response(result.data)
        else:
            return error_response(400, result.message)
    except Exception as e:
        error_logger.error(f"更新进度失败: {e}")
        return error_response(500, "服务器内部错误")


@video_bp.route('/trash/list', methods=['GET'])
def trash_list():
    try:
        result = video_service.get_trash_list()
        if result.success:
            return success_response(result.data)
        else:
            return error_response(500, result.message)
    except Exception as e:
        error_logger.error(f"获取回收站列表失败: {e}")
        return error_response(500, "服务器内部错误")


@video_bp.route('/trash/move', methods=['PUT'])
def move_to_trash():
    try:
        data = request.json
        video_id = data.get('video_id')
        
        if not video_id:
            return error_response(400, "缺少参数")
        
        result = video_service.move_to_trash(video_id)
        if result.success:
            return success_response(result.data)
        else:
            return error_response(400, result.message)
    except Exception as e:
        error_logger.error(f"移至回收站失败: {e}")
        return error_response(500, "服务器内部错误")


@video_bp.route('/trash/restore', methods=['PUT'])
def restore_from_trash():
    try:
        data = request.json
        video_id = data.get('video_id')
        
        if not video_id:
            return error_response(400, "缺少参数")
        
        result = video_service.restore_from_trash(video_id)
        if result.success:
            return success_response(result.data)
        else:
            return error_response(400, result.message)
    except Exception as e:
        error_logger.error(f"从回收站恢复失败: {e}")
        return error_response(500, "服务器内部错误")


@video_bp.route('/trash/delete', methods=['DELETE'])
def delete_permanently():
    try:
        video_id = request.args.get('video_id')
        if not video_id:
            return error_response(400, "缺少参数: video_id")
        
        result = video_service.delete_permanently(video_id)
        if result.success:
            return success_response(result.data)
        else:
            return error_response(400, result.message)
    except Exception as e:
        error_logger.error(f"永久删除失败: {e}")
        return error_response(500, "服务器内部错误")


@video_bp.route('/trash/batch-move', methods=['PUT'])
def batch_move_to_trash():
    """批量移动视频到回收站"""
    try:
        data = request.json
        if not data or 'video_ids' not in data:
            return error_response(400, "缺少参数: video_ids")
        
        result = video_service.batch_move_to_trash(data['video_ids'])
        if result.success:
            return success_response(result.data, result.message)
        else:
            return error_response(400, result.message)
    except Exception as e:
        error_logger.error(f"批量移入回收站失败: {e}")
        return error_response(500, "服务器内部错误")


@video_bp.route('/trash/batch-restore', methods=['PUT'])
def batch_restore_from_trash():
    """批量从回收站恢复视频"""
    try:
        data = request.json
        if not data or 'video_ids' not in data:
            return error_response(400, "缺少参数: video_ids")
        
        result = video_service.batch_restore_from_trash(data['video_ids'])
        if result.success:
            return success_response(result.data, result.message)
        else:
            return error_response(400, result.message)
    except Exception as e:
        error_logger.error(f"批量从回收站恢复失败: {e}")
        return error_response(500, "服务器内部错误")


@video_bp.route('/trash/batch-delete', methods=['DELETE'])
def batch_delete_permanently():
    """批量永久删除视频"""
    try:
        data = request.json
        if not data or 'video_ids' not in data:
            return error_response(400, "缺少参数: video_ids")
        
        result = video_service.batch_delete_permanently(data['video_ids'])
        if result.success:
            return success_response(result.data, result.message)
        else:
            return error_response(400, result.message)
    except Exception as e:
        error_logger.error(f"批量永久删除失败: {e}")
        return error_response(500, "服务器内部错误")


@video_bp.route('/import', methods=['POST'])
def import_video():
    try:
        data = request.json
        if not data:
            return error_response(400, "缺少参数")
        
        result = video_service.import_video(data)
        if result.success:
            video_id = result.data.get("id") if isinstance(result.data, dict) else None
            if video_id:
                _schedule_video_asset_cache(
                    video_id=video_id,
                    source="local",
                    cover_url=(result.data or {}).get("cover_path", ""),
                    preview_video=(result.data or {}).get("preview_video", ""),
                    thumbnail_images=(result.data or {}).get("thumbnail_images", []),
                    allow_cover=True,
                    allow_preview_video=_platform_allows_preview_video_download(video_id=video_id),
                )

                recent_result = video_service.apply_recent_import_tags(
                    [video_id],
                    source="local",
                    clear_previous=True
                )
                if not recent_result.success:
                    app_logger.warning(f"更新视频最近导入标签失败: {recent_result.message}")
            return success_response(result.data, result.message)
        else:
            return error_response(400, result.message)
    except Exception as e:
        error_logger.error(f"导入视频失败: {e}")
        return error_response(500, "服务器内部错误")


@video_bp.route('/import/batch', methods=['POST'])
def batch_import():
    try:
        data = request.json
        videos = data.get('videos', [])
        
        if not videos:
            return error_response(400, "缺少视频数据")
        
        result = video_service.batch_import_videos(videos)
        if result.success:
            imported_ids = result.data.get("imported_ids", []) if isinstance(result.data, dict) else []
            if imported_ids:
                imported_id_set = {str(item_id) for item_id in imported_ids if item_id}
                for video_item in videos:
                    item_id = str((video_item or {}).get("id") or "").strip()
                    if not item_id or item_id not in imported_id_set:
                        continue
                    _schedule_video_asset_cache(
                        video_id=item_id,
                        source="local",
                        cover_url=(video_item or {}).get("cover_path", "") or (video_item or {}).get("cover_url", ""),
                        preview_video=(video_item or {}).get("preview_video", ""),
                        thumbnail_images=(video_item or {}).get("thumbnail_images", []),
                        allow_cover=True,
                        allow_preview_video=_platform_allows_preview_video_download(
                            platform=(video_item or {}).get("platform", ""),
                            video_id=item_id
                        ),
                    )

                recent_result = video_service.apply_recent_import_tags(
                    imported_ids,
                    source="local",
                    clear_previous=True
                )
                if not recent_result.success:
                    app_logger.warning(f"更新视频最近导入标签失败: {recent_result.message}")
            return success_response(result.data)
        else:
            return error_response(400, result.message)
    except Exception as e:
        error_logger.error(f"批量导入失败: {e}")
        return error_response(500, "服务器内部错误")


@video_bp.route('/local-import/from-path', methods=['POST'])
def local_import_from_path():
    try:
        data = request.json or {}
        source_path = str(data.get('source_path') or '').strip()
        import_mode = str(data.get('import_mode') or '').strip()
        if not source_path:
            return error_response(400, "missing parameter: source_path")

        result = video_service.import_local_videos_from_path(source_path, import_mode=import_mode)
        if result.success:
            return success_response(result.data, result.message)
        return error_response(400, result.message)
    except Exception as e:
        error_logger.error(f"local video import from path failed: {e}")
        return error_response(500, "internal server error")


@video_bp.route('/local-stream/<video_id>', methods=['GET'])
def stream_local_video(video_id):
    try:
        resolved = video_service.resolve_local_video_file_path(video_id)
        if not resolved or not os.path.isfile(resolved):
            return make_response("Not Found", 404)

        guessed_type, _ = mimetypes.guess_type(resolved)
        response = make_response(
            send_file(
                resolved,
                mimetype=guessed_type or "application/octet-stream",
                conditional=True,
            )
        )
        response.headers["Accept-Ranges"] = "bytes"
        return response
    except Exception as e:
        error_logger.error(f"stream local video failed: id={video_id}, error={e}")
        return make_response("Internal Server Error", 500)


@video_bp.route('/tag/<tag_id>', methods=['GET'])
def get_by_tag(tag_id):
    try:
        result = video_service.get_videos_by_tag(tag_id)
        if result.success:
            return success_response(result.data)
        else:
            return error_response(500, result.message)
    except Exception as e:
        error_logger.error(f"获取标签视频失败: {e}")
        return error_response(500, "服务器内部错误")


@video_bp.route('/tags', methods=['GET'])
def get_tags():
    try:
        from application.tag_app_service import TagAppService
        tag_service = TagAppService()
        result = tag_service.get_tag_list(ContentType.VIDEO)
        
        if result.success:
            app_logger.info(f"获取标签列表成功，共 {len(result.data)} 个标签")
            return success_response(result.data)
        else:
            return error_response(500, result.message)
    except Exception as e:
        error_logger.error(f"获取标签列表失败: {e}")
        return error_response(500, "服务器内部错误")


@video_bp.route('/tag/bind', methods=['PUT'])
def bind_tags():
    try:
        data = request.json
        if not data or 'video_id' not in data or 'tag_id_list' not in data:
            return error_response(400, "缺少参数: video_id 或 tag_id_list")
        
        video_id = data['video_id']
        tag_id_list = data['tag_id_list']
        
        result = video_service.bind_tags(video_id, tag_id_list)
        if result.success:
            app_logger.info(f"绑定标签成功: {video_id}, 标签: {tag_id_list}")
            return success_response(result.data)
        else:
            return error_response(400, result.message)
    except Exception as e:
        error_logger.error(f"绑定标签失败: {e}")
        return error_response(500, "服务器内部错误")


@video_bp.route('/edit', methods=['PUT'])
def edit_video():
    try:
        data = request.json
        if not data or 'video_id' not in data:
            return error_response(400, "missing parameter: video_id")

        video_id = data['video_id']
        meta = {
            'title': data.get('title'),
            'code': data.get('code'),
            'date': data.get('date'),
            'series': data.get('series'),
            'creator': data.get('creator'),
            'author': data.get('author'),
            'actors': data.get('actors'),
            'desc': data.get('desc'),
            'cover_path': data.get('cover_path')
        }
        meta = {k: v for k, v in meta.items() if v is not None}

        result = video_service.update_meta(video_id, meta)
        if result.success:
            app_logger.info(f"edit video success: {video_id}")
            return success_response(result.data)
        else:
            return error_response(400, result.message)
    except Exception as e:
        error_logger.error(f"edit video failed: {e}")
        return error_response(500, "internal server error")


@video_bp.route('/filter', methods=['GET'])
def filter_videos():
    try:
        include_tag_ids = request.args.getlist('include_tag_ids')
        exclude_tag_ids = request.args.getlist('exclude_tag_ids')
        authors = request.args.getlist('authors')
        list_ids = request.args.getlist('list_ids')
        
        if authors or list_ids:
            result = video_service.filter_multi(
                include_tags=include_tag_ids if include_tag_ids else None,
                exclude_tags=exclude_tag_ids if exclude_tag_ids else None,
                authors=authors if authors else None,
                list_ids=list_ids if list_ids else None
            )
        else:
            result = video_service.filter_by_tags(include_tag_ids, exclude_tag_ids)
        
        if result.success:
            app_logger.info(f"筛选成功: 包含 {include_tag_ids}, 排除 {exclude_tag_ids}, 作者 {authors}, 清单 {list_ids}, 结果数量: {len(result.data)}")
            return success_response(result.data)
        else:
            return error_response(500, result.message)
    except Exception as e:
        error_logger.error(f"筛选失败: {e}")
        return error_response(500, "服务器内部错误")


@video_bp.route('/tag/batch-add', methods=['PUT'])
def batch_add_tags():
    try:
        data = request.json
        if not data or 'video_ids' not in data or 'tag_ids' not in data:
            return error_response(400, "缺少参数: video_ids 或 tag_ids")
        
        video_ids = data['video_ids']
        tag_ids = data['tag_ids']
        
        result = video_service.batch_add_tags(video_ids, tag_ids)
        if result.success:
            app_logger.info(f"批量添加标签成功: {len(video_ids)}个视频, 标签: {tag_ids}")
            return success_response(result.data)
        else:
            return error_response(400, result.message)
    except Exception as e:
        error_logger.error(f"批量添加标签失败: {e}")
        return error_response(500, "服务器内部错误")


@video_bp.route('/tag/batch-remove', methods=['PUT'])
def batch_remove_tags():
    try:
        data = request.json
        if not data or 'video_ids' not in data or 'tag_ids' not in data:
            return error_response(400, "缺少参数: video_ids 或 tag_ids")
        
        video_ids = data['video_ids']
        tag_ids = data['tag_ids']
        
        result = video_service.batch_remove_tags(video_ids, tag_ids)
        if result.success:
            app_logger.info(f"批量移除标签成功: {len(video_ids)}个视频, 标签: {tag_ids}")
            return success_response(result.data)
        else:
            return error_response(400, result.message)
    except Exception as e:
        error_logger.error(f"批量移除标签失败: {e}")
        return error_response(500, "服务器内部错误")


@video_bp.route('/actor/<actor_name>', methods=['GET'])
def get_by_actor(actor_name):
    try:
        result = video_service.get_videos_by_actor(actor_name)
        if result.success:
            return success_response(result.data)
        else:
            return error_response(500, result.message)
    except Exception as e:
        error_logger.error(f"获取演员视频失败: {e}")
        return error_response(500, "服务器内部错误")


def get_video_adapter(platform_name="", *args, **kwargs):
    """获取协议视频平台客户端。"""
    return runtime_get_video_adapter(platform_name, *args, **kwargs)


def _get_video_platform_query_status(platform_name: str) -> dict:
    return runtime_get_video_platform_query_status(platform_name)


def _get_default_video_platform_name() -> str:
    return runtime_get_default_video_platform_name()


def _resolve_video_lookup_context(
    *,
    video_id: str = "",
    code: str = "",
    platform_name: str = "",
):
    return runtime_resolve_video_lookup_context(
        video_id=video_id,
        code=code,
        platform_name=platform_name,
    )


def _build_video_host_id(platform_name: str, original_id: str) -> str:
    return runtime_build_video_host_id(platform_name, original_id)


def _manifest_nested_bool(manifest, path: tuple[str, ...], default: bool = True) -> bool:
    current = getattr(manifest, "resource_policy", {}) if manifest is not None else {}
    if not isinstance(current, dict):
        return default
    for key in path:
        if not isinstance(current, dict):
            return default
        current = current.get(key)
    if current is None:
        return default
    return bool(current)


def _platform_supports_preview_video(platform: str = "", video_id: str = "") -> bool:
    _, _, manifest = _resolve_video_lookup_context(platform_name=platform, video_id=video_id)
    return _manifest_nested_bool(
        manifest,
        ("assets", "preview_video", "available"),
        default=True,
    )


def _platform_allows_preview_video_download(platform: str = "", video_id: str = "") -> bool:
    _, _, manifest = _resolve_video_lookup_context(platform_name=platform, video_id=video_id)
    return _manifest_nested_bool(
        manifest,
        ("assets", "preview_video", "download_enabled"),
        default=True,
    )


def get_all_video_adapters(*args, **kwargs):
    """获取所有视频平台适配器"""
    adapters = {}
    for manifest in get_protocol_gateway().list_manifests(media_type="video", capability="catalog.search"):
        identity = dict(getattr(manifest, "identity", {}) or {})
        platform = str(
            identity.get("platform_label")
            or getattr(manifest, "config_key", "")
            or getattr(manifest, "plugin_id", "")
            or ""
        ).strip().lower()
        if not platform:
            continue
        try:
            adapters[platform] = get_video_adapter(platform, *args, **kwargs)
        except Exception as e:
            error_logger.error(f"获取视频平台适配器 {platform} 失败: {e}")
    return adapters


def to_proxy_image_url(
    url: str,
    *,
    asset_kind: str = "image",
    video_id: str = "",
    platform_name: str = "",
    content_id: str = "",
) -> str:
    """Resolve frontend-safe asset URLs using plugin resource policy."""
    return VideoAppService.to_frontend_asset_url(
        url,
        asset_kind=asset_kind,
        video_id=video_id,
        platform_name=platform_name,
        content_id=content_id,
        proxy_base_path="/api/v1/video/proxy2",
    )


_PREVIEW_VIDEO_MEDIA_MARKERS = (".mp4", ".m3u8", ".webm", ".mov", ".m4v")


def _normalize_str_list(value) -> list:
    if not isinstance(value, list):
        return []
    return [str(item or "").strip() for item in value if str(item or "").strip()]


def _ensure_local_asset_fields(video_data: dict) -> dict:
    if not isinstance(video_data, dict):
        return video_data

    video_data["cover_path_local"] = str(video_data.get("cover_path_local", "") or "").strip()
    video_data["thumbnail_images_local"] = _normalize_str_list(video_data.get("thumbnail_images_local", []))
    return video_data


def _sanitize_preview_video_value(raw_url: str) -> str:
    if not raw_url:
        return ""

    url = str(raw_url).strip()
    if not url:
        return ""

    lowered = url.lower()
    if lowered.startswith("blob:"):
        return ""

    if lowered.startswith("/api/v1/video/proxy2") or lowered.startswith("/v1/video/proxy2"):
        return url
    if lowered.startswith("/proxy2?") or lowered.startswith("/proxy/"):
        return url

    if lowered.startswith("//"):
        url = f"https:{url}"
        lowered = url.lower()

    if lowered.startswith("/media/"):
        return url if any(marker in lowered for marker in _PREVIEW_VIDEO_MEDIA_MARKERS) else ""

    if lowered.startswith("http://") or lowered.startswith("https://"):
        return url if any(marker in lowered for marker in _PREVIEW_VIDEO_MEDIA_MARKERS) else ""

    return url if any(marker in lowered for marker in _PREVIEW_VIDEO_MEDIA_MARKERS) else ""


def _should_refresh_preview_video_url(url: str) -> bool:
    normalized = _sanitize_preview_video_value(url)
    if not normalized:
        return False

    try:
        parsed = urlparse(normalized)
        host = str(parsed.netloc or "").strip().lower()
        lowered = normalized.lower()
    except Exception:
        return False

    for manifest in get_protocol_gateway().list_manifests(media_type="video"):
        policy = dict(getattr(manifest, "resource_policy", {}) or {})
        assets = dict(policy.get("assets") or {})
        preview_policy = dict(assets.get("preview_video") or {})
        refresh_hint = dict(preview_policy.get("refresh_hint") or {})
        if not refresh_hint:
            continue

        match_hosts = [
            str(item or "").strip().lower()
            for item in (refresh_hint.get("match_hosts") or [])
            if str(item or "").strip()
        ]
        path_prefixes = [
            str(item or "").strip().lower()
            for item in (refresh_hint.get("path_prefixes") or [])
            if str(item or "").strip()
        ]
        host_matches = bool(match_hosts) and any(candidate in host for candidate in match_hosts)
        path_matches = bool(path_prefixes) and any(lowered.startswith(prefix) for prefix in path_prefixes)
        if match_hosts or path_prefixes:
            if not host_matches and not path_matches:
                continue

        mode = str(refresh_hint.get("mode") or "").strip().lower()
        if mode not in {"signed_query_expire", "query_expire"}:
            continue

        query_param = str(refresh_hint.get("query_param") or "t").strip() or "t"
        lead_seconds = int(refresh_hint.get("lead_seconds") or 120)
        refresh_when_missing = bool(refresh_hint.get("refresh_when_missing"))

        try:
            query = parse_qs(parsed.query or "")
            expire_raw = (query.get(query_param) or [None])[0]
            if expire_raw and str(expire_raw).isdigit():
                expire_at = int(expire_raw)
                return expire_at <= int(time.time()) + lead_seconds
        except Exception:
            return refresh_when_missing

        return refresh_when_missing

    return False


def _schedule_preview_video_refresh(video_data: dict, source: str = "local"):
    if not isinstance(video_data, dict):
        return

    video_id = str(video_data.get("id") or "").strip()
    platform_name = str(video_data.get("platform") or "").strip().lower()
    code = str(video_data.get("code") or "").strip()
    if not video_id and not code:
        return
    if not _platform_supports_preview_video(platform=platform_name, video_id=video_id):
        return

    refresh_key = f"{source}:{video_id or code}"
    now = time.time()
    with _preview_refresh_lock:
        last_refresh = _preview_refresh_last_run.get(refresh_key, 0)
        if now - last_refresh < _PREVIEW_REFRESH_COOLDOWN_SECONDS:
            return
        _preview_refresh_last_run[refresh_key] = now

    def worker():
        resolved_platform, lookup_id, _manifest = _resolve_video_lookup_context(
            video_id=video_id,
            code=code,
            platform_name=platform_name,
        )
        lookup = lookup_id or code or video_id
        if not lookup:
            return

        try:
            adapter = get_video_adapter(resolved_platform)
            detail = adapter.get_video_detail(lookup)
            if not detail and code and hasattr(adapter, "get_video_by_code"):
                detail = adapter.get_video_by_code(code)

            recovered_preview = _sanitize_preview_video_value((detail or {}).get("preview_video", ""))
            if not recovered_preview or not video_id:
                return

            video_service.update_preview_video(video_id, recovered_preview, source=source)
            if _should_auto_download_preview_assets(source):
                video_service.cache_preview_video_async(video_id, recovered_preview, source=source)
        except Exception as e:
            app_logger.warning(f"async refresh preview video failed: id={video_id}, code={code}, error={e}")

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()


def _refresh_preview_video_now(video_id: str, source: str = "local", force_download: bool = True) -> dict:
    source_key = "preview" if str(source or "").strip().lower() == "preview" else "local"
    repo = video_service._get_repo_by_source(source_key)
    current_video = repo.get_by_id(video_id)
    if not current_video:
        return {"success": False, "message": "视频不存在"}

    current_data = current_video.to_dict() if hasattr(current_video, "to_dict") else {}
    code = str(current_data.get("code") or "").strip()
    platform_name = str(current_data.get("platform") or "").strip().lower()
    if not _platform_supports_preview_video(platform=platform_name, video_id=video_id):
        return {"success": False, "message": "当前平台未声明预览视频能力"}
    platform_name, lookup_id, _manifest = _resolve_video_lookup_context(
        video_id=video_id,
        code=code,
        platform_name=platform_name,
    )

    lookup = lookup_id or code or video_id
    if not lookup:
        return {"success": False, "message": "缺少可用于刷新的视频标识"}

    try:
        adapter = get_video_adapter(platform_name)
        detail = adapter.get_video_detail(lookup)
        if not detail and code and hasattr(adapter, "get_video_by_code"):
            detail = adapter.get_video_by_code(code)
    except Exception as e:
        return {"success": False, "message": f"获取平台预览视频失败: {e}"}

    refreshed_preview = _sanitize_preview_video_value((detail or {}).get("preview_video", ""))
    if not refreshed_preview:
        return {"success": False, "message": "未获取到可用预览视频链接"}

    if not video_service.update_preview_video(video_id, refreshed_preview, source=source_key):
        return {"success": False, "message": "回写预览视频链接失败"}

    old_local_preview = str(getattr(current_video, "preview_video_local", "") or "").strip()
    if old_local_preview:
        video_service._remove_preview_video_file(old_local_preview)
    video_service.update_preview_video_local(video_id, "", source=source_key)

    cover_url = str((detail or {}).get("cover_url", "") or "").strip()
    thumbnail_images = (detail or {}).get("thumbnail_images", [])
    
    app_logger.info(f"刷新预览视频: video_id={video_id}, source={source_key}, force_download={force_download}, cover_url={cover_url}, thumbnail_count={len(thumbnail_images)}")
    
    if force_download:
        app_logger.info(f"强制下载模式: 开始下载封面、缩略图和预览视频")
        if cover_url:
            video_service.cache_cover_to_static_async(video_id, cover_url, source=source_key)
        
        if thumbnail_images:
            video_service.cache_thumbnail_images_async(video_id, thumbnail_images, source=source_key, force=True)
        
        video_service.cache_preview_video_async(
            video_id,
            refreshed_preview,
            source=source_key,
            force=force_download
        )
    elif _should_auto_download_preview_assets(source_key):
        app_logger.info(f"自动下载模式: 使用_schedule_video_asset_cache")
        _schedule_video_asset_cache(
            video_id=video_id,
            source=source_key,
            cover_url=cover_url,
            preview_video=refreshed_preview,
            thumbnail_images=thumbnail_images,
        )
    else:
        app_logger.info(f"自动下载已关闭，跳过资源下载")

    latest_video = repo.get_by_id(video_id)
    latest_data = latest_video.to_dict() if latest_video and hasattr(latest_video, "to_dict") else {}
    latest_data = _ensure_preview_video_detail(latest_data, source=source_key)
    return {
        "success": True,
        "message": "预览视频链接已刷新，后台开始重新下载",
        "data": latest_data
    }


def _ensure_preview_video_detail(video_data: dict, source: str = "local") -> dict:
    if not isinstance(video_data, dict):
        return video_data

    _ensure_local_asset_fields(video_data)
    video_data["preview_video_local"] = _sanitize_preview_video_value(video_data.get("preview_video_local", ""))

    platform_name = str(video_data.get("platform") or "").strip().lower()
    video_id = str(video_data.get("id") or "").strip()
    if not _platform_supports_preview_video(platform=platform_name, video_id=video_id):
        video_data["preview_video"] = ""
        return video_data

    normalized_preview = _sanitize_preview_video_value(video_data.get("preview_video", ""))
    if normalized_preview:
        video_data["preview_video"] = normalized_preview
        if _should_refresh_preview_video_url(normalized_preview):
            _schedule_preview_video_refresh(video_data, source=source)
        return video_data

    video_data["preview_video"] = ""
    _schedule_preview_video_refresh(video_data, source=source)
    return video_data


def _resolve_protocol_video_platform_name(video_data: dict) -> str:
    if not isinstance(video_data, dict):
        return ""

    platform_name = str(video_data.get("platform") or "").strip().lower()
    video_id = str(video_data.get("id") or "").strip()
    code = str(video_data.get("code") or "").strip()

    resolved_platform, _lookup_id, _manifest = _resolve_video_lookup_context(
        video_id=video_id,
        code=code,
        platform_name=platform_name,
    )
    return str(resolved_platform or platform_name or "").strip().lower()


def _decorate_video_recommendation_item(
    video_data: dict,
    *,
    tag_map: dict | None = None,
    include_preview_detail: bool = False,
) -> dict:
    if not isinstance(video_data, dict):
        return {}

    decorated = dict(video_data)
    decorated["source"] = "preview"
    _ensure_local_asset_fields(decorated)

    video_tag_ids = decorated.get("tag_ids", []) or []
    normalized_tag_map = tag_map if isinstance(tag_map, dict) else {}
    decorated["tags"] = [
        {"id": tid, "name": normalized_tag_map.get(tid, tid)}
        for tid in video_tag_ids
    ]

    if include_preview_detail:
        decorated = _ensure_preview_video_detail(decorated, source="preview")
    else:
        decorated["preview_video"] = _sanitize_preview_video_value(decorated.get("preview_video", ""))
        decorated["preview_video_local"] = _sanitize_preview_video_value(decorated.get("preview_video_local", ""))

    platform_name = _resolve_protocol_video_platform_name(decorated)
    if platform_name:
        decorated = annotate_item(
            decorated,
            platform_name=platform_name,
            media_type="video",
        )

    return decorated


def _decorate_video_recommendation_items(
    videos: list[dict] | None,
    *,
    tag_map: dict | None = None,
    include_preview_detail: bool = False,
) -> list[dict]:
    return [
        _decorate_video_recommendation_item(
            video,
            tag_map=tag_map,
            include_preview_detail=include_preview_detail,
        )
        for video in (videos or [])
        if isinstance(video, dict)
    ]

def _get_preview_import_auto_download_enabled() -> bool:
    try:
        result = config_service.get_config()
        if not result.success or not isinstance(result.data, dict):
            return True
        return bool(result.data.get("auto_download_preview_assets_for_preview_import", False))
    except Exception as e:
        app_logger.warning(f"read preview import asset config failed: {e}")
        return True


def _should_auto_download_preview_assets(source: str = "local") -> bool:
    source_key = str(source or "").strip().lower()
    if source_key != "preview":
        return True
    return _get_preview_import_auto_download_enabled()


def _schedule_video_asset_cache(
    *,
    video_id: str,
    source: str,
    cover_url: str = "",
    preview_video: str = "",
    thumbnail_images=None,
    allow_cover: bool = True,
    allow_preview_video: bool = True,
):
    if not video_id:
        return

    cover = str(cover_url or "").strip()
    preview = _sanitize_preview_video_value(preview_video or "")
    thumbs = [str(item or "").strip() for item in (thumbnail_images or []) if str(item or "").strip()]
    auto_download_enabled = _should_auto_download_preview_assets(source)
    allow_preview_video = bool(allow_preview_video) and _platform_allows_preview_video_download(video_id=video_id)

    if allow_cover and cover:
        # 封面始终下载，不受预览库自动下载开关影响
        video_service.cache_cover_to_static_async(video_id, cover, source=source)

    if not auto_download_enabled:
        app_logger.info(f"预览库资源下载开关已关闭，跳过预览图/预览视频缓存: id={video_id}, source={source}")
        return

    if thumbs:
        video_service.cache_thumbnail_images_async(video_id, thumbs, source=source)

    if allow_preview_video and preview:
        video_service.cache_preview_video_async(video_id, preview, source=source)


def _is_source_preview_asset(path: str) -> bool:
    normalized = str(path or "").strip()
    if not normalized:
        return False
    if normalized.startswith("/media/"):
        return True
    return False


def _schedule_local_cover_thumbnail_cache(video_data: dict, source: str = "local"):
    if not isinstance(video_data, dict):
        return

    source_key = "preview" if str(source or "").strip().lower() == "preview" else "local"
    if source_key != "local":
        return

    video_id = str(video_data.get("id") or "").strip()
    if not video_id:
        return

    _ensure_local_asset_fields(video_data)

    cover_local = str(video_data.get("cover_path_local") or "").strip()
    cover_remote = str(video_data.get("cover_path") or "").strip()
    cover_candidate = cover_local or cover_remote

    thumbnails_local = _normalize_str_list(video_data.get("thumbnail_images_local", []))
    thumbnails_remote = _normalize_str_list(video_data.get("thumbnail_images", []))
    thumbnails = thumbnails_local if thumbnails_local else thumbnails_remote

    should_cache_cover = (
        bool(cover_candidate)
        and not _is_source_preview_asset(cover_candidate)
        and not str(cover_candidate).strip().startswith("/static/cover/")
    )
    should_cache_thumbs = any(not _is_source_preview_asset(item) for item in thumbnails)

    if not should_cache_cover and not should_cache_thumbs:
        return

    _schedule_video_asset_cache(
        video_id=video_id,
        source=source_key,
        cover_url=cover_candidate if should_cache_cover else "",
        thumbnail_images=thumbnails if should_cache_thumbs else [],
        allow_cover=should_cache_cover,
        allow_preview_video=False,
    )


def _resolve_video_manifest_or_error(platform_name: str, capability: str | None = None):
    return runtime_resolve_video_manifest_or_error(platform_name, capability=capability)


def _execute_video_plugin_capability(platform_name: str, capability: str, params: dict | None = None):
    return runtime_execute_video_plugin_capability(platform_name, capability, params=params)


def _get_video_platform_health_status(platform_name: str):
    _platform, _manifest, payload = _execute_video_plugin_capability(
        platform_name,
        "health.query.status",
    )
    return dict(payload or {})


def _read_video_tag_search_params() -> tuple[int, list[str]]:
    page = request.args.get('page', 1, type=int) or 1
    page = max(page, 1)

    requested_tag_ids = request.args.getlist('tag_ids')
    if not requested_tag_ids:
        csv_tag_ids = (request.args.get('tag_ids') or '').strip()
        if csv_tag_ids:
            requested_tag_ids = [part.strip() for part in csv_tag_ids.split(',') if part.strip()]
    return page, requested_tag_ids


def _video_platform_health_status_response(platform_name: str):
    try:
        return success_response(_get_video_platform_health_status(platform_name))
    except Exception as e:
        error_logger.error(f"检查视频平台配置状态失败 platform={platform_name}: {e}")
        return error_response(500, "server error")


def _video_taxonomy_tags_response(platform_name: str):
    try:
        keyword = (request.args.get('keyword') or '').strip().lower()
        category_filter = (request.args.get('category') or '').strip().lower()
        _platform, _manifest, payload = _execute_video_plugin_capability(
            platform_name,
            "taxonomy.tags",
            params={
                "keyword": keyword,
                "category": category_filter,
            },
        )
        return success_response(dict(payload or {}))
    except Exception as e:
        error_logger.error(f"获取视频平台标签失败 platform={platform_name}: {e}")
        return error_response(500, "server error")


def _video_tag_search_response(platform_name: str):
    try:
        page, requested_tag_ids = _read_video_tag_search_params()

        resolved_platform_name, manifest, payload = _execute_video_plugin_capability(
            platform_name,
            "taxonomy.tag_search",
            params={
                "page": page,
                "tag_ids": requested_tag_ids,
            },
        )

        result = dict(payload or {})
        works = result.get('videos') or result.get('works') or []
        videos = []

        for work in works:
            video = dict(work or {})
            video['platform'] = resolved_platform_name
            content_id = str(video.get('video_id') or video.get('id') or video.get('code') or "").strip()
            if video.get('cover_url'):
                video['cover_url'] = to_proxy_image_url(
                    video.get('cover_url'),
                    asset_kind="cover",
                    video_id=content_id,
                    platform_name=resolved_platform_name,
                    content_id=content_id,
                )
            if video.get('thumbnail_url'):
                video['thumbnail_url'] = to_proxy_image_url(
                    video.get('thumbnail_url'),
                    asset_kind="image",
                    video_id=content_id,
                    platform_name=resolved_platform_name,
                    content_id=content_id,
                )
            videos.append(
                annotate_item(
                    video,
                    plugin_id=manifest.plugin_id,
                    media_type="video",
                    capability="taxonomy.tag_search",
                )
            )

        return success_response({
            "platform": resolved_platform_name,
            "page": result.get('page', page),
            "has_next": result.get('has_next', False),
            "total_pages": result.get('total_pages'),
            "videos": videos,
            "query": result.get('query'),
            "requested_tag_ids": result.get('requested_tag_ids', requested_tag_ids),
            "effective_tag_ids": result.get('effective_tag_ids', []),
            "invalid_tag_ids": result.get('invalid_tag_ids', []),
            "overridden_tag_ids": result.get('overridden_tag_ids', []),
        })
    except ValueError as e:
        error_logger.error(f"视频平台标签搜索失败(参数) platform={platform_name}: {e}")
        return error_response(400, str(e))
    except PermissionError as e:
        error_logger.error(f"视频平台标签搜索失败(权限) platform={platform_name}: {e}")
        return error_response(401, str(e))
    except RuntimeError as e:
        error_logger.error(f"视频平台标签搜索失败(配置) platform={platform_name}: {e}")
        return error_response(400, str(e))
    except Exception as e:
        error_logger.error(f"视频平台标签搜索失败 platform={platform_name}: {e}")
        return error_response(500, "server error")


@video_bp.route('/third-party/search', methods=['GET'])
@require_third_party(error_response)
def third_party_search():
    try:
        keyword = request.args.get('keyword')
        platform = request.args.get('platform', 'all')
        page = request.args.get('page', 1, type=int)
        
        if not keyword:
            return error_response(400, "缺少搜索关键词")
        
        app_logger.info(f"开始搜索视频，平台: {platform}, 关键词: {keyword}, 页码: {page}")

        normalized_platform = str(platform or "").strip().lower()
        search_plugins = []
        search_lookup = {}
        for manifest in get_protocol_gateway().list_manifests(media_type="video", capability="catalog.search"):
            identity = dict(getattr(manifest, "identity", {}) or {})
            canonical_platform = str(
                identity.get("platform_label")
                or manifest.config_key
                or manifest.name
                or ""
            ).strip().lower()
            aliases = {
                canonical_platform,
                str(identity.get("host_id_prefix") or "").strip().lower(),
                str(manifest.config_key or "").strip().lower(),
                *[
                    str(item or "").strip().lower()
                    for item in getattr(manifest, "identity_aliases", []) or []
                    if str(item or "").strip()
                ],
            }
            aliases.discard("")
            if not canonical_platform or not aliases:
                continue

            descriptor = {
                "manifest": manifest,
                "canonical_platform": canonical_platform,
                "aliases": sorted(aliases),
            }
            search_plugins.append(descriptor)
            for alias in aliases:
                search_lookup[alias] = descriptor

        supported_platforms = sorted({item["canonical_platform"] for item in search_plugins})
        if normalized_platform == 'all':
            platforms_to_search = search_plugins
        else:
            descriptor = search_lookup.get(normalized_platform)
            if descriptor is None:
                return error_response(400, f"不支持的视频平台: {platform}，支持的平台: {supported_platforms}")
            platforms_to_search = [descriptor]

        all_videos = []
        platform_results = {}
        platform_errors = {}
        
        for descriptor in platforms_to_search:
            manifest = descriptor["manifest"]
            plat = descriptor["canonical_platform"]
            status = _get_video_platform_query_status(plat)
            if not bool(status.get("configured", False)):
                platform_errors[plat] = str(status.get("message") or f"{plat} 平台未配置查询凭据")
                if normalized_platform != "all":
                    return error_response(400, platform_errors[plat])
                continue

            try:
                adapter = get_video_adapter(plat)
                result = adapter.search_videos(keyword, page=page, max_pages=1)
                videos = annotate_items(
                    result.get('videos', []),
                    plugin_id=manifest.plugin_id,
                    media_type="video",
                    capability="catalog.search",
                )
                
                for video in videos:
                    video['platform'] = plat
                    content_id = str(video.get('video_id') or video.get('id') or video.get('code') or "").strip()
                    if video.get('cover_url'):
                        video['cover_url'] = to_proxy_image_url(
                            video.get('cover_url'),
                            asset_kind="cover",
                            video_id=content_id,
                            platform_name=plat,
                            content_id=content_id,
                        )
                    if video.get('thumbnail_url'):
                        video['thumbnail_url'] = to_proxy_image_url(
                            video.get('thumbnail_url'),
                            asset_kind="image",
                            video_id=content_id,
                            platform_name=plat,
                            content_id=content_id,
                        )
                
                platform_results[plat] = {
                    'page': result.get('page', page),
                    'has_next': result.get('has_next', False),
                    'total_pages': result.get('total_pages'),
                    'videos': videos
                }
                
                all_videos.extend(videos)
                app_logger.info(f"搜索完成，平台: {plat}, 页码: {page}, 找到 {len(videos)} 个视频")
                
            except RuntimeError as e:
                platform_errors[plat] = str(e)
                error_logger.error(f"搜索平台 {plat} 失败: {e}")
                if normalized_platform != "all":
                    return error_response(400, platform_errors[plat])
            except Exception as e:
                error_logger.error(f"搜索平台 {plat} 失败: {e}")
                platform_errors[plat] = f"{plat} 平台搜索失败"
                if normalized_platform != "all":
                    return error_response(500, platform_errors[plat])
                continue
        
        has_more = any(info.get('has_next', False) for info in platform_results.values())
        
        total_pages_list = [info.get('total_pages') for info in platform_results.values() if info.get('total_pages') is not None]
        total_pages = max(total_pages_list) if total_pages_list else 1
        
        response_data = {
            "platform": 'all' if normalized_platform == 'all' else normalized_platform,
            "page": page,
            "has_next": has_more,
            "total_pages": total_pages,
            "videos": all_videos,
            "platform_info": platform_results,
            "platform_errors": platform_errors,
        }
        
        return success_response(response_data)
    except Exception as e:
        import traceback
        error_logger.error(f"第三方搜索失败: {e}")
        error_logger.error(traceback.format_exc())
        return error_response(500, "服务器内部错误")


@video_bp.route('/third-party/<platform_name>/health-status', methods=['GET'])
@require_third_party(error_response)
def third_party_platform_health_status(platform_name: str):
    """检查指定视频平台查询状态。"""
    return _video_platform_health_status_response(platform_name)


@video_bp.route('/third-party/<platform_name>/tags', methods=['GET'])
@require_third_party(error_response)
def third_party_platform_tags(platform_name: str):
    """获取指定视频平台暴露的 taxonomy.tags 能力。"""
    return _video_taxonomy_tags_response(platform_name)


@video_bp.route('/third-party/<platform_name>/search-by-tags', methods=['GET'])
@require_third_party(error_response)
def third_party_platform_search_by_tags(platform_name: str):
    """通过指定视频平台的 taxonomy.tag_search 能力搜索视频。"""
    return _video_tag_search_response(platform_name)


@video_bp.route('/third-party/detail', methods=['GET'])
@require_third_party(error_response)
def third_party_detail():
    try:
        video_id = request.args.get('video_id')
        platform = request.args.get('platform', _get_default_video_platform_name())
        
        if not video_id:
            return error_response(400, "缺少参数")
        
        adapter = get_video_adapter(platform)
        detail = adapter.get_video_detail(video_id)
        
        if detail:
            return success_response(
                annotate_item(
                    detail,
                    platform_name=platform,
                    media_type="video",
                    capability="catalog.detail",
                )
            )
        else:
            return error_response(404, "视频不存在")
    except RuntimeError as e:
        error_logger.error(f"获取第三方详情失败(配置): {e}")
        return error_response(400, str(e))
    except Exception as e:
        error_logger.error(f"获取第三方详情失败: {e}")
        return error_response(500, "服务器内部错误")


@video_bp.route('/third-party/actor/search', methods=['GET'])
@require_third_party(error_response)
def third_party_actor_search():
    try:
        actor_name = request.args.get('actor_name')
        platform = request.args.get('platform', _get_default_video_platform_name())
        
        if not actor_name:
            return error_response(400, "缺少演员名称")
        
        adapter = get_video_adapter(platform)
        actors = adapter.search_actor(actor_name)
        
        return success_response(actors)
    except RuntimeError as e:
        error_logger.error(f"第三方演员搜索失败(配置): {e}")
        return error_response(400, str(e))
    except Exception as e:
        error_logger.error(f"第三方演员搜索失败: {e}")
        return error_response(500, "服务器内部错误")


@video_bp.route('/third-party/actor/works', methods=['GET'])
@require_third_party(error_response)
def third_party_actor_works():
    try:
        actor_id = request.args.get('actor_id')
        page = request.args.get('page', 1, type=int)
        platform = request.args.get('platform', _get_default_video_platform_name())
        
        if not actor_id:
            return error_response(400, "缺少演员ID")
        
        adapter = get_video_adapter(platform)
        result = adapter.get_actor_works(actor_id, page=page, max_pages=1)
        
        # 对返回的作品列表进行本地封面优先匹配：
        # 如果本地已导入该视频并存在封面，则优先使用本地封面路径（/static/cover/...），否则使用第三方图床 URL
        works = result.get("works", []) or []
        enhanced_works = []
        for work in works:
            try:
                code = work.get("code") or work.get("video_code") or ""
                if code:
                    local_video = video_service.get_video_by_code(code)
                    if local_video.success and local_video.data:
                        local_cover = local_video.data.get("cover_path") or ""
                        if local_cover:
                            # 覆盖为本地封面路径，实现“先本地缓存，否则图床”
                            work["cover_url"] = local_cover
                if work.get("cover_url") and not str(work.get("cover_url")).startswith("/static/"):
                    content_id = str(work.get("video_id") or work.get("id") or code or "").strip()
                    work["cover_url"] = to_proxy_image_url(
                        work.get("cover_url"),
                        asset_kind="cover",
                        video_id=content_id,
                        platform_name=platform,
                        content_id=content_id,
                    )
            except Exception as e:
                error_logger.error(f"为演员作品匹配本地封面失败: {e}")
            enhanced_works.append(
                annotate_item(
                    work,
                    platform_name=platform,
                    media_type="video",
                    capability="person.works",
                )
            )
        
        response_data = {
            "platform": platform,
            "page": result.get("page"),
            "has_next": result.get("has_next", False),
            "total_pages": result.get("total_pages"),
            "works": enhanced_works
        }
        
        return success_response(response_data)
    except RuntimeError as e:
        error_logger.error(f"获取演员作品失败(配置): {e}")
        return error_response(400, str(e))
    except Exception as e:
        error_logger.error(f"获取演员作品失败: {e}")
        return error_response(500, "服务器内部错误")


@video_bp.route('/third-party/import', methods=['POST'])
@require_third_party(error_response)
def third_party_import():
    try:
        data = request.json
        video_id = str(data.get('video_id') or '').strip()
        target = data.get('target', 'home')
        platform = str(data.get('platform') or '').strip().lower()
        
        if not video_id:
            return error_response(400, "缺少视频ID或code")
        
        if target not in ['home', 'recommendation']:
            return error_response(400, "无效的目标目录")
        platform, video_id, _manifest = _resolve_video_lookup_context(
            video_id=video_id,
            platform_name=platform,
        )
        
        from application.tag_app_service import TagAppService
        from domain.tag.entity import ContentType
        from core.constants import VIDEO_RECOMMENDATION_JSON_FILE
        
        tag_service = TagAppService()
        existing_tags = tag_service.get_tag_list(ContentType.VIDEO).data or []
        
        adapter = get_video_adapter(platform, existing_tags)
        detail = adapter.get_video_detail(video_id)

        if not detail and hasattr(adapter, 'get_video_by_code'):
            detail = adapter.get_video_by_code(video_id)
            if detail and detail.get("video_id"):
                video_id = str(detail.get("video_id")).strip() or video_id
        
        if not detail:
            return error_response(404, "视频不存在")

        video_id_full = _build_video_host_id(platform, video_id)
        video_code = (detail.get("code", "") or "").strip()
        
        if target == 'home':
            existing = video_service.get_video_by_code(video_code)
            if existing.success and existing.data:
                return error_response(400, f"视频 {video_id_full} 已存在")
            
            tag_name_to_id = {}
            
            for tag in existing_tags:
                tag_name_to_id[tag["name"]] = tag["id"]
            
            video_tag_ids = []
            for tag_name in detail.get("tags", []):
                if tag_name not in tag_name_to_id:
                    result = tag_service.create_tag(tag_name, ContentType.VIDEO)
                    if result.success:
                        tag_name_to_id[tag_name] = result.data["id"]
                        app_logger.info(f"创建新标签: {result.data['id']} - {tag_name}")
                if tag_name in tag_name_to_id:
                    video_tag_ids.append(tag_name_to_id[tag_name])

            cover_url = detail.get("cover_url", "")
            cover_path_fallback = (
                to_proxy_image_url(
                    cover_url,
                    asset_kind="cover",
                    video_id=video_id_full,
                    platform_name=platform,
                    content_id=video_id,
                )
                if cover_url
                else ""
            )

            video_data = {
                "id": video_id_full,
                "title": detail.get("title", ""),
                "code": video_code,
                "date": detail.get("date", ""),
                "series": detail.get("series", ""),
                "creator": detail.get("actors", [""])[0] if detail.get("actors") else "",
                "actors": detail.get("actors", []),
                "magnets": detail.get("magnets", []),
                "thumbnail_images": detail.get("thumbnail_images", []),
                "preview_video": _sanitize_preview_video_value(detail.get("preview_video", "")),
                "cover_path": cover_path_fallback,
                "thumbnail_images_local": [],
                "preview_video_local": "",
                "cover_path_local": "",
                "tag_ids": video_tag_ids,
                "list_ids": []
            }
            
            result = video_service.import_video(video_data)
            if result.success:
                recent_result = video_service.apply_recent_import_tags(
                    [video_data["id"]],
                    source="local",
                    clear_previous=True
                )
                if not recent_result.success:
                    app_logger.warning(f"更新视频最近导入标签失败: {recent_result.message}")

                _schedule_video_asset_cache(
                    video_id=video_data["id"],
                    source="local",
                    cover_url=cover_url,
                    preview_video=video_data.get("preview_video", ""),
                    thumbnail_images=video_data.get("thumbnail_images", []),
                    allow_cover=True,
                    allow_preview_video=_platform_allows_preview_video_download(
                        platform=platform,
                        video_id=video_data["id"],
                    ),
                )
                
                app_logger.info(f"导入视频成功: {video_data['id']}, 标签: {video_tag_ids}")
                return success_response(result.data, result.message)
            else:
                return error_response(400, result.message)
        else:
            from infrastructure.persistence.json_storage import JsonStorage
            from application.tag_app_service import TagAppService
            from domain.tag.entity import ContentType
            
            tag_service = TagAppService()
            existing_tags = tag_service.get_tag_list(ContentType.VIDEO).data or []
            
            tag_name_to_id = {}
            
            for tag in existing_tags:
                tag_name_to_id[tag["name"]] = tag["id"]
            
            video_tag_ids = []
            for tag_name in detail.get("tags", []):
                if tag_name not in tag_name_to_id:
                    result = tag_service.create_tag(tag_name, ContentType.VIDEO)
                    if result.success:
                        tag_name_to_id[tag_name] = result.data["id"]
                        app_logger.info(f"创建新标签: {result.data['id']} - {tag_name}")
                if tag_name in tag_name_to_id:
                    video_tag_ids.append(tag_name_to_id[tag_name])
            
            db_file = VIDEO_RECOMMENDATION_JSON_FILE
            storage = JsonStorage(db_file)
            db_data = storage.read()
            videos_key = 'video_recommendations'

            existing_codes = {
                (v.get('code', '') or '').strip().upper()
                for v in db_data.get(videos_key, [])
            }
            if video_code and video_code.upper() in existing_codes:
                return error_response(400, f"视频 {video_id_full} 已存在")
            
            cover_url = detail.get("cover_url", "")
            cover_path_fallback = (
                to_proxy_image_url(
                    cover_url,
                    asset_kind="cover",
                    video_id=video_id_full,
                    platform_name=platform,
                    content_id=video_id,
                )
                if cover_url
                else ""
            )

            video_data = {
                "id": video_id_full,
                "title": detail.get("title", ""),
                "code": video_code,
                "date": detail.get("date", ""),
                "series": detail.get("series", ""),
                "creator": detail.get("actors", [""])[0] if detail.get("actors") else "",
                "actors": detail.get("actors", []),
                "magnets": detail.get("magnets", []),
                "thumbnail_images": detail.get("thumbnail_images", []),
                "preview_video": _sanitize_preview_video_value(detail.get("preview_video", "")),
                "cover_path": cover_path_fallback,
                "thumbnail_images_local": [],
                "preview_video_local": "",
                "cover_path_local": "",
                "tag_ids": video_tag_ids,
                "list_ids": [],
                "create_time": get_current_time(),
                "last_access_time": get_current_time()
            }
            
            if videos_key not in db_data:
                db_data[videos_key] = []
            db_data[videos_key].append(video_data)
            
            if not storage.write(db_data):
                return error_response(500, "数据写入失败")
            
            _schedule_video_asset_cache(
                video_id=video_id_full,
                source="preview",
                cover_url=cover_url,
                preview_video=video_data.get("preview_video", ""),
                thumbnail_images=video_data.get("thumbnail_images", []),
                allow_cover=True,
                allow_preview_video=_platform_allows_preview_video_download(
                    platform=platform,
                    video_id=video_id_full,
                ),
            )

            recent_result = video_service.apply_recent_import_tags(
                [video_id_full],
                source="preview",
                clear_previous=True
            )
            if not recent_result.success:
                app_logger.warning(f"更新视频最近导入标签失败: {recent_result.message}")
            
            app_logger.info(f"视频导入成功: {video_id_full}, 目标: {target}")
            return success_response(video_data, "导入成功")
    except RuntimeError as e:
        error_logger.error(f"第三方导入失败(配置): {e}")
        return error_response(400, str(e))
    except Exception as e:
        error_logger.error(f"第三方导入失败: {e}")
        return error_response(500, "服务器内部错误")


# ========== 视频推荐页 API ==========

@video_bp.route('/recommendation/list', methods=['GET'])
def get_video_recommendation_list():
    """获取推荐视频列表"""
    try:
        from core.constants import VIDEO_RECOMMENDATION_JSON_FILE
        from infrastructure.persistence.json_storage import JsonStorage
        from application.tag_app_service import TagAppService
        from domain.tag.entity import ContentType
        
        sort_type = request.args.get('sort_type')
        min_score = request.args.get('min_score', type=float)
        
        storage = JsonStorage(VIDEO_RECOMMENDATION_JSON_FILE)
        db_data = storage.read()
        videos = db_data.get('video_recommendations', [])
        
        tag_service = TagAppService()
        tags = tag_service.get_tag_list(ContentType.VIDEO).data or []
        tag_map = {t["id"]: t["name"] for t in tags}
        
        filtered_videos = []
        for video in videos:
            if video.get('is_deleted'):
                continue
            if min_score is not None and (video.get('score') or 0) < min_score:
                continue

            filtered_videos.append(
                _decorate_video_recommendation_item(video, tag_map=tag_map)
            )
        
        if sort_type == 'score':
            filtered_videos.sort(key=lambda x: (x.get('score') or 0), reverse=True)
        elif sort_type == 'date':
            filtered_videos.sort(key=lambda x: (x.get('date') or ''), reverse=True)
        else:
            filtered_videos.sort(key=lambda x: (x.get('create_time') or ''), reverse=True)
        
        return success_response(filtered_videos)
    except Exception as e:
        error_logger.error(f"获取推荐视频列表失败: {e}")
        return error_response(500, "服务器内部错误")


@video_bp.route('/recommendation/detail', methods=['GET'])
def get_video_recommendation_detail():
    """获取推荐视频详情"""
    try:
        from core.constants import VIDEO_RECOMMENDATION_JSON_FILE
        from infrastructure.persistence.json_storage import JsonStorage
        from application.tag_app_service import TagAppService
        from domain.tag.entity import ContentType
        
        video_id = request.args.get('video_id')
        if not video_id:
            return error_response(400, "缺少参数: video_id")
        
        storage = JsonStorage(VIDEO_RECOMMENDATION_JSON_FILE)
        db_data = storage.read()
        videos = db_data.get('video_recommendations', [])
        
        tag_service = TagAppService()
        tags = tag_service.get_tag_list(ContentType.VIDEO).data or []
        tag_map = {t["id"]: t["name"] for t in tags}
        
        for video in videos:
            if video.get('id') == video_id:
                detail = _decorate_video_recommendation_item(
                    video,
                    tag_map=tag_map,
                    include_preview_detail=True,
                )
                return success_response(detail)
        
        return error_response(404, "视频不存在")
    except Exception as e:
        error_logger.error(f"获取推荐视频详情失败: {e}")
        return error_response(500, "服务器内部错误")


@video_bp.route('/recommendation/migrate-to-local', methods=['POST'])
def migrate_video_recommendations_to_local():
    """Create async task to migrate preview recommendation videos into local library."""
    try:
        data = request.json or {}
        video_ids = data.get('video_ids', [])
        if not isinstance(video_ids, list) or len(video_ids) == 0:
            return error_response(400, "missing parameter: video_ids")

        normalized_ids = [str(item or "").strip() for item in video_ids if str(item or "").strip()]
        if len(normalized_ids) == 0:
            return error_response(400, "missing parameter: video_ids")

        from infrastructure.task_manager import task_manager
        task_platform = ""
        for candidate_id in normalized_ids:
            resolved_platform, _lookup_id, _manifest = _resolve_video_lookup_context(video_id=candidate_id)
            if str(resolved_platform or "").strip():
                task_platform = str(resolved_platform).strip().upper()
                break
        if not task_platform:
            task_platform = str(_get_default_video_platform_name() or "").strip().upper()

        task_id = task_manager.create_task(
            platform=task_platform,
            import_type='migrate_to_local',
            target='home',
            comic_ids=normalized_ids,
            content_type='video',
            extra_data={
                "source": "preview",
                "entry": "video_recommendation_migrate_to_local"
            }
        )

        app_logger.info(
            f"创建预览视频迁移本地任务: task_id={task_id}, count={len(normalized_ids)}"
        )
        return success_response(
            {
                "task_id": task_id,
                "content_type": "video",
                "message": "导入任务已创建"
            },
            "导入任务已创建，请到我的-导入任务查看进度"
        )
    except Exception as e:
        error_logger.error(f"migrate recommendation videos to local failed: {e}")
        return error_response(500, "internal server error")


@video_bp.route('/recommendation/edit', methods=['PUT'])
def edit_video_recommendation():
    """编辑推荐视频元数据"""
    try:
        from core.constants import VIDEO_RECOMMENDATION_JSON_FILE
        from infrastructure.persistence.json_storage import JsonStorage
        
        data = request.json
        if not data or 'video_id' not in data:
            return error_response(400, "缺少参数: video_id")
        
        video_id = data['video_id']
        meta = {
            'title': data.get('title'),
            'code': data.get('code'),
            'date': data.get('date'),
            'series': data.get('series'),
            'actors': data.get('actors'),
            'desc': data.get('desc'),
            'cover_path': data.get('cover_path')
        }
        meta = {k: v for k, v in meta.items() if v is not None}
        
        storage = JsonStorage(VIDEO_RECOMMENDATION_JSON_FILE)
        db_data = storage.read()
        videos = db_data.get('video_recommendations', [])
        
        found = False
        for video in videos:
            if video.get('id') == video_id:
                video.update(meta)
                found = True
                break
        
        if not found:
            return error_response(404, "视频不存在")
        
        if not storage.write(db_data):
            return error_response(500, "数据写入失败")
        
        app_logger.info(f"编辑推荐视频成功: {video_id}")
        return success_response({"message": "编辑成功"})
    except Exception as e:
        error_logger.error(f"编辑推荐视频失败: {e}")
        return error_response(500, "服务器内部错误")


@video_bp.route('/recommendation/tag/bind', methods=['PUT'])
def bind_video_recommendation_tags():
    """绑定推荐视频标签"""
    try:
        from core.constants import VIDEO_RECOMMENDATION_JSON_FILE
        from infrastructure.persistence.json_storage import JsonStorage
        
        data = request.json
        if not data or 'video_id' not in data or 'tag_id_list' not in data:
            return error_response(400, "缺少参数: video_id 或 tag_id_list")
        
        video_id = data['video_id']
        tag_id_list = data['tag_id_list']
        
        storage = JsonStorage(VIDEO_RECOMMENDATION_JSON_FILE)
        db_data = storage.read()
        videos = db_data.get('video_recommendations', [])
        
        found = False
        for video in videos:
            if video.get('id') == video_id:
                video['tag_ids'] = tag_id_list
                found = True
                break
        
        if not found:
            return error_response(404, "视频不存在")
        
        if not storage.write(db_data):
            return error_response(500, "数据写入失败")
        
        app_logger.info(f"绑定推荐视频标签成功: {video_id}, 标签: {tag_id_list}")
        return success_response({"message": "标签绑定成功"})
    except Exception as e:
        error_logger.error(f"绑定推荐视频标签失败: {e}")
        return error_response(500, "服务器内部错误")


@video_bp.route('/recommendation/score', methods=['PUT'])
def update_video_recommendation_score():
    """更新推荐视频评分"""
    try:
        from core.constants import VIDEO_RECOMMENDATION_JSON_FILE
        from infrastructure.persistence.json_storage import JsonStorage
        
        data = request.json
        video_id = data.get('video_id')
        score = data.get('score')
        
        if not video_id or score is None:
            return error_response(400, "缺少参数")
        
        storage = JsonStorage(VIDEO_RECOMMENDATION_JSON_FILE)
        db_data = storage.read()
        videos = db_data.get('video_recommendations', [])
        
        found = False
        for video in videos:
            if video.get('id') == video_id:
                video['score'] = score
                found = True
                break
        
        if not found:
            return error_response(404, "视频不存在")
        
        if not storage.write(db_data):
            return error_response(500, "数据写入失败")
        
        return success_response({"message": "评分更新成功"})
    except Exception as e:
        error_logger.error(f"更新推荐视频评分失败: {e}")
        return error_response(500, "服务器内部错误")


@video_bp.route('/recommendation/trash/move', methods=['PUT'])
def move_video_recommendation_to_trash():
    """移动推荐视频到回收站"""
    try:
        from core.constants import VIDEO_RECOMMENDATION_JSON_FILE
        from infrastructure.persistence.json_storage import JsonStorage
        
        data = request.json
        video_id = data.get('video_id')
        
        if not video_id:
            return error_response(400, "缺少参数")
        
        storage = JsonStorage(VIDEO_RECOMMENDATION_JSON_FILE)
        db_data = storage.read()
        videos = db_data.get('video_recommendations', [])
        
        found = False
        for video in videos:
            if video.get('id') == video_id:
                video['is_deleted'] = True
                video['deleted_time'] = get_current_time()
                found = True
                break
        
        if not found:
            return error_response(404, "视频不存在")
        
        if not storage.write(db_data):
            return error_response(500, "数据写入失败")
        
        return success_response({"message": "已移入回收站"})
    except Exception as e:
        error_logger.error(f"移动推荐视频到回收站失败: {e}")
        return error_response(500, "服务器内部错误")


@video_bp.route('/recommendation/trash/batch-move', methods=['PUT'])
def batch_move_video_recommendation_to_trash():
    """批量移动推荐视频到回收站"""
    try:
        from core.constants import VIDEO_RECOMMENDATION_JSON_FILE
        from infrastructure.persistence.json_storage import JsonStorage
        
        data = request.json
        video_ids = data.get('video_ids', [])
        
        if not video_ids:
            return error_response(400, "缺少参数")
        
        storage = JsonStorage(VIDEO_RECOMMENDATION_JSON_FILE)
        db_data = storage.read()
        videos = db_data.get('video_recommendations', [])
        
        count = 0
        for video in videos:
            if video.get('id') in video_ids:
                video['is_deleted'] = True
                video['deleted_time'] = get_current_time()
                count += 1
        
        if not storage.write(db_data):
            return error_response(500, "数据写入失败")
        
        return success_response({"moved_count": count}, f"已将 {count} 个视频移入回收站")
    except Exception as e:
        error_logger.error(f"批量移动推荐视频到回收站失败: {e}")
        return error_response(500, "服务器内部错误")


@video_bp.route('/recommendation/trash/list', methods=['GET'])
def get_video_recommendation_trash_list():
    """获取推荐视频回收站列表"""
    try:
        from core.constants import VIDEO_RECOMMENDATION_JSON_FILE
        from infrastructure.persistence.json_storage import JsonStorage
        from application.tag_app_service import TagAppService
        from domain.tag.entity import ContentType
        
        storage = JsonStorage(VIDEO_RECOMMENDATION_JSON_FILE)
        db_data = storage.read()
        videos = db_data.get('video_recommendations', [])
        
        tag_service = TagAppService()
        tags = tag_service.get_tag_list(ContentType.VIDEO).data or []
        tag_map = {t["id"]: t["name"] for t in tags}
        
        trash_videos = []
        for video in videos:
            if video.get('is_deleted'):
                trash_videos.append(
                    _decorate_video_recommendation_item(video, tag_map=tag_map)
                )
        
        trash_videos.sort(key=lambda x: x.get('deleted_time', ''), reverse=True)
        return success_response(trash_videos)
    except Exception as e:
        error_logger.error(f"获取推荐视频回收站列表失败: {e}")
        return error_response(500, "服务器内部错误")


@video_bp.route('/recommendation/trash/restore', methods=['PUT'])
def restore_video_recommendation_from_trash():
    """从回收站恢复推荐视频"""
    try:
        from core.constants import VIDEO_RECOMMENDATION_JSON_FILE
        from infrastructure.persistence.json_storage import JsonStorage
        
        data = request.json
        video_id = data.get('video_id')
        
        if not video_id:
            return error_response(400, "缺少参数")
        
        storage = JsonStorage(VIDEO_RECOMMENDATION_JSON_FILE)
        db_data = storage.read()
        videos = db_data.get('video_recommendations', [])
        
        found = False
        for video in videos:
            if video.get('id') == video_id:
                video['is_deleted'] = False
                if 'deleted_time' in video:
                    del video['deleted_time']
                found = True
                break
        
        if not found:
            return error_response(404, "视频不存在")
        
        if not storage.write(db_data):
            return error_response(500, "数据写入失败")
        
        app_logger.info(f"推荐视频从回收站恢复: {video_id}")
        return success_response({"message": "已从回收站恢复"})
    except Exception as e:
        error_logger.error(f"从回收站恢复推荐视频失败: {e}")
        return error_response(500, "服务器内部错误")


@video_bp.route('/recommendation/trash/delete', methods=['DELETE'])
def delete_video_recommendation_permanently():
    """永久删除推荐视频"""
    try:
        from core.constants import VIDEO_RECOMMENDATION_JSON_FILE
        from infrastructure.persistence.json_storage import JsonStorage
        
        video_id = request.args.get('video_id')
        if not video_id:
            return error_response(400, "缺少参数")
        
        storage = JsonStorage(VIDEO_RECOMMENDATION_JSON_FILE)
        db_data = storage.read()
        videos = db_data.get('video_recommendations', [])
        
        original_count = len(videos)
        
        video_to_delete = None
        for v in videos:
            if v.get('id') == video_id:
                video_to_delete = v
                break
        
        videos = [v for v in videos if v.get('id') != video_id]
        
        if len(videos) == original_count:
            return error_response(404, "视频不存在")
        
        db_data['video_recommendations'] = videos
        
        if not storage.write(db_data):
            return error_response(500, "数据写入失败")
        
        video_service.delete_recommendation_assets(
            video_id,
            preview_video=(video_to_delete or {}).get("preview_video", ""),
            preview_video_local=(video_to_delete or {}).get("preview_video_local", ""),
            cover_path=(video_to_delete or {}).get("cover_path", ""),
            cover_path_local=(video_to_delete or {}).get("cover_path_local", ""),
            thumbnail_images=(video_to_delete or {}).get("thumbnail_images", []),
            thumbnail_images_local=(video_to_delete or {}).get("thumbnail_images_local", []),
        )
        
        app_logger.info(f"推荐视频永久删除: {video_id}")
        return success_response({"message": "已永久删除"})
    except Exception as e:
        error_logger.error(f"永久删除推荐视频失败: {e}")
        return error_response(500, "服务器内部错误")


@video_bp.route('/recommendation/trash/batch-restore', methods=['PUT'])
def batch_restore_video_recommendation_from_trash():
    """批量从回收站恢复推荐视频"""
    try:
        from core.constants import VIDEO_RECOMMENDATION_JSON_FILE
        from infrastructure.persistence.json_storage import JsonStorage
        
        data = request.json
        video_ids = data.get('video_ids', [])
        
        if not video_ids:
            return error_response(400, "缺少参数")
        
        storage = JsonStorage(VIDEO_RECOMMENDATION_JSON_FILE)
        db_data = storage.read()
        videos = db_data.get('video_recommendations', [])
        
        count = 0
        for video in videos:
            if video.get('id') in video_ids:
                video['is_deleted'] = False
                if 'deleted_time' in video:
                    del video['deleted_time']
                count += 1
        
        if not storage.write(db_data):
            return error_response(500, "数据写入失败")
        
        return success_response({"restored_count": count}, f"已恢复 {count} 个视频")
    except Exception as e:
        error_logger.error(f"批量恢复推荐视频失败: {e}")
        return error_response(500, "服务器内部错误")


@video_bp.route('/recommendation/trash/batch-delete', methods=['DELETE'])
def batch_delete_video_recommendation_permanently():
    """批量永久删除推荐视频"""
    try:
        from core.constants import VIDEO_RECOMMENDATION_JSON_FILE
        from infrastructure.persistence.json_storage import JsonStorage
        
        data = request.json
        video_ids = data.get('video_ids', [])
        
        if not video_ids:
            return error_response(400, "缺少参数")
        
        storage = JsonStorage(VIDEO_RECOMMENDATION_JSON_FILE)
        db_data = storage.read()
        videos = db_data.get('video_recommendations', [])
        
        original_count = len(videos)
        
        videos_to_delete = []
        remaining_videos = []
        for video in videos:
            if video.get('id') in video_ids:
                videos_to_delete.append(video)
            else:
                remaining_videos.append(video)
        
        if len(remaining_videos) == original_count:
            return error_response(404, "没有找到视频")
        
        db_data['video_recommendations'] = remaining_videos
        
        if not storage.write(db_data):
            return error_response(500, "数据写入失败")
        
        for video in videos_to_delete:
            video_service.delete_recommendation_assets(
                video.get('id', ''),
                preview_video=video.get('preview_video', ''),
                preview_video_local=video.get('preview_video_local', ''),
                cover_path=video.get('cover_path', ''),
                cover_path_local=video.get('cover_path_local', ''),
                thumbnail_images=video.get('thumbnail_images', []),
                thumbnail_images_local=video.get('thumbnail_images_local', []),
            )
        
        app_logger.info(f"推荐视频批量永久删除: {len(videos_to_delete)}个")
        return success_response({"deleted_count": len(videos_to_delete)}, f"已永久删除 {len(videos_to_delete)} 个视频")
    except Exception as e:
        error_logger.error(f"批量永久删除推荐视频失败: {e}")
        return error_response(500, "服务器内部错误")


@video_bp.route('/recommendation/search', methods=['GET'])
def search_video_recommendations():
    """搜索推荐视频"""
    try:
        from core.constants import VIDEO_RECOMMENDATION_JSON_FILE
        from infrastructure.persistence.json_storage import JsonStorage
        from application.tag_app_service import TagAppService
        from domain.tag.entity import ContentType
        
        keyword = request.args.get('keyword')
        if not keyword:
            return error_response(400, "缺少参数: keyword")
        
        keyword = keyword.lower()
        
        storage = JsonStorage(VIDEO_RECOMMENDATION_JSON_FILE)
        db_data = storage.read()
        videos = db_data.get('video_recommendations', [])
        
        tag_service = TagAppService()
        tags = tag_service.get_tag_list(ContentType.VIDEO).data or []
        tag_map = {t["id"]: t["name"] for t in tags}
        
        results = []
        for video in videos:
            if video.get('is_deleted'):
                continue
            title = video.get('title', '').lower()
            code = video.get('code', '').lower()
            actors = ' '.join(video.get('actors', [])).lower()
            if keyword in title or keyword in code or keyword in actors:
                results.append(
                    _decorate_video_recommendation_item(video, tag_map=tag_map)
                )
        
        return success_response(results)
    except Exception as e:
        error_logger.error(f"搜索推荐视频失败: {e}")
        return error_response(500, "服务器内部错误")


@video_bp.route('/recommendation/filter', methods=['GET'])
def filter_video_recommendations():
    """根据标签、作者、清单筛选推荐视频"""
    try:
        from infrastructure.persistence.repositories.video_recommendation_repository_impl import VideoRecommendationJsonRepository
        from infrastructure.persistence.repositories.tag_repository_impl import TagJsonRepository
        
        include_tag_ids = request.args.getlist('include_tag_ids')
        exclude_tag_ids = request.args.getlist('exclude_tag_ids')
        authors = request.args.getlist('authors')
        list_ids = request.args.getlist('list_ids')
        
        video_repo = VideoRecommendationJsonRepository()
        tag_repo = TagJsonRepository()
        tags = tag_repo.get_all()
        tag_map = {t.id: t.name for t in tags}
        
        if authors or list_ids:
            videos = video_repo.filter_multi(
                include_tags=include_tag_ids if include_tag_ids else None,
                exclude_tags=exclude_tag_ids if exclude_tag_ids else None,
                authors=authors if authors else None,
                list_ids=list_ids if list_ids else None
            )
        else:
            videos = video_repo.filter_by_tags(include_tag_ids, exclude_tag_ids)
        
        results = []
        for v in videos:
            video_info = v.to_dict()
            video_info["tags"] = [{"id": tid, "name": tag_map.get(tid, tid)} for tid in v.tag_ids]
            results.append(video_info)

        results = _decorate_video_recommendation_items(results, tag_map=tag_map)

        app_logger.info(f"视频推荐筛选成功: 包含 {include_tag_ids}, 排除 {exclude_tag_ids}, 作者 {authors}, 清单 {list_ids}, 结果数量: {len(results)}")
        return success_response(results)
    except Exception as e:
        error_logger.error(f"视频推荐筛选失败: {e}")
        return error_response(500, "服务器内部错误")


# ========== 视频播放相关 API ==========

@video_bp.route('/recommendation/<video_id>/play-urls', methods=['GET'])
@require_third_party(error_response)
def get_video_recommendation_play_urls(video_id):
    """获取推荐视频播放链接（从 MissAV 和 Jable 提取）"""
    try:
        from core.constants import VIDEO_RECOMMENDATION_JSON_FILE
        from infrastructure.persistence.json_storage import JsonStorage
        
        storage = JsonStorage(VIDEO_RECOMMENDATION_JSON_FILE)
        db_data = storage.read()
        videos = db_data.get('video_recommendations', [])
        
        video = None
        for v in videos:
            if v.get('id') == video_id:
                video = v
                break
        
        if not video:
            return error_response(404, "视频不存在")
        
        code = video.get('code', '')
        
        if not code:
            return error_response(400, "视频没有番号信息")
        
        sources = _build_play_sources(code)
        
        return success_response({
            'video_id': video_id,
            'code': code,
            'title': video.get('title', ''),
            'sources': sources
        })
        
    except Exception as e:
        error_logger.error(f"获取播放链接失败: {e}")
        return error_response(500, "服务器内部错误")

@video_bp.route('/<video_id>/play-urls', methods=['GET'])
@require_third_party(error_response)
def get_video_play_urls(video_id):
    """获取视频播放链接（从 MissAV 和 Jable 提取）"""
    try:
        result = video_service.get_video_detail(video_id)
        if not result.success or not result.data:
            return error_response(404, "视频不存在")
        
        video = result.data
        code = video.get('code', '')
        
        if not code:
            return error_response(400, "视频没有番号信息")
        
        sources = _build_play_sources(code)
        
        return success_response({
            'video_id': video_id,
            'code': code,
            'title': video.get('title', ''),
            'sources': sources
        })
        
    except Exception as e:
        error_logger.error(f"获取播放链接失败: {e}")
        return error_response(500, "服务器内部错误")


@video_bp.route('/proxy/<domain>/<path:path>', methods=['GET'])
@require_third_party(error_response)
def proxy_video_request(domain, path):
    """代理视频请求，解决跨域问题"""
    try:
        proxy_result = _get_missav_client().proxy_stream(
            domain=domain,
            path=path,
            query_string=request.query_string.decode(),
            incoming_referer=request.headers.get('Referer', '')
        )
        return Response(proxy_result.body, status=proxy_result.status_code, headers=proxy_result.headers)
        
    except Exception as e:
        error_logger.error(f"代理请求失败: {e}")
        return Response(f'Proxy error: {str(e)}', status=500)


@video_bp.route('/proxy2', methods=['GET', 'POST', 'HEAD'])
@require_third_party(error_response)
def proxy_video_request2():
    """代理视频请求（完整URL方式，支持重写m3u8）"""
    try:
        body_url = ''
        if request.method == 'POST':
            data = request.get_json(silent=True) or {}
            body_url = data.get('url', '')

        proxy_result = _get_missav_client().proxy_url(
            method=request.method,
            query_string=request.query_string.decode(),
            body_url=body_url,
            incoming_referer=request.headers.get('Referer', ''),
            incoming_headers={
                "Range": request.headers.get("Range", ""),
                "Accept": request.headers.get("Accept", ""),
                "Origin": request.headers.get("Origin", ""),
                "User-Agent": request.headers.get("User-Agent", "")
            }
        )

        response = make_response(proxy_result.content)
        response.status_code = proxy_result.status_code
        for n, v in proxy_result.headers:
            response.headers[n] = v
        return response
    except ValueError as e:
        return Response(str(e), status=400)
    except Exception as e:
        error_logger.error(f"代理请求2失败: {e}")
        return Response(f'Proxy error: {str(e)}', status=500)


# ========== 演员作品分页获取 API ==========

@video_bp.route('/actor/works/<actor_id>', methods=['GET'])
def get_actor_works(actor_id):
    try:
        offset = int(request.args.get('offset', 0))
        limit = int(request.args.get('limit', 5))
        
        result = actor_service.get_actor_works_paginated(actor_id, offset, limit)
        
        if result.success:
            return success_response(result.data)
        else:
            return error_response(400, result.message)
    except Exception as e:
        error_logger.error(f"获取演员作品失败: {e}")
        return error_response(500, "服务器内部错误")


@video_bp.route('/actor/search-works', methods=['GET'])
def search_actor_works():
    """根据演员名搜索作品（不需要订阅）"""
    try:
        actor_name = request.args.get('actor_name')
        offset = int(request.args.get('offset', 0))
        limit = int(request.args.get('limit', 5))
        
        if not actor_name:
            return error_response(400, "演员名称不能为空")
        
        result = actor_service.search_actor_works_by_name(actor_name, offset, limit)
        
        if result.success:
            return success_response(result.data)
        else:
            return error_response(500, result.message)
    except Exception as e:
        error_logger.error(f"搜索演员作品失败: {e}")
        return error_response(500, "服务器内部错误")


@video_bp.route('/actor/works-cache/clear', methods=['DELETE'])
def clear_actor_works_cache():
    """清理演员作品缓存"""
    try:
        actor_name = request.args.get('actor_name')
        
        result = actor_service.clear_actor_works_cache(actor_name)
        
        if result.success:
            return success_response(result.data)
        else:
            return error_response(400, result.message)
    except Exception as e:
        error_logger.error(f"清理演员作品缓存失败: {e}")
        return error_response(500, "服务器内部错误")
