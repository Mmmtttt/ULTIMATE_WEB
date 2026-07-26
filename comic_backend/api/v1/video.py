"""
视频 API 路由
"""

from flask import Blueprint, request, jsonify, Response, make_response, send_file
from application.video_app_service import VideoAppService
from application.actor_app_service import ActorAppService
from application.content_sorting import (
    normalize_custom_order_records,
    sort_content_items,
)
from application.list_query_support import (
    build_paginated_payload,
    extract_available_authors,
    matches_keyword,
    normalize_page,
    normalize_page_size,
    normalize_string_list,
)
from application.config_app_service import ConfigAppService
from application.persisted_content_metadata import build_persisted_annotation, normalize_data_relative_path
from application.storage_usage_service import annotate_video_storage_usage
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
from infrastructure.persistence.repositories import JsonDocumentRepository
from core.host_platform_fallback import infer_host_video_platform, merge_host_video_display
from core.constants import DATA_DIR, VIDEO_RECOMMENDATION_JSON_FILE
from core.utils import get_current_time
from core.runtime_profile import is_third_party_enabled, get_runtime_profile
from domain.tag.entity import ContentType
import os
import threading
import time
from urllib.parse import parse_qs, quote, urlencode, urlparse
import mimetypes
import re
from .runtime_guard import require_third_party
from protocol.gateway import get_protocol_gateway
from protocol.presentation import annotate_item, annotate_items
from application.tag_content_type_guard import validate_tag_ids_for_content_type
from infrastructure.persistence.repositories.tag_repository_impl import TagJsonRepository

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


def _parse_bool_arg(name: str, default: bool = False) -> bool:
    raw = str(request.args.get(name, "") or "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


def _build_local_video_detail_payload(video_id: str):
    result = video_service.get_video_detail(video_id)
    if not result.success:
        return result

    detail = _decorate_local_video_payload_dict(result.data or {})
    return ServiceResult.ok(detail, result.message or "成功")


def _decorate_local_video_payload_dict(video_data: dict) -> dict:
    detail = dict(video_data or {})
    detail = _ensure_preview_video_detail(detail, source="local")
    detail = _attach_video_playback_projection(detail, source="local")
    _schedule_local_cover_thumbnail_cache(detail, source="local")
    _schedule_preview_video_local_cache(detail, source="local")
    return detail


def _get_video_proxy_client():
    """Load a protocol-declared playback proxy client lazily."""
    if not is_third_party_enabled():
        raise RuntimeError(
            f"third-party integration is disabled in current runtime profile: {get_runtime_profile()}"
        )
    return runtime_get_playback_proxy_client(proxy_base_path='/api/v1/video')


def _build_play_sources(code: str):
    client = _get_video_proxy_client()
    return client.build_sources(code)


def _get_video_recommendation_document_repository() -> JsonDocumentRepository:
    return JsonDocumentRepository(
        VIDEO_RECOMMENDATION_JSON_FILE,
        "video_recommendations",
        "total_video_recommendations",
    )


def _commit_custom_order(document_repo: JsonDocumentRepository, ordered_ids=None) -> bool:
    changed = False
    processed = False

    def update_items(items):
        nonlocal changed, processed
        normalized_items, did_change = normalize_custom_order_records(items, ordered_ids)
        changed = did_change
        processed = True
        return normalized_items if did_change else None

    updated = document_repo.update_items(update_items)
    if updated:
        return True
    return processed and not changed


def _build_teledrive_file_url(file_id: str, name: str) -> str:
    normalized_id = str(file_id or "").strip()
    if not normalized_id:
        return ""
    query = urlencode({"name": str(name or "")})
    return f"/api/v1/teledrive/files/{quote(normalized_id, safe='')}/content?{query}"


def _build_direct_video_source(
    source_key: str,
    name: str,
    url: str,
    *,
    origin: str,
    episode_index: int = 0,
) -> dict:
    source_name = str(name or "").strip() or origin or "视频"
    return {
        "key": str(source_key or source_name).strip(),
        "name": source_name,
        "available": True,
        "type": "direct",
        "source": str(source_key or source_name).strip(),
        "episode_index": int(episode_index or 0),
        "currentResolution": "原始",
        "streams": [
            {
                "resolution": "原始",
                "url": str(url or "").strip(),
                "type": "direct",
                "source": str(origin or "").strip(),
            }
        ],
    }


def _build_local_stream_url(video_id: str, episode_index: int = 0) -> str:
    normalized_id = str(video_id or "").strip()
    if not normalized_id:
        return ""
    suffix = f"?episode={int(episode_index)}" if int(episode_index or 0) > 0 else ""
    return f"/api/v1/video/local-stream/{quote(normalized_id, safe='')}{suffix}"


def _build_local_play_url(video_id: str, raw_url: str, episode_index: int = 0) -> str:
    url = str(raw_url or "").strip()
    lowered = url.lower()
    if lowered.startswith(("http://", "https://", "/api/v1/video/local-stream/", "/v1/video/local-stream/")):
        return url
    return _build_local_stream_url(video_id, episode_index)


def _build_teledrive_video_sources(video: dict) -> list:
    display = video.get("display") if isinstance(video.get("display"), dict) else {}
    teledrive = display.get("teledrive") if isinstance(display.get("teledrive"), dict) else {}
    if str(teledrive.get("type") or "") != "video":
        return []

    sources = []
    for index, episode in enumerate(teledrive.get("episodes") or [], start=1):
        if not isinstance(episode, dict):
            continue
        file_id = str(episode.get("file_id") or "").strip()
        name = str(episode.get("name") or "").strip()
        url = _build_teledrive_file_url(file_id, name)
        if not url:
            continue
        sources.append(_build_direct_video_source(
            f"teledrive_episode_{index}",
            episode.get("relative_path") or name or f"第 {index} 集",
            url,
            origin="remote_storage",
            episode_index=index,
        ))
    return sources


def _build_local_video_sources(video: dict) -> list:
    video_id = str(video.get("id") or "").strip()
    display = video.get("display") if isinstance(video.get("display"), dict) else {}
    episodes = display.get("local_episodes") if isinstance(display.get("local_episodes"), list) else []
    sources = []
    for index, episode in enumerate(episodes, start=1):
        if not isinstance(episode, dict):
            continue
        url = _build_local_play_url(video_id, episode.get("url"), index)
        if not url:
            continue
        sources.append(_build_direct_video_source(
            f"local_episode_{index}",
            episode.get("relative_path") or episode.get("name") or f"第 {index} 集",
            url,
            origin="local",
            episode_index=index,
        ))
    if sources:
        return sources

    local_video_path = str(video.get("local_video_path") or "").strip()
    local_source_path = str(video.get("local_source_path") or "").strip()
    if local_video_path or local_source_path:
        return [_build_direct_video_source(
            "local_episode_1",
            video.get("title") or video.get("code") or "本地视频",
            _build_local_play_url(video_id, local_video_path, 0),
            origin="local",
            episode_index=1,
        )]
    return []


def _normalize_playback_source_arg(raw_value: str) -> str:
    normalized = str(raw_value or "").strip().lower()
    return normalized if normalized in {"local", "remote"} else ""


def _normalize_remote_provider_arg(raw_value: str) -> str:
    normalized = str(raw_value or "").strip().lower()
    return "" if normalized in {"", "auto"} else normalized


def _normalize_provider_key(raw_value: str, fallback: str) -> str:
    normalized = re.sub(r"[^a-z0-9._-]+", "_", str(raw_value or "").strip().lower()).strip("._-")
    return normalized or fallback


def _pick_provider_label(raw_item: dict, fallback: str) -> str:
    for key in ("provider_label", "plugin_name", "name", "label", "platform", "source"):
        value = str((raw_item or {}).get(key) or "").strip()
        if value:
            return value
    return str(fallback or "").strip() or "远程平台"


def _build_provider_group(
    *,
    key: str,
    label: str,
    kind: str,
    selection_mode: str,
    sources: list,
    error: str = "",
) -> dict:
    normalized_sources = []
    available_sources = []
    for fallback_index, source in enumerate(sources or [], start=1):
        if not isinstance(source, dict):
            continue
        source_key = str(source.get("key") or source.get("source") or source.get("name") or f"{key}_source_{fallback_index}").strip()
        normalized_source = dict(source)
        normalized_source["key"] = source_key
        normalized_source["source"] = str(normalized_source.get("source") or source_key).strip()
        normalized_source["name"] = str(normalized_source.get("name") or label or f"播放项 {fallback_index}").strip()
        streams = normalized_source.get("streams")
        if not isinstance(streams, list):
            streams = []
        normalized_source["streams"] = [item for item in streams if isinstance(item, dict)]
        normalized_source["available"] = bool(
            normalized_source.get("available", True)
            and (
                normalized_source["streams"]
                or str(normalized_source.get("url") or "").strip()
            )
        )
        normalized_sources.append(normalized_source)
        if normalized_source["available"]:
            available_sources.append(normalized_source)
    default_source_key = str((available_sources[0] if available_sources else {}).get("key") or "").strip()
    return {
        "key": str(key or "").strip(),
        "label": str(label or "").strip() or "播放平台",
        "kind": str(kind or "").strip() or "remote",
        "selection_mode": "episodes" if selection_mode == "episodes" else "streams",
        "available": bool(available_sources),
        "supports_episode_selection": selection_mode == "episodes" and len(available_sources) > 1,
        "default_source_key": default_source_key,
        "sources": normalized_sources,
        "error": str(error or "").strip(),
    }


def _resolve_storage_provider_meta(video: dict) -> dict:
    display = video.get("display") if isinstance(video.get("display"), dict) else {}
    teledrive = display.get("teledrive") if isinstance(display.get("teledrive"), dict) else {}
    teledrive_origin = display.get("teledrive_origin") if isinstance(display.get("teledrive_origin"), dict) else {}
    candidates = [teledrive, teledrive_origin, video]

    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        raw_key = (
            candidate.get("provider_key")
            or candidate.get("plugin_id")
            or candidate.get("source")
            or ""
        )
        raw_label = _pick_provider_label(candidate, "")
        if str(raw_key or "").strip() or raw_label:
            key = _normalize_provider_key(str(raw_key or "").strip(), "remote_storage")
            label = raw_label or key
            return {"key": key, "label": label, "kind": "storage_remote"}

    return {"key": "remote_storage", "label": "远端文件", "kind": "storage_remote"}


def _normalize_online_source_entry(entry: dict, fallback_index: int) -> dict | None:
    if not isinstance(entry, dict):
        return None

    provider_key = _normalize_provider_key(
        str(entry.get("source") or entry.get("platform") or entry.get("name") or "").strip(),
        f"remote_provider_{fallback_index}",
    )
    provider_label = _pick_provider_label(entry, f"远程平台 {fallback_index}")

    streams = entry.get("streams")
    if not isinstance(streams, list):
        streams = []
    normalized_streams = [item for item in streams if isinstance(item, dict)]

    fallback_url = str(entry.get("proxy_url") or entry.get("url") or "").strip()
    if not normalized_streams and fallback_url:
        normalized_streams = [{
            "resolution": str(entry.get("currentResolution") or "原始").strip() or "原始",
            "url": fallback_url,
            "type": str(entry.get("type") or "direct").strip() or "direct",
            "source": provider_key,
        }]

    available = bool(entry.get("available", True) and normalized_streams)
    return {
        "key": provider_key,
        "name": provider_label,
        "available": available,
        "type": str(entry.get("type") or "direct").strip() or "direct",
        "source": provider_key,
        "currentResolution": str(entry.get("currentResolution") or "").strip(),
        "streams": normalized_streams,
        "page_url": str(entry.get("page_url") or "").strip(),
        "error": str(entry.get("error") or "").strip(),
        "raw": dict(entry),
    }


def _build_online_provider_groups(code: str) -> list[dict]:
    provider_groups = []
    for fallback_index, entry in enumerate(_build_play_sources(code), start=1):
        normalized_source = _normalize_online_source_entry(entry, fallback_index)
        if not normalized_source:
            continue
        provider_groups.append(
            _build_provider_group(
                key=str(normalized_source.get("source") or ""),
                label=str(normalized_source.get("name") or ""),
                kind="online",
                selection_mode="streams",
                sources=[normalized_source],
                error=str(normalized_source.get("error") or ""),
            )
        )
    return provider_groups


def _build_play_urls_payload(
    *,
    video_id: str,
    code: str,
    title: str,
    playback_source: str,
    provider_groups: list,
    requested_provider_key: str = "",
) -> dict:
    normalized_groups = [item for item in provider_groups if isinstance(item, dict)]
    available_groups = [item for item in normalized_groups if item.get("available")]
    selected_group = None
    requested_key = _normalize_provider_key(requested_provider_key, "") if requested_provider_key else ""
    if requested_key:
        selected_group = next(
            (item for item in normalized_groups if str(item.get("key") or "").strip().lower() == requested_key),
            None,
        )
    if selected_group is None and available_groups:
        selected_group = available_groups[0]
    selected_sources = [item for item in list((selected_group or {}).get("sources") or []) if item.get("available")]
    selected_provider_key = str((selected_group or {}).get("key") or "").strip()
    selected_provider_label = str((selected_group or {}).get("label") or "").strip()
    return {
        "video_id": video_id,
        "code": code,
        "title": title,
        "playback_source": playback_source,
        "provider": selected_provider_key,
        "provider_key": selected_provider_key,
        "provider_label": selected_provider_label,
        "default_provider_key": selected_provider_key,
        "provider_groups": normalized_groups,
        "sources": selected_sources,
    }


def _resolve_remote_video_sources(video_id: str, video: dict, *, remote_provider: str = "") -> ServiceResult:
    code = str(video.get("code") or "").strip()
    title = str(video.get("title") or "").strip()
    requested_provider = _normalize_remote_provider_arg(remote_provider)
    teledrive_sources = _build_teledrive_video_sources(video)
    provider_groups = []

    if teledrive_sources:
        storage_meta = _resolve_storage_provider_meta(video)
        provider_groups.append(
            _build_provider_group(
                key=str(storage_meta.get("key") or ""),
                label=str(storage_meta.get("label") or ""),
                kind=str(storage_meta.get("kind") or "storage_remote"),
                selection_mode="episodes",
                sources=teledrive_sources,
            )
        )

    if code:
        try:
            provider_groups.extend(_build_online_provider_groups(code))
        except Exception as e:
            error_logger.error(f"build remote online sources failed: video_id={video_id}, code={code}, error={e}")
            if not provider_groups:
                return ServiceResult.error("在线播放源加载失败")

    if not provider_groups:
        return ServiceResult.error("远程播放源不可用")

    if requested_provider:
        app_logger.info(
            f"remote provider requested: video_id={video_id}, code={code}, provider={requested_provider}"
        )

    return ServiceResult.ok(
        _build_play_urls_payload(
            video_id=video_id,
            code=code,
            title=title,
            playback_source="remote",
            provider_groups=provider_groups,
            requested_provider_key=requested_provider,
        )
    )


@video_bp.route('/list', methods=['GET'])
def video_list():
    try:
        sort_type = request.args.get('sort_type')
        sort_order = request.args.get('sort_order', 'desc')
        min_score = request.args.get('min_score', type=float)
        max_score = request.args.get('max_score', type=float)
        keyword = request.args.get('keyword', '')
        include_tag_ids = request.args.getlist('include_tag_ids')
        exclude_tag_ids = request.args.getlist('exclude_tag_ids')
        authors = request.args.getlist('authors')
        list_ids = request.args.getlist('list_ids')
        paginate = _parse_bool_arg('paginate')
        summary_only = _parse_bool_arg('summary')
        include_available_authors = _parse_bool_arg('include_available_authors')
        include_storage_usage = _parse_bool_arg('include_storage_usage')
        page = request.args.get('page', default=1, type=int)
        page_size = request.args.get('page_size', default=24, type=int)

        result = video_service.get_video_list(
            sort_type,
            sort_order,
            min_score,
            max_score,
            keyword=keyword,
            include_tags=include_tag_ids,
            exclude_tags=exclude_tag_ids,
            authors=authors,
            list_ids=list_ids,
            page=page,
            page_size=page_size,
            paginate=paginate,
            summary_only=summary_only,
            include_available_authors=include_available_authors,
            include_storage_usage=include_storage_usage,
        )
        if result.success:
            return success_response(result.data)
        else:
            return error_response(500, result.message)
    except Exception as e:
        error_logger.error(f"获取视频列表失败: {e}")
        return error_response(500, "服务器内部错误")


@video_bp.route('/custom-order', methods=['PUT'])
def update_video_custom_order():
    try:
        data = request.json or {}
        video_ids = data.get('video_ids', [])
        result = video_service.update_custom_order(video_ids, source="local")
        if result.success:
            return success_response(result.data, result.message or "自定义排序已保存")
        return error_response(400, result.message)
    except Exception as e:
        error_logger.error(f"保存视频自定义排序失败: {e}")
        return error_response(500, "服务器内部错误")


@video_bp.route('/detail', methods=['GET'])
def video_detail():
    try:
        video_id = request.args.get('video_id')
        if not video_id:
            return error_response(400, "缺少参数")
        
        result = _build_local_video_detail_payload(video_id)
        if result.success:
            return success_response(result.data)
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
            payload = _decorate_local_video_payload_dict(result.data or {}) if isinstance(result.data, dict) else result.data
            return success_response(payload, result.message or "LOCAL 视频详情已更新")
        return error_response(400, result.message or "LOCAL 视频详情更新失败")
    except Exception as e:
        error_logger.error(f"refresh local video metadata api failed: {e}")
        return error_response(500, "internal server error")


@video_bp.route('/local-metadata/refresh/batch', methods=['POST'])
@require_third_party(error_response)
def refresh_local_video_metadata_batch():
    try:
        data = request.json or {}
        video_ids = [
            str(item or "").strip()
            for item in (data.get('video_ids') or [])
            if str(item or "").strip()
        ]
        if not video_ids:
            return error_response(400, "missing parameter: video_ids")

        from infrastructure.task_manager import task_manager

        task_id = task_manager.create_batch_task(
            task_type=task_manager.TASK_TYPE_VIDEO_LOCAL_METADATA_REFRESH,
            content_type="video",
            item_ids=video_ids,
            title=f"批量补全本地视频信息（{len(video_ids)} 项）",
        )
        return success_response({
            "task_id": task_id,
            "count": len(video_ids),
            "task_type": task_manager.TASK_TYPE_VIDEO_LOCAL_METADATA_REFRESH,
        }, "批量补全任务已创建")
    except ValueError as e:
        return error_response(400, str(e))
    except Exception as e:
        error_logger.error(f"create batch local video metadata task failed: {e}")
        return error_response(500, "internal server error")


@video_bp.route('/local-thumbnails/generate', methods=['POST'])
def generate_local_video_thumbnails():
    try:
        data = request.json or {}
        video_id = str(data.get('video_id') or '').strip()
        if not video_id:
            return error_response(400, "缺少参数: video_id")

        result = video_service.generate_local_video_thumbnails(video_id)
        if result.success:
            payload = _decorate_local_video_payload_dict(result.data or {}) if isinstance(result.data, dict) else result.data
            return success_response(payload, result.message or "缩略图生成成功")
        return error_response(400, result.message or "生成缩略图失败")
    except Exception as e:
        error_logger.error(f"generate local video thumbnails api failed: {e}")
        return error_response(500, "internal server error")


@video_bp.route('/local-thumbnails/generate/batch', methods=['POST'])
def generate_local_video_thumbnails_batch():
    try:
        data = request.json or {}
        video_ids = [
            str(item or "").strip()
            for item in (data.get('video_ids') or [])
            if str(item or "").strip()
        ]
        if not video_ids:
            return error_response(400, "missing parameter: video_ids")

        from infrastructure.task_manager import task_manager

        task_id = task_manager.create_batch_task(
            task_type=task_manager.TASK_TYPE_VIDEO_LOCAL_THUMBNAIL_GENERATE,
            content_type="video",
            item_ids=video_ids,
            title=f"批量生成视频缩略图（{len(video_ids)} 项）",
        )
        return success_response({
            "task_id": task_id,
            "count": len(video_ids),
            "task_type": task_manager.TASK_TYPE_VIDEO_LOCAL_THUMBNAIL_GENERATE,
        }, "批量缩略图任务已创建")
    except ValueError as e:
        return error_response(400, str(e))
    except Exception as e:
        error_logger.error(f"create batch local video thumbnail task failed: {e}")
        return error_response(500, "internal server error")


@video_bp.route('/local-thumbnails/cover', methods=['PUT'])
def select_local_thumbnail_cover():
    try:
        data = request.json or {}
        video_id = str(data.get('video_id') or '').strip()
        if not video_id:
            return error_response(400, "缺少参数: video_id")

        try:
            thumbnail_index = int(data.get('thumbnail_index'))
        except Exception:
            return error_response(400, "缺少参数: thumbnail_index")

        result = video_service.select_local_thumbnail_as_cover(video_id, thumbnail_index)
        if result.success:
            payload = _decorate_local_video_payload_dict(result.data or {}) if isinstance(result.data, dict) else result.data
            return success_response(payload, result.message or "封面已更新")
        return error_response(400, result.message or "设置封面失败")
    except Exception as e:
        error_logger.error(f"select local thumbnail cover api failed: {e}")
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
        grouping_mode = str(data.get('grouping_mode') or '').strip()
        if not source_path:
            return error_response(400, "missing parameter: source_path")

        result = video_service.import_local_videos_from_path(
            source_path,
            import_mode=import_mode,
            grouping_mode=grouping_mode,
        )
        if result.success:
            return success_response(result.data, result.message)
        return error_response(400, result.message)
    except Exception as e:
        error_logger.error(f"local video import from path failed: {e}")
        return error_response(500, "internal server error")


@video_bp.route('/local-stream/<video_id>', methods=['GET'])
def stream_local_video(video_id):
    try:
        episode_index = request.args.get("episode", default=0, type=int) or 0
        resolved = video_service.resolve_local_video_file_path(video_id, episode_index=episode_index)
        if not resolved or not os.path.isfile(resolved):
            return make_response("Not Found", 404)

        file_size = os.path.getsize(resolved)
        guessed_type, _ = mimetypes.guess_type(resolved)
        content_type = guessed_type or "video/mp4"

        # Handle Range requests — Android WebView requires proper 206 responses
        range_header = request.headers.get("Range")
        if range_header:
            range_match = re.match(r"bytes=(\d+)-(\d*)", range_header)
            if range_match:
                start = int(range_match.group(1))
                end_str = range_match.group(2)
                end = int(end_str) if end_str else file_size - 1
                end = min(end, file_size - 1)

                if start >= file_size:
                    resp = make_response("", 416)
                    resp.headers["Content-Range"] = f"bytes */{file_size}"
                    return resp

                chunk_size = end - start + 1
                with open(resolved, "rb") as f:
                    f.seek(start)
                    data = f.read(chunk_size)

                resp = make_response(data, 206)
                resp.headers["Content-Type"] = content_type
                resp.headers["Content-Length"] = str(chunk_size)
                resp.headers["Content-Range"] = f"bytes {start}-{end}/{file_size}"
                resp.headers["Accept-Ranges"] = "bytes"
                return resp

        # Full file response
        resp = make_response()
        resp.headers["Content-Type"] = content_type
        resp.headers["Content-Length"] = str(file_size)
        resp.headers["Accept-Ranges"] = "bytes"

        # Stream the file directly instead of using Flask's send_file
        # (send_file relies on wsgi.file_wrapper which may not work on Chaquopy/Android)
        def generate():
            with open(resolved, "rb") as f:
                while True:
                    chunk = f.read(8192)
                    if not chunk:
                        break
                    yield chunk

        resp.response = generate()
        return resp
    except Exception as e:
        error_logger.error(f"stream local video failed: id={video_id}, error={e}", exc_info=True)
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


def _normalize_preview_media_path(raw_path: str) -> str:
    candidate = str(raw_path or "").strip()
    if not candidate:
        return ""

    relative = normalize_data_relative_path(candidate)
    if not relative:
        normalized_candidate = candidate.replace("\\", "/").lstrip("/").strip()
        if not normalized_candidate or "://" in normalized_candidate or candidate.startswith("//"):
            return ""

        joined_abs = os.path.abspath(os.path.join(DATA_DIR, normalized_candidate.replace("/", os.sep)))
        data_root = os.path.abspath(DATA_DIR)
        try:
            if os.path.commonpath([data_root, joined_abs]) != data_root or not os.path.exists(joined_abs):
                return ""
        except Exception:
            return ""
        relative = normalized_candidate

    return f"/media/{str(relative or '').lstrip('/')}"


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

    media_url = _normalize_preview_media_path(url)
    if media_url:
        lowered_media = media_url.lower()
        return media_url if any(marker in lowered_media for marker in _PREVIEW_VIDEO_MEDIA_MARKERS) else ""

    return url if any(marker in lowered for marker in _PREVIEW_VIDEO_MEDIA_MARKERS) else ""


def _normalize_playback_episode_name(episode: dict, fallback_index: int) -> str:
    if not isinstance(episode, dict):
        return f"第 {fallback_index} 集"
    name = str(
        episode.get("name")
        or episode.get("relative_path")
        or episode.get("title")
        or f"第 {fallback_index} 集"
    ).strip()
    return name or f"第 {fallback_index} 集"


def _normalize_playback_episode_index(episode: dict, fallback_index: int) -> int:
    if not isinstance(episode, dict):
        return fallback_index
    try:
        normalized = int(episode.get("index") or fallback_index)
    except Exception:
        normalized = fallback_index
    return normalized if normalized > 0 else fallback_index


def _build_primary_local_episodes(video_data: dict) -> list[dict]:
    display = video_data.get("display") if isinstance(video_data.get("display"), dict) else {}
    local_episodes = display.get("local_episodes") if isinstance(display.get("local_episodes"), list) else []
    if local_episodes:
        return [
            {
                "index": _normalize_playback_episode_index(episode, fallback_index),
                "name": _normalize_playback_episode_name(episode, fallback_index),
                "url": str((episode or {}).get("url") or "").strip(),
                "kind": "local_episode",
            }
            for fallback_index, episode in enumerate(local_episodes, start=1)
            if isinstance(episode, dict)
        ]

    local_video_path = str(video_data.get("local_video_path") or "").strip()
    if not local_video_path:
        return []

    return [{
        "index": 1,
        "name": str(video_data.get("title") or video_data.get("code") or "第 1 集").strip() or "第 1 集",
        "url": local_video_path,
        "kind": "local_episode",
    }]


def _build_primary_teledrive_episodes(video_data: dict) -> list[dict]:
    display = video_data.get("display") if isinstance(video_data.get("display"), dict) else {}
    teledrive = display.get("teledrive") if isinstance(display.get("teledrive"), dict) else {}
    episodes = teledrive.get("episodes") if isinstance(teledrive.get("episodes"), list) else []
    normalized = []
    for fallback_index, episode in enumerate(episodes, start=1):
        if not isinstance(episode, dict):
            continue
        file_id = str(episode.get("file_id") or "").strip()
        name = str(episode.get("name") or "").strip()
        normalized.append({
            "index": _normalize_playback_episode_index(episode, fallback_index),
            "name": _normalize_playback_episode_name(episode, fallback_index),
            "url": _build_teledrive_file_url(file_id, name),
            "kind": "teledrive_episode",
        })
    return [item for item in normalized if str(item.get("url") or "").strip()]


def _build_remote_playback_group(video_data: dict) -> dict:
    teledrive_episodes = _build_primary_teledrive_episodes(video_data)
    code = str(video_data.get("code") or "").strip()
    if teledrive_episodes:
        return {
            "key": "remote",
            "label": "远程",
            "mode": "storage_remote",
            "available": True,
            "supports_play_session": True,
            "supports_episode_selection": len(teledrive_episodes) > 1,
            "default_episode_index": int(teledrive_episodes[0].get("index") or 1),
            "episodes": teledrive_episodes,
        }

    if code:
        return {
            "key": "remote",
            "label": "远程",
            "mode": "online",
            "available": True,
            "supports_play_session": True,
            "supports_episode_selection": False,
            "default_episode_index": 1,
            "episodes": [],
        }

    return {}


def _build_primary_source_groups(video_data: dict) -> list[dict]:
    groups = []
    local_episodes = _build_primary_local_episodes(video_data)
    if local_episodes:
        groups.append(
            {
                "key": "local",
                "label": "本地",
                "mode": "local",
                "available": True,
                "supports_play_session": True,
                "supports_episode_selection": len(local_episodes) > 1,
                "default_episode_index": int(local_episodes[0].get("index") or 1),
                "episodes": local_episodes,
            }
        )

    remote_group = _build_remote_playback_group(video_data)
    if remote_group:
        groups.append(remote_group)
    return groups


def _build_primary_playback_summary(video_data: dict, *, source: str = "local") -> dict:
    source_groups = _build_primary_source_groups(video_data)
    default_group = source_groups[0] if source_groups else {}
    online_available = bool(str(video_data.get("code") or "").strip())

    if source_groups:
        return {
            "available": True,
            "mode": str(default_group.get("mode") or "none"),
            "supports_play_session": bool(default_group.get("supports_play_session", False)),
            "supports_episode_selection": bool(default_group.get("supports_episode_selection", False)),
            "default_episode_index": int(default_group.get("default_episode_index") or 1),
            "episodes": list(default_group.get("episodes") or []),
            "default_source_key": str(default_group.get("key") or ""),
            "source_groups": source_groups,
            "sources": [
                {
                    "key": str(group.get("key") or ""),
                    "label": str(group.get("label") or ""),
                    "kind": str(group.get("mode") or ""),
                }
                for group in source_groups
            ],
        }

    return {
        "available": online_available,
        "mode": "online" if online_available else "none",
        "supports_play_session": online_available,
        "supports_episode_selection": False,
        "default_episode_index": 1,
        "episodes": [],
        "default_source_key": "remote" if online_available else "",
        "source_groups": ([{
            "key": "remote",
            "label": "远程",
            "mode": "online",
            "available": True,
            "supports_play_session": True,
            "supports_episode_selection": False,
            "default_episode_index": 1,
            "episodes": [],
        }] if online_available else []),
        "sources": ([{
            "key": "remote",
            "label": "远程",
            "kind": "online",
        }] if online_available else []),
    }


def _build_preview_playback_assets(video_data: dict) -> list[dict]:
    _ensure_local_asset_fields(video_data)

    local_preview = _sanitize_preview_video_value(video_data.get("preview_video_local", ""))
    remote_preview = _sanitize_preview_video_value(video_data.get("preview_video", ""))
    source_origin = str(video_data.get("source_origin") or "").strip().lower()
    primary_episode_urls = {
        str(item.get("url") or "").strip()
        for item in (_build_primary_local_episodes(video_data) + _build_primary_teledrive_episodes(video_data))
        if str(item.get("url") or "").strip()
    }
    if str(video_data.get("local_video_path") or "").strip():
        primary_episode_urls.add(str(video_data.get("local_video_path") or "").strip())
    if source_origin == "teledrive_migrate" and remote_preview:
        primary_episode_urls.add(remote_preview)

    assets = []
    seen_urls = set()

    def add_asset(key: str, label: str, raw_url: str, origin: str) -> None:
        url = _sanitize_preview_video_value(raw_url)
        if not url or url in primary_episode_urls or url in seen_urls:
            return
        seen_urls.add(url)
        lower = url.lower()
        assets.append({
            "key": key,
            "label": label,
            "url": url,
            "transport": "hls" if (".m3u8" in lower or "m3u8" in lower) else "direct",
            "origin": origin,
        })

    add_asset("preview_local", "本地预览", local_preview, "local")
    add_asset("preview_remote", "远端预览", remote_preview, "remote")
    return assets


def _attach_video_playback_projection(video_data: dict, *, source: str = "local") -> dict:
    if not isinstance(video_data, dict):
        return video_data

    primary = _build_primary_playback_summary(video_data, source=source)
    preview_assets = _build_preview_playback_assets(video_data)
    playback = {
        "bucket": "candidate" if str(source or "").strip().lower() == "preview" else "local",
        "primary": primary,
        "preview": {
            "available": bool(preview_assets),
            "default_asset_key": preview_assets[0]["key"] if preview_assets else "",
            "assets": preview_assets,
        },
    }
    video_data["playback"] = playback
    return video_data


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
    latest_data = _attach_video_playback_projection(latest_data, source=source_key)
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

    host_platform = infer_host_video_platform(video_data)
    if host_platform:
        return str(host_platform or "").strip().lower()

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

    host_display_updates = merge_host_video_display(decorated)
    if host_display_updates:
        decorated["display"] = dict(host_display_updates.get("display") or {})

    platform_name = _resolve_protocol_video_platform_name(decorated)
    if platform_name:
        annotated = annotate_item(
            decorated,
            platform_name=platform_name,
            media_type="video",
        )
        if host_display_updates and not annotated.get("display"):
            annotated["display"] = dict(host_display_updates.get("display") or {})
        decorated = annotated

    decorated = _attach_video_playback_projection(decorated, source="preview")
    if include_preview_detail:
        _schedule_preview_video_local_cache(decorated, source="preview")
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


def _build_preview_video_card_dict(video_data: dict, *, tag_map: dict | None = None) -> dict:
    if not isinstance(video_data, dict):
        return {}

    card = dict(video_data)
    card["source"] = "preview"
    _ensure_local_asset_fields(card)
    card["tags"] = [
        {"id": tid, "name": (tag_map or {}).get(tid, tid)}
        for tid in (card.get("tag_ids") or [])
    ]

    host_display_updates = merge_host_video_display(card)
    if host_display_updates:
        card["display"] = dict(host_display_updates.get("display") or {})

    platform_name = _resolve_protocol_video_platform_name(card)
    if platform_name:
        annotated = annotate_item(card, platform_name=platform_name, media_type="video")
        if host_display_updates and not annotated.get("display"):
            annotated["display"] = dict(host_display_updates.get("display") or {})
        card = annotated

    allowed_keys = {
        "id",
        "title",
        "title_jp",
        "creator",
        "score",
        "tag_ids",
        "tags",
        "list_ids",
        "create_time",
        "last_access_time",
        "platform",
        "plugin_id",
        "plugin_name",
        "display",
        "custom_order",
        "code",
        "date",
        "cover_path",
        "cover_path_local",
        "actors",
        "source",
        "storage_size_bytes",
        "storage_size_label",
        "storage_file_count",
        "storage_size_scope",
        "storage_is_soft_ref",
        "storage_excluded_reason",
    }
    return {key: card.get(key) for key in allowed_keys}


def _refresh_preview_video_persisted_fields(video_data: dict) -> bool:
    if not isinstance(video_data, dict):
        return False
    if str(video_data.get("storage_path_relative", "") or "").strip() and str(video_data.get("storage_path_kind", "") or "").strip():
        return False
    try:
        return bool(video_service._refresh_video_persisted_metadata(video_data, source="preview"))
    except Exception as exc:
        error_logger.error(f"回填预览视频存储路径失败: {video_data.get('id')}, {exc}")
        return False

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


def _build_persisted_video_import_fields(
    video_data: dict,
    *,
    platform_name: str,
    plugin_id: str,
    source: str,
) -> dict:
    payload = dict(video_data or {})
    persisted = build_persisted_annotation(
        payload,
        media_type="video",
        plugin_id=plugin_id or None,
        platform_name=platform_name or None,
    )
    video_id = str(payload.get("id") or "").strip()
    if not video_id:
        return persisted

    try:
        root_dir, _, _ = video_service._build_preview_asset_root(video_id, source)
        asset_dir = os.path.join(root_dir, video_service._sanitize_video_asset_id(video_id))
        relative_dir = normalize_data_relative_path(asset_dir)
        if relative_dir:
            persisted["storage_path_relative"] = relative_dir
            persisted["storage_path_kind"] = "preview_asset_dir"
    except Exception:
        pass
    return persisted


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


def _schedule_preview_video_local_cache(video_data: dict, source: str = "local"):
    if not isinstance(video_data, dict):
        return

    video_id = str(video_data.get("id") or "").strip()
    if not video_id:
        return

    preview_assets = _build_preview_playback_assets(video_data)
    if not preview_assets:
        return

    has_local_asset = any(
        str(asset.get("origin") or "").strip().lower() == "local"
        and _is_source_preview_asset(asset.get("url"))
        for asset in preview_assets
    )
    if has_local_asset:
        return

    remote_asset = next(
        (
            asset
            for asset in preview_assets
            if str(asset.get("origin") or "").strip().lower() == "remote"
            and str(asset.get("url") or "").strip()
        ),
        None,
    )
    if not remote_asset:
        return

    platform_name = str(video_data.get("platform") or "").strip().lower()
    if not _platform_allows_preview_video_download(platform=platform_name, video_id=video_id):
        return

    _schedule_video_asset_cache(
        video_id=video_id,
        source=source,
        preview_video=str(remote_asset.get("url") or "").strip(),
        allow_cover=False,
        allow_preview_video=True,
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
                "actor_refs": detail.get("actor_refs", []),
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
            video_data.update(
                _build_persisted_video_import_fields(
                    video_data,
                    platform_name=platform,
                    plugin_id=getattr(_manifest, "plugin_id", ""),
                    source="local",
                )
            )
            
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
            
            document_repo = _get_video_recommendation_document_repository()
            db_data = document_repo.read_document()
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
                "actor_refs": detail.get("actor_refs", []),
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
            video_data.update(
                _build_persisted_video_import_fields(
                    video_data,
                    platform_name=platform,
                    plugin_id=getattr(_manifest, "plugin_id", ""),
                    source="preview",
                )
            )
            
            if videos_key not in db_data:
                db_data[videos_key] = []
            db_data[videos_key].append(video_data)
            
            if not document_repo.write_document(db_data):
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
        from application.tag_app_service import TagAppService
        from domain.tag.entity import ContentType

        sort_type = request.args.get('sort_type')
        sort_order = request.args.get('sort_order', 'desc')
        min_score = request.args.get('min_score', type=float)
        max_score = request.args.get('max_score', type=float)
        keyword = request.args.get('keyword', '')
        include_tag_ids = set(normalize_string_list(request.args.getlist('include_tag_ids')))
        exclude_tag_ids = set(normalize_string_list(request.args.getlist('exclude_tag_ids')))
        authors = set(normalize_string_list(request.args.getlist('authors')))
        list_ids = set(normalize_string_list(request.args.getlist('list_ids')))
        paginate = _parse_bool_arg('paginate')
        summary_only = _parse_bool_arg('summary')
        include_available_authors = _parse_bool_arg('include_available_authors')
        include_storage_usage = _parse_bool_arg('include_storage_usage')
        page = request.args.get('page', default=1, type=int)
        page_size = request.args.get('page_size', default=24, type=int)

        document_repo = _get_video_recommendation_document_repository()
        db_data = document_repo.read_document()
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
            if max_score is not None and (video.get('score') or 0) > max_score:
                continue
            video_tag_ids = set(str(tag_id or "").strip() for tag_id in (video.get('tag_ids') or []) if str(tag_id or "").strip())
            if include_tag_ids and not include_tag_ids.issubset(video_tag_ids):
                continue
            if exclude_tag_ids and exclude_tag_ids.intersection(video_tag_ids):
                continue
            if authors:
                video_authors = set(
                    str(actor or "").strip()
                    for actor in (video.get('actors') or [])
                    if str(actor or "").strip()
                )
                creator = str(video.get('creator') or '').strip()
                if creator:
                    video_authors.add(creator)
                if not authors.intersection(video_authors):
                    continue
            if list_ids:
                video_list_ids = set(str(list_id or "").strip() for list_id in (video.get('list_ids') or []) if str(list_id or "").strip())
                if not list_ids.intersection(video_list_ids):
                    continue
            if keyword and not matches_keyword(video, keyword, tag_map=tag_map):
                continue

            filtered_videos.append(video)

        filtered_videos = sort_content_items(
            filtered_videos,
            sort_type or 'create_time',
            sort_order,
        )

        def serialize_card(item):
            if include_storage_usage:
                annotate_video_storage_usage([item], source="preview")
            return _build_preview_video_card_dict(item, tag_map=tag_map)

        def serialize_detail(item):
            if include_storage_usage:
                annotate_video_storage_usage([item], source="preview")
            return _decorate_video_recommendation_item(item, tag_map=tag_map)

        if paginate:
            payload = build_paginated_payload(
                filtered_videos,
                page=normalize_page(page, 1),
                page_size=normalize_page_size(page_size),
                serializer=serialize_card if summary_only else serialize_detail,
                extra={
                    "available_authors": extract_available_authors(filtered_videos) if include_available_authors else [],
                },
            )
            return success_response(payload)

        serializer = serialize_card if summary_only else serialize_detail
        return success_response([serializer(item) for item in filtered_videos])
    except Exception as e:
        error_logger.error(f"获取推荐视频列表失败: {e}")
        return error_response(500, "服务器内部错误")


@video_bp.route('/recommendation/custom-order', methods=['PUT'])
def update_video_recommendation_custom_order():
    try:
        data = request.json or {}
        video_ids = data.get('video_ids', [])
        result = video_service.update_custom_order(video_ids, source="preview")
        if result.success:
            return success_response(result.data, result.message or "自定义排序已保存")
        return error_response(400, result.message)
    except Exception as e:
        error_logger.error(f"保存推荐视频自定义排序失败: {e}")
        return error_response(500, "服务器内部错误")


@video_bp.route('/recommendation/detail', methods=['GET'])
def get_video_recommendation_detail():
    """获取推荐视频详情"""
    try:
        from application.tag_app_service import TagAppService
        from domain.tag.entity import ContentType
        
        video_id = request.args.get('video_id')
        if not video_id:
            return error_response(400, "缺少参数: video_id")
        
        document_repo = _get_video_recommendation_document_repository()
        db_data = document_repo.read_document()
        videos = db_data.get('video_recommendations', [])
        
        tag_service = TagAppService()
        tags = tag_service.get_tag_list(ContentType.VIDEO).data or []
        tag_map = {t["id"]: t["name"] for t in tags}
        
        for video in videos:
            if video.get('id') == video_id:
                if _refresh_preview_video_persisted_fields(video):
                    document_repo.write_document(db_data)
                annotate_video_storage_usage([video], source="preview")
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
        
        document_repo = _get_video_recommendation_document_repository()
        db_data = document_repo.read_document()
        videos = db_data.get('video_recommendations', [])
        
        found = False
        for video in videos:
            if video.get('id') == video_id:
                video.update(meta)
                found = True
                break
        
        if not found:
            return error_response(404, "视频不存在")
        
        if not document_repo.write_document(db_data):
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
        data = request.json
        if not data or 'video_id' not in data or 'tag_id_list' not in data:
            return error_response(400, "缺少参数: video_id 或 tag_id_list")
        
        video_id = data['video_id']
        tag_id_list = data['tag_id_list']
        validated_tag_ids, validation_error = validate_tag_ids_for_content_type(
            TagJsonRepository(),
            tag_id_list,
            ContentType.VIDEO,
        )
        if validation_error:
            return error_response(400, validation_error)
        
        document_repo = _get_video_recommendation_document_repository()
        db_data = document_repo.read_document()
        videos = db_data.get('video_recommendations', [])
        
        found = False
        for video in videos:
            if video.get('id') == video_id:
                video['tag_ids'] = validated_tag_ids
                found = True
                break
        
        if not found:
            return error_response(404, "视频不存在")
        
        if not document_repo.write_document(db_data):
            return error_response(500, "数据写入失败")
        
        app_logger.info(f"绑定推荐视频标签成功: {video_id}, 标签: {validated_tag_ids}")
        return success_response({"message": "标签绑定成功"})
    except Exception as e:
        error_logger.error(f"绑定推荐视频标签失败: {e}")
        return error_response(500, "服务器内部错误")


@video_bp.route('/recommendation/score', methods=['PUT'])
def update_video_recommendation_score():
    """更新推荐视频评分"""
    try:
        data = request.json
        video_id = data.get('video_id')
        score = data.get('score')
        
        if not video_id or score is None:
            return error_response(400, "缺少参数")
        
        document_repo = _get_video_recommendation_document_repository()
        db_data = document_repo.read_document()
        videos = db_data.get('video_recommendations', [])
        
        found = False
        for video in videos:
            if video.get('id') == video_id:
                video['score'] = score
                found = True
                break
        
        if not found:
            return error_response(404, "视频不存在")
        
        if not document_repo.write_document(db_data):
            return error_response(500, "数据写入失败")
        
        return success_response({"message": "评分更新成功"})
    except Exception as e:
        error_logger.error(f"更新推荐视频评分失败: {e}")
        return error_response(500, "服务器内部错误")


@video_bp.route('/recommendation/trash/move', methods=['PUT'])
def move_video_recommendation_to_trash():
    """移动推荐视频到回收站"""
    try:
        data = request.json
        video_id = data.get('video_id')
        
        if not video_id:
            return error_response(400, "缺少参数")
        
        document_repo = _get_video_recommendation_document_repository()
        db_data = document_repo.read_document()
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
        
        if not document_repo.write_document(db_data):
            return error_response(500, "数据写入失败")
        
        return success_response({"message": "已移入回收站"})
    except Exception as e:
        error_logger.error(f"移动推荐视频到回收站失败: {e}")
        return error_response(500, "服务器内部错误")


@video_bp.route('/recommendation/trash/batch-move', methods=['PUT'])
def batch_move_video_recommendation_to_trash():
    """批量移动推荐视频到回收站"""
    try:
        data = request.json
        video_ids = data.get('video_ids', [])
        
        if not video_ids:
            return error_response(400, "缺少参数")
        
        document_repo = _get_video_recommendation_document_repository()
        db_data = document_repo.read_document()
        videos = db_data.get('video_recommendations', [])
        
        count = 0
        for video in videos:
            if video.get('id') in video_ids:
                video['is_deleted'] = True
                video['deleted_time'] = get_current_time()
                count += 1
        
        if not document_repo.write_document(db_data):
            return error_response(500, "数据写入失败")
        
        return success_response({"moved_count": count}, f"已将 {count} 个视频移入回收站")
    except Exception as e:
        error_logger.error(f"批量移动推荐视频到回收站失败: {e}")
        return error_response(500, "服务器内部错误")


@video_bp.route('/recommendation/trash/list', methods=['GET'])
def get_video_recommendation_trash_list():
    """获取推荐视频回收站列表"""
    try:
        from application.tag_app_service import TagAppService
        from domain.tag.entity import ContentType

        document_repo = _get_video_recommendation_document_repository()
        db_data = document_repo.read_document()
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
        data = request.json
        video_id = data.get('video_id')
        
        if not video_id:
            return error_response(400, "缺少参数")
        
        document_repo = _get_video_recommendation_document_repository()
        db_data = document_repo.read_document()
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
        
        if not document_repo.write_document(db_data):
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
        video_id = request.args.get('video_id')
        if not video_id:
            return error_response(400, "缺少参数")
        
        document_repo = _get_video_recommendation_document_repository()
        db_data = document_repo.read_document()
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
        
        if not document_repo.write_document(db_data):
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
        data = request.json
        video_ids = data.get('video_ids', [])
        
        if not video_ids:
            return error_response(400, "缺少参数")
        
        document_repo = _get_video_recommendation_document_repository()
        db_data = document_repo.read_document()
        videos = db_data.get('video_recommendations', [])
        
        count = 0
        for video in videos:
            if video.get('id') in video_ids:
                video['is_deleted'] = False
                if 'deleted_time' in video:
                    del video['deleted_time']
                count += 1
        
        if not document_repo.write_document(db_data):
            return error_response(500, "数据写入失败")
        
        return success_response({"restored_count": count}, f"已恢复 {count} 个视频")
    except Exception as e:
        error_logger.error(f"批量恢复推荐视频失败: {e}")
        return error_response(500, "服务器内部错误")


@video_bp.route('/recommendation/trash/batch-delete', methods=['DELETE'])
def batch_delete_video_recommendation_permanently():
    """批量永久删除推荐视频"""
    try:
        data = request.json
        video_ids = data.get('video_ids', [])
        
        if not video_ids:
            return error_response(400, "缺少参数")
        
        document_repo = _get_video_recommendation_document_repository()
        db_data = document_repo.read_document()
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
        
        if not document_repo.write_document(db_data):
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
        from application.tag_app_service import TagAppService
        from domain.tag.entity import ContentType
        
        keyword = request.args.get('keyword')
        if not keyword:
            return error_response(400, "缺少参数: keyword")
        
        keyword = keyword.lower()
        
        document_repo = _get_video_recommendation_document_repository()
        db_data = document_repo.read_document()
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
    """获取推荐视频播放链接"""
    try:
        playback_source = _normalize_playback_source_arg(request.args.get("playback_source", ""))
        remote_provider = _normalize_remote_provider_arg(request.args.get("remote_provider", ""))
        document_repo = _get_video_recommendation_document_repository()
        db_data = document_repo.read_document()
        videos = db_data.get('video_recommendations', [])
        
        video = None
        for v in videos:
            if v.get('id') == video_id:
                video = v
                break
        
        if not video:
            return error_response(404, "视频不存在")

        if playback_source == "local":
            return error_response(400, "推荐库视频不支持本地播放源")

        remote_result = _resolve_remote_video_sources(video_id, video, remote_provider=remote_provider)
        if remote_result.success:
            return success_response(remote_result.data)
        return error_response(400, remote_result.message or "远程播放源不可用")
        
    except Exception as e:
        error_logger.error(f"获取播放链接失败: {e}")
        return error_response(500, "服务器内部错误")

@video_bp.route('/<video_id>/play-urls', methods=['GET'])
def get_video_play_urls(video_id):
    """获取视频播放链接"""
    try:
        playback_source = _normalize_playback_source_arg(request.args.get("playback_source", ""))
        remote_provider = _normalize_remote_provider_arg(request.args.get("remote_provider", ""))
        result = video_service.get_video_detail(video_id)
        if not result.success or not result.data:
            return error_response(404, "视频不存在")
        
        video = result.data
        code = str(video.get('code', '') or '').strip()
        title = str(video.get('title', '') or '').strip()

        if playback_source == "local":
            local_sources = _build_local_video_sources(video)
            if local_sources:
                local_provider_groups = [
                    _build_provider_group(
                        key="local",
                        label="本地文件",
                        kind="local",
                        selection_mode="episodes",
                        sources=local_sources,
                    )
                ]
                return success_response(
                    _build_play_urls_payload(
                        video_id=video_id,
                        code=code,
                        title=title,
                        playback_source="local",
                        provider_groups=local_provider_groups,
                        requested_provider_key="local",
                    )
                )
            return error_response(400, "本地播放源不可用")

        if playback_source == "remote":
            remote_result = _resolve_remote_video_sources(video_id, video, remote_provider=remote_provider)
            if remote_result.success:
                return success_response(remote_result.data)
            return error_response(400, remote_result.message or "远程播放源不可用")

        local_sources = _build_local_video_sources(video)
        if local_sources:
            local_provider_groups = [
                _build_provider_group(
                    key="local",
                    label="本地文件",
                    kind="local",
                    selection_mode="episodes",
                    sources=local_sources,
                )
            ]
            return success_response(
                _build_play_urls_payload(
                    video_id=video_id,
                    code=code,
                    title=title,
                    playback_source="local",
                    provider_groups=local_provider_groups,
                    requested_provider_key="local",
                )
            )

        if not code:
            return error_response(400, "视频没有番号信息")

        if not is_third_party_enabled():
            return error_response(
                503,
                f"third-party integration is disabled in current runtime profile: {get_runtime_profile()}"
            )

        remote_result = _resolve_remote_video_sources(video_id, video, remote_provider="")
        if remote_result.success:
            return success_response(remote_result.data)
        return error_response(400, remote_result.message or "远程播放源不可用")
        
    except Exception as e:
        error_logger.error(f"获取播放链接失败: {e}")
        return error_response(500, "服务器内部错误")


@video_bp.route('/proxy/<domain>/<path:path>', methods=['GET'])
@require_third_party(error_response)
def proxy_video_request(domain, path):
    """代理视频请求，解决跨域问题"""
    try:
        proxy_result = _get_video_proxy_client().proxy_stream(
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

        proxy_result = _get_video_proxy_client().proxy_url(
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
