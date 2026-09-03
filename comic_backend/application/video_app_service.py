"""
视频应用服务
Mmmtttt
"""

from typing import List, Dict, Optional, Any, Tuple, Callable
import base64
import math
import os
import re
import shutil
import tempfile
import threading
import time
import traceback
import requests
from io import BytesIO
from urllib.parse import urlparse, urljoin, unquote
from PIL import Image
from application.content_sorting import (
    normalize_custom_order_records,
    sort_content_items,
)
from application.catalog_query_service import CatalogQueryService
from application.cover_versioning import annotate_cover_url
from application.list_query_support import (
    build_paginated_payload,
    extract_available_authors,
    matches_keyword,
    normalize_page,
    normalize_page_size,
    normalize_string_list,
)
from application.persisted_content_metadata import (
    build_persisted_annotation,
    normalize_data_relative_path,
    resolve_data_relative_path,
)
from application.storage_usage_service import annotate_video_storage_usage

from domain.video import Video, VideoRepository
from domain.video_recommendation import VideoRecommendationRepository, VideoRecommendation
from domain.tag import Tag, TagRepository
from domain.actor import ActorSubscription, ActorRepository
from infrastructure.persistence.repositories.video_repository_impl import VideoJsonRepository
from infrastructure.persistence.repositories.video_recommendation_repository_impl import VideoRecommendationJsonRepository
from infrastructure.persistence.repositories.tag_repository_impl import TagJsonRepository
from infrastructure.persistence.repositories.actor_repository_impl import ActorJsonRepository
from infrastructure.persistence.repositories.document_repository import JsonDocumentRepository
from infrastructure.persistence.json_storage import JsonStorage
from infrastructure.persistence.cache import CacheManager
from infrastructure.common.result import ServiceResult
from infrastructure.logger import app_logger, error_logger
from core.host_platform_fallback import infer_host_video_platform, merge_host_video_display
from core.utils import get_current_time, generate_id, generate_uuid
from core.constants import (
    DATA_DIR,
    STATIC_DIR,
    VIDEO_CACHE_DIR,
    VIDEO_DIR,
    VIDEO_RECOMMENDATION_CACHE_DIR,
    VIDEO_JSON_FILE,
    VIDEO_RECOMMENDATION_JSON_FILE,
)
from core.enums import ContentType
from application.tag_content_type_guard import validate_tag_ids_for_content_type
from application.base.content_app_service import BaseContentAppService
from application.local_video_thumbnail_service import (
    DEFAULT_LOCAL_VIDEO_THUMBNAIL_COUNT,
    DEFAULT_LOCAL_VIDEO_THUMBNAIL_WIDTH,
    FFmpegLocalVideoThumbnailService,
    probe_local_video_thumbnail_runtime,
)
from application.video_runtime_support import get_preview_request_client
from protocol.gateway import get_protocol_gateway
from protocol.platform_meta import (
    build_platform_root_dir,
    resolve_manifest_host_prefix,
    resolve_manifest_platform_label,
    resolve_platform_manifest,
    split_prefixed_id,
)
from protocol.presentation import annotate_item
from protocol.runtime_config import get_protocol_config_store


class _ProtocolVideoMetadataAdapter:
    def __init__(self, gateway, manifest):
        self._gateway = gateway
        self._manifest = manifest
        self.platform_name = str(
            resolve_manifest_platform_label(
                manifest,
                fallback=getattr(manifest, "config_key", "") or getattr(manifest, "plugin_id", ""),
            )
            or ""
        ).strip().lower()

    @staticmethod
    def _payload_field_has_value(payload: Dict[str, Any], field_name: str) -> bool:
        value = payload.get(field_name)
        if isinstance(value, str):
            return bool(value.strip())
        if isinstance(value, (list, tuple, set, dict)):
            return len(value) > 0
        return value is not None

    def _execute(self, capability: str, params: Dict[str, Any]) -> Any:
        return self._gateway.execute_plugin(
            self._manifest.plugin_id,
            capability,
            params=params,
        )

    def search_videos(self, keyword: str, page: int = 1, max_pages: int = 1) -> Dict[str, Any]:
        return self._execute(
            "catalog.search",
            {
                "keyword": keyword,
                "page": page,
                "max_pages": max_pages,
            },
        ) or {}

    def get_video_detail(self, video_id: str, movie_type=None) -> Optional[Dict[str, Any]]:
        if not self._manifest.has_capability("catalog.detail"):
            return None
        return self._execute(
            "catalog.detail",
            {
                "video_id": video_id,
                "movie_type": movie_type,
            },
        ) or {}

    def get_video_by_code(self, code: str) -> Optional[Dict[str, Any]]:
        if not self._manifest.has_capability("catalog.by_code"):
            return None
        return self._execute("catalog.by_code", {"code": code}) or {}

    def should_skip_remote_detail(self, first_result: Dict[str, Any]) -> bool:
        search_entry = dict(self._manifest.get_capability_entry("catalog.search") or {})
        detail_policy = dict(search_entry.get("result_detail_policy") or {})
        mode = str(detail_policy.get("mode") or "").strip().lower()
        fields = [
            str(item or "").strip()
            for item in (detail_policy.get("fields") or [])
            if str(item or "").strip()
        ]

        if mode in {"search_payload", "search_payload_only", "prefer_search_payload"}:
            return True

        if mode == "search_payload_if_fields_present":
            if not fields:
                return False
            return all(self._payload_field_has_value(first_result, field_name) for field_name in fields)

        return False


class VideoAppService(BaseContentAppService):
    _entity_name = "视频"
    _cache_manager = CacheManager()
    RECENT_IMPORT_TAG_ID = "tag_video_recent_import"
    RECENT_IMPORT_TAG_NAME = "最近导入"
    PREVIEW_ASSET_COVER_NAME = "cover.jpg"
    PREVIEW_VIDEO_MAX_BYTES = 180 * 1024 * 1024
    PREVIEW_VIDEO_EXTENSIONS = (".mp4", ".webm", ".mov", ".m4v", ".m3u8")
    LOCAL_VIDEO_ID_PREFIX = "LOCALV"
    ABNORMAL_CODE_PREFIX = "LOCALERR_"
    LOCAL_VIDEO_FILENAME = "source"
    LOCAL_IMPORT_MODE_HARDLINK_MOVE = "hardlink_move"
    LOCAL_IMPORT_MODE_SOFTLINK_REF = "softlink_ref"
    LOCAL_IMPORT_GROUPING_PER_FILE = "per_file"
    LOCAL_IMPORT_GROUPING_LEAF_DIR = "leaf_dir"
    SOURCE_ORIGIN_LOCAL_IMPORT = "local_import"
    SOURCE_ORIGIN_MAGNET_DOWNLOAD = "magnet_download"
    LOCAL_THUMBNAIL_TARGET_COUNT = DEFAULT_LOCAL_VIDEO_THUMBNAIL_COUNT
    LOCAL_THUMBNAIL_WIDTH = DEFAULT_LOCAL_VIDEO_THUMBNAIL_WIDTH
    VIDEO_FILE_EXTENSIONS = (
        ".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm",
        ".m4v", ".ts", ".m2ts", ".rmvb", ".mpg", ".mpeg",
    )
    ARCHIVE_FILE_EXTENSIONS = (".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz")
    CODE_PATTERN = re.compile(r"(?<![A-Za-z0-9])([A-Za-z]{2,7})[\s_-]?([0-9]{2,4})(?![A-Za-z0-9])")
    FC2_PATTERN = re.compile(
        r"(?i)(?:^|[^a-z0-9])(fc2)\s*[-_ ]?\s*(?:ppv\s*[-_ ]?)?([0-9]{4,8})(?:$|[^a-z0-9])"
    )
    GENERIC_CODE_PREFIXES = {
        "EPISODE",
        "PART",
        "CHAPTER",
        "VOLUME",
        "VOL",
        "DISC",
        "DISK",
    }
    _asset_download_lock = threading.Lock()
    _asset_download_tasks = set()
    
    def __init__(
        self,
        video_repo: VideoRepository = None,
        video_rec_repo: VideoRecommendationRepository = None,
        tag_repo: TagRepository = None,
        actor_repo: ActorRepository = None
    ):
        self._video_repo = video_repo or VideoJsonRepository()
        self._video_rec_repo = video_rec_repo or VideoRecommendationJsonRepository()
        self._tag_repo = tag_repo or TagJsonRepository()
        self._actor_repo = actor_repo or ActorJsonRepository()
        self._video_document_repo = JsonDocumentRepository(VIDEO_JSON_FILE, "videos", "total_videos")
        self._video_recommendation_document_repo = JsonDocumentRepository(
            VIDEO_RECOMMENDATION_JSON_FILE,
            "video_recommendations",
            "total_video_recommendations",
        )
        self._catalog_query_service = CatalogQueryService()

    def _get_repo_by_source(self, source: str = "local"):
        return self._video_rec_repo if source == "preview" else self._video_repo

    @staticmethod
    def _apply_persisted_fields(target: Any, updates: Dict[str, Any]) -> bool:
        changed = False
        for key, value in (updates or {}).items():
            if isinstance(target, dict):
                current = target.get(key)
                if current != value:
                    target[key] = value
                    changed = True
                continue

            if getattr(target, key, None) != value:
                setattr(target, key, value)
                changed = True
        return changed

    def _build_video_persisted_metadata(
        self,
        video_payload: Dict[str, Any],
        *,
        storage_path: str = "",
        storage_kind: str = "",
        platform_name: str = "",
        plugin_id: str = "",
    ) -> Dict[str, Any]:
        persisted = build_persisted_annotation(
            video_payload,
            media_type="video",
            plugin_id=plugin_id or None,
            platform_name=platform_name or None,
        )
        if storage_path:
            relative_path = normalize_data_relative_path(storage_path)
            if relative_path:
                persisted["storage_path_relative"] = relative_path
        if storage_kind:
            persisted["storage_path_kind"] = storage_kind
        return persisted

    @staticmethod
    def _format_cover_aspect_ratio(width: int, height: int) -> str:
        try:
            width_value = int(width)
            height_value = int(height)
        except Exception:
            return ""
        if width_value <= 0 or height_value <= 0:
            return ""

        ratio = width_value / height_value
        common_ratios = (
            (16, 9),
            (3, 2),
            (4, 3),
            (1, 1),
            (2, 3),
            (9, 16),
        )
        closest = min(common_ratios, key=lambda item: abs((item[0] / item[1]) - ratio))
        if abs((closest[0] / closest[1]) - ratio) <= 0.08:
            return f"{closest[0]} / {closest[1]}"

        divisor = math.gcd(width_value, height_value)
        if divisor > 0:
            width_value //= divisor
            height_value //= divisor
        return f"{width_value} / {height_value}"

    def _build_video_display_from_cover_asset(self, video_payload: Dict[str, Any]) -> Dict[str, Any]:
        host_display_updates = merge_host_video_display(video_payload)
        if host_display_updates:
            return host_display_updates

        raw_display = dict((video_payload or {}).get("display") or {})
        cover_display = dict(raw_display.get("cover") or {})
        if str(cover_display.get("aspect_ratio") or "").strip():
            return {}

        cover_candidates = [
            str((video_payload or {}).get("cover_path_local") or "").strip(),
            str((video_payload or {}).get("cover_path") or "").strip(),
        ]
        for candidate in cover_candidates:
            abs_path = self._resolve_static_asset_abs_path(candidate)
            if not abs_path or not os.path.isfile(abs_path):
                continue
            try:
                with Image.open(abs_path) as image:
                    aspect_ratio = self._format_cover_aspect_ratio(*image.size)
            except Exception:
                continue
            if not aspect_ratio:
                continue

            cover_display["aspect_ratio"] = aspect_ratio
            cover_display.setdefault("mobile_aspect_ratio", aspect_ratio)
            raw_display["cover"] = cover_display
            return {"display": raw_display}

        return {}

    def _ensure_recent_import_tag_id(self) -> Optional[str]:
        configured_tag = self._tag_repo.get_by_id(self.RECENT_IMPORT_TAG_ID)
        if configured_tag and configured_tag.content_type == ContentType.VIDEO:
            if configured_tag.name != self.RECENT_IMPORT_TAG_NAME:
                configured_tag.name = self.RECENT_IMPORT_TAG_NAME
                self._tag_repo.save(configured_tag)
            return configured_tag.id

        for tag in self._tag_repo.get_all(ContentType.VIDEO):
            if tag.name == self.RECENT_IMPORT_TAG_NAME:
                return tag.id

        new_tag_id = self.RECENT_IMPORT_TAG_ID if configured_tag is None else generate_id("tag")
        new_tag = Tag(
            id=new_tag_id,
            name=self.RECENT_IMPORT_TAG_NAME,
            content_type=ContentType.VIDEO,
            create_time=get_current_time()
        )
        if self._tag_repo.save(new_tag):
            app_logger.info(f"创建视频系统标签: {self.RECENT_IMPORT_TAG_NAME} ({new_tag.id})")
            return new_tag.id

        error_logger.error("创建视频系统标签失败")
        return None

    @classmethod
    def _resolve_video_annotation_platform_name(cls, video_data: Dict[str, Any]) -> str:
        raw = dict(video_data or {})
        explicit_platform = str(raw.get("platform") or "").strip()
        if explicit_platform and explicit_platform.lower() != "local":
            return explicit_platform

        host_platform = infer_host_video_platform(raw)
        if host_platform and host_platform.lower() != "local":
            return host_platform

        return ""

    @classmethod
    def _annotate_video_record(cls, video_data: Dict[str, Any]) -> Dict[str, Any]:
        raw = dict(video_data or {})
        host_display_updates = merge_host_video_display(raw)
        if host_display_updates:
            raw["display"] = dict(host_display_updates.get("display") or {})

        platform_name = cls._resolve_video_annotation_platform_name(raw)
        if not platform_name:
            return raw
        annotated = annotate_item(raw, platform_name=platform_name, media_type="video")
        if host_display_updates and not annotated.get("display"):
            annotated["display"] = dict(host_display_updates.get("display") or {})
        return annotated

    @classmethod
    def _annotate_video_records(cls, video_records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [
            cls._annotate_video_record(item)
            for item in (video_records or [])
            if isinstance(item, dict)
        ]

    @classmethod
    def _video_to_card_dict(cls, video: Video) -> Dict[str, Any]:
        payload = {
            "id": video.id,
            "title": video.title,
            "title_jp": video.title_jp,
            "creator": video.creator,
            "score": video.score,
            "tag_ids": list(video.tag_ids or []),
            "list_ids": list(video.list_ids or []),
            "create_time": video.create_time,
            "last_access_time": video.last_access_time,
            "platform": video.platform,
            "plugin_id": video.plugin_id,
            "plugin_name": video.plugin_name,
            "display": dict(video.display or {}),
            "custom_order": video.custom_order,
            "code": video.code,
            "date": video.date,
            "cover_path": video.cover_path,
            "cover_path_local": video.cover_path_local,
            "actors": list(video.actors or []),
            "source": "local",
        }
        payload.update(cls._storage_fields_from_item(video))
        annotate_cover_url(payload)
        return cls._annotate_video_record(payload)

    @staticmethod
    def _storage_fields_from_item(item: Any) -> Dict[str, Any]:
        fields: Dict[str, Any] = {}
        for key in (
            "storage_size_bytes",
            "storage_size_label",
            "storage_file_count",
            "storage_size_scope",
            "storage_is_soft_ref",
            "storage_excluded_reason",
        ):
            value = getattr(item, key, None)
            if value is not None:
                fields[key] = value
        return fields

    def apply_recent_import_tags(
        self,
        video_ids: List[str],
        source: str = "local",
        clear_previous: bool = True
    ) -> ServiceResult:
        try:
            target_ids = [video_id for video_id in dict.fromkeys(video_ids or []) if video_id]
            if not target_ids:
                return ServiceResult.ok({
                    "tag_id": None,
                    "updated_count": 0,
                    "cleared_count": 0
                }, "无需更新最近导入标签")

            tag_id = self._ensure_recent_import_tag_id()
            if not tag_id:
                return ServiceResult.error("创建最近导入标签失败")

            repo = self._get_repo_by_source(source)

            cleared_count = 0
            with JsonStorage.defer_catalog_index_sync():
                if clear_previous:
                    clearing_ids = [
                        video.id
                        for video in repo.get_all()
                        if tag_id in (video.tag_ids or [])
                    ]
                    if hasattr(repo, "update_many_by_ids"):
                        cleared_count = repo.update_many_by_ids(
                            clearing_ids,
                            lambda video: video.remove_tags([tag_id]),
                        )
                    else:
                        for video_id in clearing_ids:
                            video = repo.get_by_id(video_id)
                            if video:
                                video.remove_tags([tag_id])
                                if repo.save(video):
                                    cleared_count += 1

                def add_recent_import_tag(video) -> bool | None:
                    if tag_id in (video.tag_ids or []):
                        return False
                    video.add_tags([tag_id])
                    return None

                if hasattr(repo, "update_many_by_ids"):
                    updated_count = repo.update_many_by_ids(target_ids, add_recent_import_tag)
                else:
                    updated_count = 0
                    for video_id in target_ids:
                        video = repo.get_by_id(video_id)
                        if not video:
                            continue
                        if add_recent_import_tag(video) is False:
                            continue
                        if repo.save(video):
                            updated_count += 1

            app_logger.info(
                f"更新视频最近导入标签完成: source={source}, tag_id={tag_id}, "
                f"cleared={cleared_count}, updated={updated_count}"
            )
            return ServiceResult.ok({
                "tag_id": tag_id,
                "updated_count": updated_count,
                "cleared_count": cleared_count
            }, "更新最近导入标签成功")
        except Exception as e:
            error_logger.error(f"更新视频最近导入标签失败: {e}")
            return ServiceResult.error("更新最近导入标签失败")

    @staticmethod
    def _commit_custom_order(document_repo: JsonDocumentRepository, ordered_ids: List[str] = None) -> bool:
        changed = False
        processed = False

        def update_items(items: List[Dict[str, Any]]):
            nonlocal changed, processed
            normalized_items, did_change = normalize_custom_order_records(items, ordered_ids)
            changed = did_change
            processed = True
            return normalized_items if did_change else None

        updated = document_repo.update_items(update_items)
        if updated:
            return True
        return processed and not changed
    
    def get_video_list(
        self,
        sort_type: str = "create_time",
        sort_order: str = "desc",
        min_score: float = None,
        max_score: float = None,
        include_deleted: bool = False,
        keyword: str = "",
        include_tags: List[str] = None,
        exclude_tags: List[str] = None,
        authors: List[str] = None,
        list_ids: List[str] = None,
        page: int = 1,
        page_size: int = 24,
        paginate: bool = False,
        summary_only: bool = False,
        include_available_authors: bool = False,
        include_storage_usage: bool = False
    ) -> ServiceResult:
        try:
            if paginate and not include_storage_usage:
                tags = self._tag_repo.get_all()
                tag_map = {t.id: t.name for t in tags}

                def indexed_serializer(item: Dict[str, Any]) -> Dict[str, Any]:
                    video = Video.from_dict(item)
                    if summary_only:
                        return self._video_to_card_dict(video)
                    payload = {
                        **video.to_dict(),
                        **self._storage_fields_from_item(video),
                        "tags": [{"id": tid, "name": tag_map.get(tid, tid)} for tid in video.tag_ids],
                    }
                    annotate_cover_url(payload)
                    return payload

                indexed_payload = self._catalog_query_service.query_local_page(
                    media_type="video",
                    serializer=indexed_serializer,
                    sort_type=sort_type,
                    sort_order=sort_order,
                    min_score=min_score,
                    max_score=max_score,
                    keyword=keyword,
                    include_tags=include_tags,
                    exclude_tags=exclude_tags,
                    authors=authors,
                    list_ids=list_ids,
                    page=page,
                    page_size=page_size,
                    include_available_authors=include_available_authors,
                )
                if indexed_payload is not None:
                    app_logger.info(
                        f"通过 SQLite 索引获取视频分页列表成功，页 {indexed_payload['page']}/"
                        f"{indexed_payload['total_pages']}，总计 {indexed_payload['total']} 个视频"
                    )
                    return ServiceResult.ok(indexed_payload)

            videos = self._video_repo.get_all()
            tags = self._tag_repo.get_all()
            tag_map = {t.id: t.name for t in tags}

            include_tag_ids = set(normalize_string_list(include_tags))
            exclude_tag_ids = set(normalize_string_list(exclude_tags))
            author_set = set(normalize_string_list(authors))
            list_id_set = set(normalize_string_list(list_ids))

            if not include_deleted:
                videos = [v for v in videos if not v.is_deleted]

            if min_score is not None:
                videos = [v for v in videos if v.score is not None and v.score >= min_score]
            if max_score is not None:
                videos = [v for v in videos if v.score is not None and v.score <= max_score]
            if include_tag_ids:
                videos = [v for v in videos if include_tag_ids.issubset(set(v.tag_ids or []))]
            if exclude_tag_ids:
                videos = [v for v in videos if not exclude_tag_ids.intersection(set(v.tag_ids or []))]
            if author_set:
                videos = [
                    v for v in videos
                    if author_set.intersection(
                        set(str(actor or "").strip() for actor in (v.actors or []) if str(actor or "").strip())
                    ) or str(v.creator or "").strip() in author_set
                ]
            if list_id_set:
                videos = [v for v in videos if list_id_set.intersection(set(v.list_ids or []))]
            if keyword:
                videos = [v for v in videos if matches_keyword(v, keyword, tag_map=tag_map)]
            if sort_type:
                videos = sort_content_items(videos, sort_type, sort_order)

            def serialize_video_card(video):
                if include_storage_usage:
                    annotate_video_storage_usage([video], source="local")
                return self._video_to_card_dict(video)

            def serialize_video_summary(video):
                if include_storage_usage:
                    annotate_video_storage_usage([video], source="local")
                payload = {
                    **video.to_dict(),
                    **self._storage_fields_from_item(video),
                    "tags": [{"id": tid, "name": tag_map.get(tid, tid)} for tid in video.tag_ids],
                }
                annotate_cover_url(payload)
                return payload

            if paginate:
                payload = build_paginated_payload(
                    videos,
                    page=normalize_page(page, 1),
                    page_size=normalize_page_size(page_size),
                    serializer=serialize_video_card if summary_only else serialize_video_summary,
                    extra={
                        "available_authors": extract_available_authors(videos) if include_available_authors else [],
                    },
                )
                app_logger.info(
                    f"获取视频分页列表成功，页 {payload['page']}/{payload['total_pages']}，总计 {payload['total']} 个视频"
                )
                return ServiceResult.ok(payload)

            video_list = []
            for v in videos:
                if summary_only:
                    video_list.append(serialize_video_card(v))
                    continue
                video_list.append(serialize_video_summary(v))
            if not summary_only:
                video_list = self._annotate_video_records(video_list)

            app_logger.info(f"获取视频列表成功，共 {len(video_list)} 个视频")
            return ServiceResult.ok(video_list)
        except Exception as e:
            error_logger.error(f"获取视频列表失败: {e}")
            return ServiceResult.error("获取视频列表失败")

    def update_custom_order(self, video_ids: List[str], source: str = "local") -> ServiceResult:
        try:
            normalized_ids = [
                str(video_id or "").strip()
                for video_id in (video_ids or [])
                if str(video_id or "").strip()
            ]
            if not normalized_ids:
                return ServiceResult.error("缺少参数: video_ids")

            document_repo = (
                self._video_recommendation_document_repo
                if str(source or "").strip().lower() == "preview"
                else self._video_document_repo
            )
            if not self._commit_custom_order(document_repo, normalized_ids):
                return ServiceResult.error("保存自定义排序失败")

            return ServiceResult.ok({"updated_count": len(normalized_ids)}, "自定义排序已保存")
        except Exception as e:
            error_logger.error(f"保存视频自定义排序失败: {e}")
            return ServiceResult.error("保存自定义排序失败")
    
    def get_video_detail(self, video_id: str) -> ServiceResult:
        try:
            video = self._video_repo.get_by_id(video_id)
            if not video:
                return ServiceResult.error("视频不存在")

            try:
                if (not str(getattr(video, "storage_path_relative", "") or "").strip()) or (not str(getattr(video, "storage_path_kind", "") or "").strip()):
                    if self._refresh_video_persisted_metadata(video, source="local"):
                        self._video_repo.save(video)
            except Exception as persisted_error:
                error_logger.error(f"回填视频存储路径失败（详情）: {video_id}, {persisted_error}")
            
            tags = self._tag_repo.get_all()
            tag_map = {t.id: t.name for t in tags}
            
            annotate_video_storage_usage([video], source="local")
            detail = video.to_dict()
            detail.update(self._storage_fields_from_item(video))
            local_episodes = self._discover_local_video_episodes(video)
            if local_episodes:
                display = dict(detail.get("display") or {})
                display["local_episodes"] = local_episodes
                detail["display"] = display
                detail["total_units"] = len(local_episodes)
            detail["tags"] = [{"id": tid, "name": tag_map.get(tid, tid)} for tid in video.tag_ids]
            detail["source"] = "local"
            detail["storage_path"] = self._resolve_video_storage_path(video)
            detail["local_thumbnail_capability"] = self._build_local_thumbnail_capability(video)
            detail = self._annotate_video_record(detail)
            
            app_logger.info(f"获取视频详情成功: {video_id}")
            return ServiceResult.ok(detail)
        except Exception as e:
            error_logger.error(f"获取视频详情失败: {e}")
            error_logger.error(traceback.format_exc())
            return ServiceResult.error("获取视频详情失败")

    @staticmethod
    def _normalize_local_cover_thumbnail_index(raw_index: Any, thumbnail_count: int = 0) -> int:
        try:
            normalized = int(raw_index)
        except Exception:
            normalized = -1

        if normalized < 0:
            return -1
        if thumbnail_count > 0 and normalized >= int(thumbnail_count):
            return -1
        return normalized

    def _build_local_thumbnail_capability(self, video: Optional[Video]) -> Dict[str, Any]:
        local_thumbnails = list(getattr(video, "thumbnail_images_local", []) or []) if isinstance(video, Video) else []
        generated_count = len([item for item in local_thumbnails if str(item or "").strip()])
        runtime_capability = probe_local_video_thumbnail_runtime()
        mobile_core_runtime = str(runtime_capability.get("runtime_profile") or "").strip().lower() == "mobile_core"
        has_local_source = self._has_video_source_file(video)
        show_generate_action = (not mobile_core_runtime) and has_local_source
        can_generate = bool(runtime_capability.get("supported")) and has_local_source
        can_select_cover = (generated_count > 0) and not mobile_core_runtime

        reason = ""
        if not runtime_capability.get("supported"):
            reason = str(runtime_capability.get("reason") or "").strip()
        elif not has_local_source:
            reason = "当前视频没有可用的本地源文件"

        return {
            "supported": bool(runtime_capability.get("supported")),
            "provider": str(runtime_capability.get("provider") or "").strip(),
            "platform": str(runtime_capability.get("platform") or "").strip(),
            "runtime_profile": str(runtime_capability.get("runtime_profile") or "").strip(),
            "has_local_source": has_local_source,
            "show_generate_action": show_generate_action,
            "can_generate": can_generate,
            "can_select_cover": can_select_cover,
            "generated_count": generated_count,
            "target_count": self.LOCAL_THUMBNAIL_TARGET_COUNT,
            "selected_index": self._normalize_local_cover_thumbnail_index(
                getattr(video, "local_cover_thumbnail_index", -1),
                generated_count,
            ),
            "reason": reason,
        }
    
    def _resolve_video_storage_path(self, video: Video) -> str:
        stored_relative = str(getattr(video, "storage_path_relative", "") or "").strip()
        if stored_relative:
            stored_abs = resolve_data_relative_path(stored_relative)
            if stored_abs and os.path.exists(stored_abs):
                return stored_abs

        source_path = str(getattr(video, "local_source_path", "") or "").strip()
        if source_path:
            if source_path.startswith(("http://", "https://")):
                return source_path
            if source_path.startswith("/media/"):
                resolved = self.resolve_local_video_file_path(video.id)
                return str(resolved or "")
            try:
                return os.path.abspath(os.path.expandvars(os.path.expanduser(source_path)))
            except Exception:
                return source_path

        resolved = self.resolve_local_video_file_path(video.id)
        return str(resolved or "")

    def _copy_thumbnail_file_to_cover(self, video_id: str, source_thumb_abs_path: str) -> Tuple[str, str]:
        cover_abs_path, cover_relative_path = self._build_preview_cover_save_paths(video_id, "local")
        cover_tmp_path = f"{cover_abs_path}.tmp"
        shutil.copy2(source_thumb_abs_path, cover_tmp_path)
        os.replace(cover_tmp_path, cover_abs_path)
        return cover_abs_path, cover_relative_path

    @staticmethod
    def _build_local_cover_asset_version() -> str:
        return str(int(time.time() * 1000))

    def generate_local_video_thumbnails(self, video_id: str) -> ServiceResult:
        try:
            normalized_video_id = str(video_id or "").strip()
            if not normalized_video_id:
                return ServiceResult.error("缺少 video_id")

            video = self._video_repo.get_by_id(normalized_video_id)
            if not video:
                return ServiceResult.error("视频不存在")

            capability = self._build_local_thumbnail_capability(video)
            if not bool(capability.get("can_generate")):
                reason = str(capability.get("reason") or "").strip() or "当前视频无法生成缩略图"
                return ServiceResult.error(reason)

            resolved_video_path = self.resolve_local_video_file_path(normalized_video_id)
            if not resolved_video_path or not os.path.isfile(resolved_video_path):
                return ServiceResult.error("未找到可用的本地视频文件")

            asset_dir, relative_dir = self._build_preview_asset_dir(normalized_video_id, "local")
            temp_root = tempfile.mkdtemp(prefix="thumbs-build-", dir=asset_dir)
            temp_thumbs_dir = os.path.join(temp_root, "thumbs")
            os.makedirs(temp_thumbs_dir, exist_ok=True)

            try:
                generator = FFmpegLocalVideoThumbnailService(
                    ffmpeg_path=str(probe_local_video_thumbnail_runtime().get("ffmpeg_path") or "").strip()
                )
                generation_result = generator.generate_thumbnails(
                    video_path=resolved_video_path,
                    output_dir=temp_thumbs_dir,
                    count=self.LOCAL_THUMBNAIL_TARGET_COUNT,
                    width=self.LOCAL_THUMBNAIL_WIDTH,
                )

                final_thumbs_dir = os.path.join(asset_dir, "thumbs")
                if os.path.isdir(final_thumbs_dir):
                    shutil.rmtree(final_thumbs_dir, ignore_errors=True)
                shutil.move(temp_thumbs_dir, final_thumbs_dir)

                thumbnail_urls = [
                    f"{relative_dir}/thumbs/thumb-{index:04d}.jpg"
                    for index in range(1, int(generation_result.get("thumbnail_count") or 0) + 1)
                ]
                if not thumbnail_urls:
                    return ServiceResult.error("未生成任何缩略图")

                default_cover_index = self._normalize_local_cover_thumbnail_index(
                    generation_result.get("default_cover_index", -1),
                    len(thumbnail_urls),
                )
                if default_cover_index < 0:
                    default_cover_index = 0

                default_cover_url = thumbnail_urls[default_cover_index]
                default_cover_abs = self._resolve_static_asset_abs_path(default_cover_url)
                if not default_cover_abs or not os.path.isfile(default_cover_abs):
                    return ServiceResult.error("生成的缩略图文件不可用")

                _cover_abs, cover_relative_path = self._copy_thumbnail_file_to_cover(
                    normalized_video_id,
                    default_cover_abs,
                )

                video.thumbnail_images_local = thumbnail_urls
                video.cover_path_local = cover_relative_path
                video.local_cover_thumbnail_index = default_cover_index
                video.local_cover_asset_version = self._build_local_cover_asset_version()

                if not self._video_repo.save(video):
                    return ServiceResult.error("回写缩略图信息失败")

                detail_result = self.get_video_detail(normalized_video_id)
                if not detail_result.success:
                    return detail_result
                return ServiceResult.ok(detail_result.data, "缩略图生成成功")
            finally:
                shutil.rmtree(temp_root, ignore_errors=True)
        except Exception as e:
            error_logger.error(f"generate local video thumbnails failed: id={video_id}, error={e}")
            return ServiceResult.error("生成缩略图失败")

    def select_local_thumbnail_as_cover(self, video_id: str, thumbnail_index: int) -> ServiceResult:
        try:
            normalized_video_id = str(video_id or "").strip()
            if not normalized_video_id:
                return ServiceResult.error("缺少 video_id")

            video = self._video_repo.get_by_id(normalized_video_id)
            if not video:
                return ServiceResult.error("视频不存在")

            thumbnails = [
                str(item or "").strip()
                for item in list(getattr(video, "thumbnail_images_local", []) or [])
                if str(item or "").strip()
            ]
            if not thumbnails:
                return ServiceResult.error("当前视频还没有可用的本地缩略图")

            selected_index = self._normalize_local_cover_thumbnail_index(thumbnail_index, len(thumbnails))
            if selected_index < 0:
                return ServiceResult.error("缩略图索引无效")

            selected_thumb_url = thumbnails[selected_index]
            selected_thumb_abs = self._resolve_static_asset_abs_path(selected_thumb_url)
            if not selected_thumb_abs or not os.path.isfile(selected_thumb_abs):
                return ServiceResult.error("目标缩略图文件不存在")

            _cover_abs, cover_relative_path = self._copy_thumbnail_file_to_cover(
                normalized_video_id,
                selected_thumb_abs,
            )
            video.cover_path_local = cover_relative_path
            video.local_cover_thumbnail_index = selected_index
            video.local_cover_asset_version = self._build_local_cover_asset_version()

            if not self._video_repo.save(video):
                return ServiceResult.error("回写封面失败")

            detail_result = self.get_video_detail(normalized_video_id)
            if not detail_result.success:
                return detail_result
            return ServiceResult.ok(detail_result.data, "封面已更新")
        except Exception as e:
            error_logger.error(f"select local thumbnail as cover failed: id={video_id}, error={e}")
            return ServiceResult.error("设置封面失败")

    def get_video_by_code(self, code: str) -> ServiceResult:
        try:
            video = self._video_repo.get_by_code(code)
            if not video:
                return ServiceResult.error("视频不存在")
            return ServiceResult.ok(self._annotate_video_record(video.to_dict()))
        except Exception as e:
            error_logger.error(f"根据番号获取视频失败: {e}")
            return ServiceResult.error("获取视频失败")
    
    def search_videos(self, keyword: str) -> ServiceResult:
        try:
            videos = self._video_repo.search(keyword)
            tags = self._tag_repo.get_all()
            tag_map = {t.id: t.name for t in tags}
            
            videos = [v for v in videos if not v.is_deleted]
            
            results = []
            for v in videos:
                video_info = v.to_dict()
                video_info["tags"] = [{"id": tid, "name": tag_map.get(tid, tid)} for tid in v.tag_ids]
                results.append(video_info)
            results = self._annotate_video_records(results)
            
            app_logger.info(f"搜索成功: 关键词'{keyword}', 结果数量: {len(results)}")
            return ServiceResult.ok(results)
        except Exception as e:
            error_logger.error(f"搜索失败: {e}")
            return ServiceResult.error("搜索失败")
    
    def update_video_score(self, video_id: str, score: float) -> ServiceResult:
        return self._update_score_impl(self._video_repo, video_id, score)
    
    def update_video_progress(self, video_id: str, unit: int) -> ServiceResult:
        return self._update_progress_impl(self._video_repo, video_id, unit)
    
    def move_to_trash(self, video_id: str) -> ServiceResult:
        return self._move_to_trash_impl(self._video_repo, video_id)
    
    def restore_from_trash(self, video_id: str) -> ServiceResult:
        return self._restore_from_trash_impl(self._video_repo, video_id)
    
    def delete_permanently(self, video_id: str) -> ServiceResult:
        try:
            video = self._video_repo.get_by_id(video_id)
            if not video:
                return ServiceResult.error("视频不存在")
            
            self._cleanup_video_files(video)
            
            success = self._video_repo.delete(video_id)
            if success:
                app_logger.info(f"视频已永久删除: {video_id}")
                return ServiceResult.ok({"message": "视频已永久删除"})
            return ServiceResult.error("删除失败")
        except Exception as e:
            error_logger.error(f"永久删除视频失败: {e}")
            return ServiceResult.error("删除失败")

    def _get_video_storage_dirs(self, video_id: str) -> List[str]:
        safe_video_id = self._sanitize_video_asset_id(video_id)
        platform_dir = os.path.join(VIDEO_DIR, self._get_video_platform_key(video_id), safe_video_id)
        return [platform_dir]
    
    def _cleanup_video_files(self, video):
        """清理视频相关的本地文件"""
        from core.constants import COVER_DIR
        
        if video.cover_path:
            relative_path = video.cover_path.lstrip('/')
            if relative_path.startswith('static/cover/'):
                relative_path = relative_path.replace('static/cover/', '', 1)
            
            cover_path_full = os.path.join(COVER_DIR, relative_path)
            if os.path.exists(cover_path_full):
                try:
                    os.remove(cover_path_full)
                    app_logger.info(f"已删除视频封面: {cover_path_full}")
                except Exception as e:
                    error_logger.error(f"删除视频封面失败: {e}")
        
        candidate_dirs = []
        resolved_local_dir = self._resolve_video_local_asset_dir(video)
        if resolved_local_dir:
            candidate_dirs.append(resolved_local_dir)
        for video_dir in self._get_video_storage_dirs(video.id):
            if video_dir not in candidate_dirs:
                candidate_dirs.append(video_dir)

        for video_dir in candidate_dirs:
            if not os.path.exists(video_dir):
                continue
            try:
                shutil.rmtree(video_dir)
                app_logger.info(f"已删除视频目录: {video_dir}")
            except Exception as e:
                error_logger.error(f"删除视频目录失败: {e}")

        self._remove_preview_video_file(getattr(video, "cover_path", ""))
        self._remove_preview_video_file(getattr(video, "preview_video", ""))
        for thumb_url in getattr(video, "thumbnail_images", []) or []:
            self._remove_preview_video_file(thumb_url)
        self._remove_preview_video_file(getattr(video, "cover_path_local", ""))
        self._remove_preview_video_file(getattr(video, "preview_video_local", ""))
        self._remove_preview_video_file(getattr(video, "local_video_path", ""))
        for thumb_url in getattr(video, "thumbnail_images_local", []) or []:
            self._remove_preview_video_file(thumb_url)
    
    def delete_recommendation_assets(
        self,
        video_id: str,
        preview_video: str = "",
        preview_video_local: str = "",
        cover_path: str = "",
        cover_path_local: str = "",
        thumbnail_images: Optional[List[str]] = None,
        thumbnail_images_local: Optional[List[str]] = None,
    ):
        for video_dir in self._get_video_storage_dirs(video_id):
            if not os.path.exists(video_dir):
                continue
            try:
                shutil.rmtree(video_dir)
            except Exception as e:
                error_logger.error(f"删除推荐视频目录失败: {e}")

        if preview_video:
            self._remove_preview_video_file(preview_video)
        if preview_video_local:
            self._remove_preview_video_file(preview_video_local)
        if cover_path:
            self._remove_preview_video_file(cover_path)
        if cover_path_local:
            self._remove_preview_video_file(cover_path_local)
        for thumb_url in thumbnail_images or []:
            self._remove_preview_video_file(thumb_url)
        for thumb_url in thumbnail_images_local or []:
            self._remove_preview_video_file(thumb_url)
    
    @staticmethod
    def _is_local_video_id(video_id: str) -> bool:
        return str(video_id or "").strip().upper().startswith("LOCAL")

    @classmethod
    def _is_video_file_path(cls, file_path: str) -> bool:
        ext = os.path.splitext(str(file_path or ""))[1].lower()
        return ext in cls.VIDEO_FILE_EXTENSIONS

    @classmethod
    def _is_archive_file_path(cls, file_path: str) -> bool:
        ext = os.path.splitext(str(file_path or ""))[1].lower()
        return ext in cls.ARCHIVE_FILE_EXTENSIONS

    @staticmethod
    def _to_media_url(abs_path: str) -> str:
        target_path = os.path.abspath(str(abs_path or ""))
        data_root = os.path.abspath(DATA_DIR)
        try:
            if os.path.commonpath([data_root, target_path]) != data_root:
                return ""
        except Exception:
            return ""

        relative = os.path.relpath(target_path, data_root).replace("\\", "/").lstrip("/")
        return f"/media/{relative}" if relative else ""

    @staticmethod
    def _sanitize_local_fs_name(name: str, fallback: str = "video") -> str:
        normalized = re.sub(r'[\\/:*?"<>|\x00-\x1F]+', "_", str(name or "").strip())
        normalized = re.sub(r"\s+", " ", normalized).rstrip(" .")
        if not normalized:
            normalized = fallback

        reserved = {
            "CON", "PRN", "AUX", "NUL",
            "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
            "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9",
        }
        if normalized.upper() in reserved:
            normalized = f"{normalized}_"
        return normalized[:180]

    @staticmethod
    def _make_unique_dir_path(path: str) -> str:
        candidate = os.path.abspath(str(path or ""))
        if not os.path.exists(candidate):
            return candidate

        parent = os.path.dirname(candidate)
        name = os.path.basename(candidate)
        for index in range(2, 10_000):
            next_candidate = os.path.join(parent, f"{name}__{index}")
            if not os.path.exists(next_candidate):
                return next_candidate
        raise RuntimeError(f"failed to allocate storage dir: {candidate}")

    @staticmethod
    def _media_url_to_abs_path(media_url: str) -> str:
        url = str(media_url or "").strip()
        if not url.startswith("/media/"):
            return ""

        relative = url[len("/media/"):].lstrip("/").replace("/", os.sep)
        candidate = os.path.abspath(os.path.join(DATA_DIR, relative))
        data_root = os.path.abspath(DATA_DIR)
        try:
            if os.path.commonpath([data_root, candidate]) != data_root:
                return ""
        except Exception:
            return ""
        return candidate

    @staticmethod
    def _extract_local_asset_root(abs_path: str) -> str:
        raw_path = str(abs_path or "").strip()
        if not raw_path:
            return ""

        candidate = os.path.abspath(raw_path)
        video_root = os.path.abspath(VIDEO_DIR)
        try:
            if os.path.commonpath([video_root, candidate]) != video_root:
                return ""
        except Exception:
            return ""

        relative = os.path.relpath(candidate, video_root)
        parts = [part for part in relative.split(os.sep) if part not in {"", "."}]
        if len(parts) < 2:
            return ""
        return os.path.join(video_root, parts[0], parts[1])

    def _resolve_explicit_video_local_asset_dir(self, video: Optional[Video]) -> str:
        if not isinstance(video, Video):
            return ""

        candidates = []

        stored_relative = str(getattr(video, "storage_path_relative", "") or "").strip()
        if stored_relative:
            stored_abs = resolve_data_relative_path(stored_relative)
            if stored_abs:
                if os.path.isfile(stored_abs):
                    candidates.append(os.path.dirname(stored_abs))
                else:
                    candidates.append(stored_abs)

        stored_dir_name = str(getattr(video, "local_asset_dir_name", "") or "").strip()
        if stored_dir_name:
            candidates.append(stored_dir_name)

        local_video_abs = self._media_url_to_abs_path(getattr(video, "local_video_path", ""))
        if local_video_abs:
            candidates.append(self._extract_local_asset_root(local_video_abs))

        source_abs = str(getattr(video, "local_source_path", "") or "").strip()
        if source_abs:
            candidates.append(self._extract_local_asset_root(source_abs))

        media_urls = [
            getattr(video, "cover_path_local", ""),
            getattr(video, "preview_video_local", ""),
        ]
        media_urls.extend(list(getattr(video, "thumbnail_images_local", []) or []))
        for media_url in media_urls:
            abs_path = self._media_url_to_abs_path(media_url)
            if abs_path:
                candidates.append(self._extract_local_asset_root(abs_path))

        seen = set()
        for candidate in candidates:
            normalized = str(candidate or "").strip()
            if not normalized:
                continue
            lowered = os.path.normcase(normalized)
            if lowered in seen:
                continue
            seen.add(lowered)
            if os.path.isabs(normalized):
                return normalized
            return normalized
        return ""

    def _resolve_video_local_asset_dir(self, video: Optional[Video]) -> str:
        if not isinstance(video, Video):
            return ""

        explicit_dir = self._resolve_explicit_video_local_asset_dir(video)
        platform_key = self._get_video_platform_key(video.id)
        platform_manifest = self._resolve_video_protocol_context(video_id=video.id).get("manifest")
        platform_root = build_platform_root_dir(VIDEO_DIR, manifest=platform_manifest, platform_name=platform_key)

        if explicit_dir:
            if os.path.isabs(explicit_dir):
                return explicit_dir
            return os.path.join(platform_root, explicit_dir)

        return os.path.join(platform_root, self._sanitize_video_asset_id(video.id))

    def _resolve_video_source_filename(self, video: Optional[Video], default_extension: str = "") -> str:
        if isinstance(video, Video):
            stored_name = str(getattr(video, "local_source_filename", "") or "").strip()
            if stored_name:
                return stored_name

            local_video_abs = self._media_url_to_abs_path(getattr(video, "local_video_path", ""))
            if local_video_abs:
                filename = os.path.basename(local_video_abs)
                if filename:
                    return filename

            local_source_path = str(getattr(video, "local_source_path", "") or "").strip()
            if local_source_path:
                filename = os.path.basename(local_source_path)
                if filename:
                    return filename

        normalized_ext = str(default_extension or "").strip().lower() or ".mp4"
        return f"{self.LOCAL_VIDEO_FILENAME}{normalized_ext}"

    def _generate_local_video_id(self) -> str:
        return f"{self.LOCAL_VIDEO_ID_PREFIX}_{generate_uuid()[:12]}"

    def _generate_abnormal_code(self) -> str:
        while True:
            candidate = f"{self.ABNORMAL_CODE_PREFIX}{generate_uuid()[:10].upper()}"
            if self._find_local_video_duplicate("", candidate):
                continue
            return candidate

    @classmethod
    def normalize_local_import_mode(cls, raw_mode: str) -> str:
        mode = str(raw_mode or "").strip().lower()
        if mode in {"softlink_ref", "soft_ref", "softlink", "soft"}:
            return cls.LOCAL_IMPORT_MODE_SOFTLINK_REF
        if mode in {"hardlink_move", "move_huge", "move", "hardlink"}:
            return cls.LOCAL_IMPORT_MODE_HARDLINK_MOVE
        return cls.LOCAL_IMPORT_MODE_HARDLINK_MOVE

    @classmethod
    def normalize_local_import_grouping_mode(cls, raw_mode: str) -> str:
        mode = str(raw_mode or "").strip().lower()
        if mode in {"leaf_dir", "leaf", "dir", "directory", "folder"}:
            return cls.LOCAL_IMPORT_GROUPING_LEAF_DIR
        return cls.LOCAL_IMPORT_GROUPING_PER_FILE

    @staticmethod
    def _normalize_local_path_key(path: str) -> str:
        raw = str(path or "").strip()
        if not raw:
            return ""
        try:
            normalized = os.path.abspath(os.path.expandvars(os.path.expanduser(raw)))
        except Exception:
            normalized = raw
        return os.path.normcase(normalized)

    @staticmethod
    def _build_local_stream_url(video_id: str) -> str:
        safe_id = str(video_id or "").strip()
        return f"/api/v1/video/local-stream/{safe_id}" if safe_id else ""

    @staticmethod
    def _natural_filename_key(value: str) -> List[Any]:
        return [
            int(part) if part.isdigit() else part.lower()
            for part in re.split(r"(\d+)", str(value or ""))
        ]

    @classmethod
    def _build_local_episode_stream_url(cls, video_id: str, episode_index: int = 0) -> str:
        base_url = cls._build_local_stream_url(video_id)
        if not base_url or int(episode_index or 0) <= 0:
            return base_url
        return f"{base_url}?episode={int(episode_index)}"

    def _build_local_episode_entry(
        self,
        video_id: str,
        abs_path: str,
        *,
        base_dir: str = "",
        index: int = 1,
        include_source_path: bool = True,
    ) -> Dict[str, Any]:
        normalized_path = os.path.abspath(str(abs_path or ""))
        base_path = os.path.abspath(str(base_dir or os.path.dirname(normalized_path)))
        filename = os.path.basename(normalized_path)
        try:
            relative_path = os.path.relpath(normalized_path, base_path).replace("\\", "/")
        except Exception:
            relative_path = filename

        media_url = self._to_media_url(normalized_path)
        url = media_url or self._build_local_episode_stream_url(video_id, index)
        entry = {
            "name": filename,
            "relative_path": relative_path,
            "url": url,
            "index": int(index or 1),
        }
        if include_source_path:
            entry["source_path"] = normalized_path
        return entry

    def _extract_local_episode_path(self, video: Video, episode: Dict[str, Any]) -> str:
        if not isinstance(episode, dict):
            return ""

        source_path = str(episode.get("source_path") or "").strip()
        if source_path:
            candidate = os.path.abspath(os.path.expandvars(os.path.expanduser(source_path)))
            if os.path.isfile(candidate):
                return candidate

        url_path = self._media_url_to_abs_path(str(episode.get("url") or "").strip())
        if url_path and os.path.isfile(url_path):
            return url_path

        relative_path = str(episode.get("relative_path") or "").strip()
        if relative_path:
            base_dir = self._resolve_video_local_asset_dir(video)
            if base_dir:
                candidate = os.path.abspath(os.path.join(base_dir, relative_path.replace("/", os.sep)))
                try:
                    if os.path.commonpath([os.path.abspath(base_dir), candidate]) == os.path.abspath(base_dir) and os.path.isfile(candidate):
                        return candidate
                except Exception:
                    pass

        return ""

    def _get_local_episode_entries(self, video: Optional[Video]) -> List[Dict[str, Any]]:
        if not isinstance(video, Video):
            return []

        display = getattr(video, "display", {}) if video else {}
        existing = display.get("local_episodes") if isinstance(display, dict) else []
        if isinstance(existing, list) and existing:
            normalized_entries = []
            for index, episode in enumerate(existing, start=1):
                if not isinstance(episode, dict):
                    continue
                entry = dict(episode)
                entry["index"] = index
                entry["name"] = str(
                    entry.get("name")
                    or entry.get("relative_path")
                    or entry.get("title")
                    or f"第 {index} 集"
                ).strip() or f"第 {index} 集"
                normalized_entries.append(entry)
            if normalized_entries:
                return normalized_entries

        return [
            dict(item)
            for item in (self._discover_local_video_episodes(video) or [])
            if isinstance(item, dict)
        ]

    def _get_episode_entry_path(self, video: Optional[Video], episode: Dict[str, Any]) -> str:
        if not isinstance(episode, dict):
            return ""

        source_path = str(episode.get("source_path") or "").strip()
        if source_path:
            expanded = os.path.abspath(os.path.expandvars(os.path.expanduser(source_path)))
            if expanded:
                return expanded

        if isinstance(video, Video):
            resolved = self._extract_local_episode_path(video, episode)
            if resolved:
                return resolved

        media_path = self._media_url_to_abs_path(str(episode.get("url") or "").strip())
        if media_path:
            return media_path
        return ""

    def _collect_existing_local_episode_path_keys(self, video: Optional[Video]) -> set[str]:
        if not isinstance(video, Video):
            return set()

        path_keys = set()
        for episode in self._get_local_episode_entries(video):
            normalized = self._normalize_local_path_key(self._get_episode_entry_path(video, episode))
            if normalized:
                path_keys.add(normalized)

        local_source_path = self._normalize_local_path_key(getattr(video, "local_source_path", ""))
        if local_source_path:
            path_keys.add(local_source_path)
        return path_keys

    def _merge_local_episode_entries(
        self,
        existing_entries: List[Dict[str, Any]],
        new_entries: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        merged_entries = []
        for index, episode in enumerate([*(existing_entries or []), *(new_entries or [])], start=1):
            if not isinstance(episode, dict):
                continue
            entry = dict(episode)
            entry["index"] = index
            entry["name"] = str(
                entry.get("name")
                or entry.get("relative_path")
                or entry.get("title")
                or f"第 {index} 集"
            ).strip() or f"第 {index} 集"
            merged_entries.append(entry)
        return merged_entries

    def _resolve_import_episode_storage(
        self,
        episode_entries: List[Dict[str, Any]],
        *,
        preferred_dir: str = "",
    ) -> Dict[str, str]:
        episode_paths = [
            self._get_episode_entry_path(None, episode)
            for episode in (episode_entries or [])
            if isinstance(episode, dict)
        ]
        episode_paths = [path for path in episode_paths if path]
        if not episode_paths:
            return {
                "local_video_path": "",
                "local_source_path": "",
                "local_source_filename": "",
                "local_asset_dir_name": "",
                "storage_path_relative": "",
                "storage_path_kind": "source",
            }

        first_entry = episode_entries[0]
        canonical_path = episode_paths[0]
        storage_reference = canonical_path
        storage_kind = "local_file" if normalize_data_relative_path(canonical_path) else "source"

        normalized_preferred_dir = str(preferred_dir or "").strip()
        if normalized_preferred_dir:
            storage_reference = normalized_preferred_dir
            storage_kind = "local_dir" if normalize_data_relative_path(normalized_preferred_dir) else "source"
        else:
            unique_dirs = {
                os.path.dirname(path)
                for path in episode_paths
            }
            if len(episode_paths) > 1 and len(unique_dirs) == 1:
                only_dir = next(iter(unique_dirs))
                storage_reference = only_dir
                storage_kind = "local_dir" if normalize_data_relative_path(only_dir) else "source"

        local_asset_dir_name = ""
        asset_root = self._extract_local_asset_root(canonical_path)
        if asset_root:
            local_asset_dir_name = os.path.basename(asset_root)
        else:
            local_asset_dir_name = os.path.basename(os.path.dirname(canonical_path))

        return {
            "local_video_path": str(first_entry.get("url") or "").strip(),
            "local_source_path": canonical_path,
            "local_source_filename": os.path.basename(canonical_path),
            "local_asset_dir_name": local_asset_dir_name,
            "storage_path_relative": normalize_data_relative_path(storage_reference),
            "storage_path_kind": storage_kind,
        }

    def _build_video_import_units(
        self,
        source_dir: str,
        *,
        grouping_mode: str,
    ) -> Dict[str, Any]:
        scanned_files = 0
        scanned_video_files = 0
        skipped_count = 0
        skipped_items: List[Dict[str, str]] = []
        units: List[Dict[str, Any]] = []

        for root, _dirs, files in os.walk(source_dir):
            root_abs = os.path.abspath(root)
            sorted_files = sorted(files, key=self._natural_filename_key)
            video_files: List[str] = []

            for filename in sorted_files:
                scanned_files += 1
                abs_file_path = os.path.join(root_abs, filename)
                if self._is_archive_file_path(filename):
                    skipped_count += 1
                    skipped_items.append({"file": abs_file_path, "reason": "archive_ignored"})
                    continue
                if not self._is_video_file_path(filename):
                    continue
                scanned_video_files += 1
                video_files.append(filename)

            if not video_files:
                continue

            if grouping_mode == self.LOCAL_IMPORT_GROUPING_LEAF_DIR:
                recognized_buckets: Dict[str, Dict[str, Any]] = {}
                unrecognized_files: List[str] = []
                for filename in video_files:
                    stem, _ext = os.path.splitext(filename)
                    extracted_code = self.extract_code_from_filename(stem)
                    if extracted_code:
                        bucket_key = self._normalize_code_for_compare(extracted_code)
                        bucket = recognized_buckets.setdefault(
                            bucket_key,
                            {"code_hint": extracted_code, "filenames": []},
                        )
                        bucket["filenames"].append(filename)
                    else:
                        unrecognized_files.append(filename)

                if recognized_buckets:
                    for bucket in recognized_buckets.values():
                        grouped_filenames = sorted(bucket["filenames"], key=self._natural_filename_key)
                        first_stem = os.path.splitext(grouped_filenames[0])[0].strip()
                        units.append(
                            {
                                "root": root_abs,
                                "filenames": grouped_filenames,
                                "title_hint": first_stem or (bucket.get("code_hint") or "本地视频"),
                                "code_hint": str(bucket.get("code_hint") or "").strip(),
                            }
                        )
                    if unrecognized_files:
                        units.append(
                            {
                                "root": root_abs,
                                "filenames": sorted(unrecognized_files, key=self._natural_filename_key),
                                "title_hint": os.path.basename(root_abs) or "本地视频合集",
                                "code_hint": "",
                            }
                        )
                    continue

                units.append(
                    {
                        "root": root_abs,
                        "filenames": video_files,
                        "title_hint": os.path.basename(root_abs) or "本地视频合集",
                        "code_hint": "",
                    }
                )
                continue

            for filename in video_files:
                stem, _ext = os.path.splitext(filename)
                units.append(
                    {
                        "root": root_abs,
                        "filenames": [filename],
                        "title_hint": stem.strip() or filename,
                        "code_hint": self.extract_code_from_filename(stem),
                    }
                )

        return {
            "scanned_files": scanned_files,
            "scanned_video_files": scanned_video_files,
            "skipped_count": skipped_count,
            "skipped_items": skipped_items,
            "units": units,
        }

    def _discover_local_video_episodes(self, video: Optional[Video]) -> List[Dict[str, Any]]:
        if not isinstance(video, Video):
            return []

        candidate_files: List[str] = []
        seen_files = set()
        candidate_dirs: List[str] = []
        seen_dirs = set()

        def add_file(path: str) -> None:
            normalized = os.path.abspath(os.path.expandvars(os.path.expanduser(str(path or "").strip())))
            if not normalized or not os.path.isfile(normalized) or not self._is_video_file_path(normalized):
                return
            key = os.path.normcase(normalized)
            if key in seen_files:
                return
            seen_files.add(key)
            candidate_files.append(normalized)

        def add_dir(path: str) -> None:
            normalized = os.path.abspath(os.path.expandvars(os.path.expanduser(str(path or "").strip())))
            if not normalized or not os.path.isdir(normalized):
                return
            key = os.path.normcase(normalized)
            if key in seen_dirs:
                return
            seen_dirs.add(key)
            candidate_dirs.append(normalized)

        display = getattr(video, "display", {}) if video else {}
        existing_episodes = display.get("local_episodes") if isinstance(display, dict) else []
        if isinstance(existing_episodes, list):
            for episode in existing_episodes:
                episode_path = self._extract_local_episode_path(video, episode)
                add_file(episode_path)
                if episode_path:
                    add_dir(os.path.dirname(episode_path))
            if candidate_files:
                reference_dir = os.path.dirname(candidate_files[0])

                def sort_key(item: str) -> List[Any]:
                    try:
                        sortable = os.path.relpath(item, reference_dir)
                    except Exception:
                        sortable = os.path.basename(item)
                    return self._natural_filename_key(sortable)

                candidate_files.sort(key=sort_key)
                base_dir = reference_dir
                return [
                    self._build_local_episode_entry(video.id, path, base_dir=base_dir, index=index)
                    for index, path in enumerate(candidate_files, start=1)
                ]

        resolved_primary = self.resolve_local_video_file_path(video.id)
        if resolved_primary:
            add_file(resolved_primary)

        stored_relative = str(getattr(video, "storage_path_relative", "") or "").strip()
        storage_kind = str(getattr(video, "storage_path_kind", "") or "").strip().lower()
        if stored_relative:
            stored_abs = resolve_data_relative_path(stored_relative)
            if stored_abs:
                if os.path.isfile(stored_abs):
                    add_file(stored_abs)
                elif os.path.isdir(stored_abs) and storage_kind == "local_dir":
                    add_dir(stored_abs)

        if candidate_dirs and resolved_primary:
            add_dir(os.path.dirname(resolved_primary))

        for base_dir in candidate_dirs:
            if not os.path.isdir(base_dir):
                continue
            for root, _, files in os.walk(base_dir):
                for filename in files:
                    if self._is_video_file_path(filename):
                        add_file(os.path.join(root, filename))

        if not candidate_files:
            return []

        reference_dir = os.path.dirname(candidate_files[0])

        def sort_key(item: str) -> List[Any]:
            try:
                sortable = os.path.relpath(item, reference_dir)
            except Exception:
                sortable = os.path.basename(item)
            return self._natural_filename_key(sortable)

        candidate_files.sort(key=sort_key)

        base_dir = ""
        if len(candidate_files) == 1:
            base_dir = os.path.dirname(candidate_files[0])
        else:
            drives = {
                os.path.splitdrive(os.path.abspath(path))[0].lower()
                for path in candidate_files
            }
            if len(drives) == 1:
                try:
                    base_dir = os.path.commonpath(candidate_files)
                except Exception:
                    base_dir = ""
                if base_dir and os.path.isfile(base_dir):
                    base_dir = os.path.dirname(base_dir)
        if not base_dir:
            base_dir = os.path.dirname(candidate_files[0])

        return [
            self._build_local_episode_entry(video.id, path, base_dir=base_dir, index=index)
            for index, path in enumerate(candidate_files, start=1)
        ]

    @classmethod
    def extract_code_from_filename(cls, filename_without_ext: str) -> str:
        raw_name = str(filename_without_ext or "").strip()
        if not raw_name:
            return ""

        fc2_match = cls.FC2_PATTERN.search(raw_name)
        if fc2_match:
            number = str(fc2_match.group(2) or "").strip()
            if number:
                return f"FC2-PPV-{number}"

        normal_match = cls.CODE_PATTERN.search(raw_name)
        if not normal_match:
            return ""

        prefix = str(normal_match.group(1) or "").upper()
        number = str(normal_match.group(2) or "").strip()
        if not prefix or not number:
            return ""
        if prefix in cls.GENERIC_CODE_PREFIXES:
            return ""
        return f"{prefix}-{number}"

    def _extract_or_generate_code(self, filename_without_ext: str) -> str:
        extracted = self.extract_code_from_filename(filename_without_ext)
        return extracted or self._generate_abnormal_code()

    @classmethod
    def _normalize_code_for_storage(cls, code: str) -> str:
        raw = str(code or "").strip()
        if not raw:
            return ""

        extracted = cls.extract_code_from_filename(raw)
        if extracted and cls._normalize_code_for_compare(extracted) == cls._normalize_code_for_compare(raw):
            return extracted
        return raw

    def _build_local_source_file_target(
        self,
        video_id: str,
        original_filename: str,
        preferred_dir_name: str = "",
    ) -> Tuple[str, str, str, str]:
        original_name = os.path.basename(str(original_filename or "").strip())
        stem, ext = os.path.splitext(original_name)
        normalized_ext = str(ext or "").strip().lower() or ".mp4"
        platform_dir = self._get_video_platform_key(video_id)
        platform_manifest = self._resolve_video_protocol_context(video_id=video_id).get("manifest")
        platform_root = build_platform_root_dir(VIDEO_DIR, manifest=platform_manifest, platform_name=platform_dir)
        safe_video_id = self._sanitize_video_asset_id(video_id)
        fallback_base = safe_video_id or "video"

        source_filename = self._sanitize_local_fs_name(
            original_name or f"{fallback_base}{normalized_ext}",
            fallback=f"{fallback_base}{normalized_ext}",
        )
        if not os.path.splitext(source_filename)[1]:
            source_filename = f"{source_filename}{normalized_ext}"

        if preferred_dir_name:
            storage_dir_name = self._sanitize_local_fs_name(preferred_dir_name, fallback=fallback_base)
            target_dir = os.path.join(platform_root, storage_dir_name)
        else:
            desired_dir_name = self._sanitize_local_fs_name(stem or fallback_base, fallback=fallback_base)
            target_dir = self._make_unique_dir_path(os.path.join(platform_root, desired_dir_name))
            storage_dir_name = os.path.basename(target_dir)

        os.makedirs(target_dir, exist_ok=True)
        target_file = os.path.join(target_dir, source_filename)
        return target_dir, target_file, storage_dir_name, source_filename

    def _has_video_source_file(self, video: Optional[Video]) -> bool:
        if not isinstance(video, Video):
            return False
        resolved = self.resolve_local_video_file_path(video.id)
        return bool(resolved and os.path.isfile(resolved))

    def _make_unique_file_path(self, target_path: str) -> str:
        candidate = os.path.abspath(str(target_path or ""))
        if not os.path.exists(candidate):
            return candidate

        stem, ext = os.path.splitext(candidate)
        for index in range(2, 10_000):
            next_candidate = f"{stem}__{index}{ext}"
            if not os.path.exists(next_candidate):
                return next_candidate
        raise RuntimeError(f"failed to allocate local video file path: {candidate}")

    def _import_local_video_group(
        self,
        root: str,
        filenames: List[str],
        *,
        normalized_mode: str,
        title_hint: str = "",
        code_hint: str = "",
        local_video_cache: Optional[Dict[str, Dict[str, Video]]] = None,
    ) -> Dict[str, Any]:
        sorted_filenames = sorted(
            [str(filename or "").strip() for filename in (filenames or []) if str(filename or "").strip()],
            key=self._natural_filename_key,
        )
        if not sorted_filenames:
            return {"status": "skipped", "reason": "empty_group", "duplicate_files": []}

        normalized_root = os.path.abspath(root)
        fallback_title = title_hint or os.path.splitext(sorted_filenames[0])[0].strip() or os.path.basename(normalized_root) or "本地视频"
        normalized_code_hint = self._normalize_code_for_storage(code_hint)
        code = normalized_code_hint or self._extract_or_generate_code(fallback_title)
        bind_existing_video = None
        if not str(code or "").startswith(self.ABNORMAL_CODE_PREFIX):
            bind_existing_video = self._find_local_video_duplicate_entity("", code, local_video_cache=local_video_cache)

        video_id = str(getattr(bind_existing_video, "id", "") or "").strip() or self._generate_local_video_id()
        existing_entries = self._get_local_episode_entries(bind_existing_video)
        existing_path_keys = self._collect_existing_local_episode_path_keys(bind_existing_video)
        moved_pairs: List[Tuple[str, str]] = []
        duplicate_files: List[str] = []
        target_dir = ""
        local_asset_dir_name = str(getattr(bind_existing_video, "local_asset_dir_name", "") or "").strip() if bind_existing_video else ""
        local_source_filename = ""
        new_entries: List[Dict[str, Any]] = []

        try:
            if normalized_mode == self.LOCAL_IMPORT_MODE_HARDLINK_MOVE:
                preferred_dir_name = local_asset_dir_name
                if bind_existing_video and not preferred_dir_name:
                    existing_asset_dir = self._resolve_explicit_video_local_asset_dir(bind_existing_video)
                    if existing_asset_dir:
                        preferred_dir_name = os.path.basename(existing_asset_dir)

                target_dir, first_target, local_asset_dir_name, local_source_filename = self._build_local_source_file_target(
                    video_id,
                    sorted_filenames[0],
                    preferred_dir_name=preferred_dir_name,
                )
            else:
                local_source_filename = sorted_filenames[0]

            for filename in sorted_filenames:
                source_file = os.path.abspath(os.path.join(normalized_root, filename))
                source_key = self._normalize_local_path_key(source_file)
                if source_key and source_key in existing_path_keys:
                    duplicate_files.append(source_file)
                    continue

                next_index = len(existing_entries) + len(new_entries) + 1
                if normalized_mode == self.LOCAL_IMPORT_MODE_HARDLINK_MOVE:
                    target_name = (
                        os.path.basename(first_target)
                        if not new_entries
                        else self._sanitize_local_fs_name(os.path.basename(filename), fallback=f"episode-{next_index:03d}.mp4")
                    )
                    target_file = self._make_unique_file_path(os.path.join(target_dir, target_name))
                    shutil.move(source_file, target_file)
                    moved_pairs.append((source_file, target_file))
                    episode_entry = self._build_local_episode_entry(
                        video_id,
                        target_file,
                        base_dir=target_dir,
                        index=next_index,
                        include_source_path=True,
                    )
                else:
                    episode_entry = self._build_local_episode_entry(
                        video_id,
                        source_file,
                        base_dir=normalized_root,
                        index=next_index,
                        include_source_path=True,
                    )

                new_entries.append(episode_entry)
                episode_key = self._normalize_local_path_key(self._get_episode_entry_path(None, episode_entry))
                if episode_key:
                    existing_path_keys.add(episode_key)

            if not new_entries:
                return {
                    "status": "skipped",
                    "reason": "duplicate_episode_exists",
                    "duplicate_id": str(getattr(bind_existing_video, "id", "") or ""),
                    "code": code,
                    "duplicate_files": duplicate_files,
                }

            merged_entries = self._merge_local_episode_entries(existing_entries, new_entries)
            storage_info = self._resolve_import_episode_storage(
                merged_entries,
                preferred_dir=target_dir if normalized_mode == self.LOCAL_IMPORT_MODE_HARDLINK_MOVE else "",
            )

            if bind_existing_video:
                existing_video = self._video_repo.get_by_id(video_id) or bind_existing_video
                existing_video.local_video_path = storage_info["local_video_path"]
                existing_video.local_source_path = storage_info["local_source_path"]
                existing_video.local_asset_dir_name = storage_info["local_asset_dir_name"] or local_asset_dir_name
                existing_video.local_source_filename = storage_info["local_source_filename"] or local_source_filename
                existing_video.source_origin = self.SOURCE_ORIGIN_LOCAL_IMPORT
                existing_video.source_updated_time = get_current_time()
                existing_video.storage_path_relative = storage_info["storage_path_relative"]
                existing_video.storage_path_kind = storage_info["storage_path_kind"]
                existing_video.total_units = len(merged_entries)
                existing_video.current_unit = max(1, int(getattr(existing_video, "current_unit", 1) or 1))
                display_payload = dict(getattr(existing_video, "display", {}) or {})
                display_payload["local_episodes"] = merged_entries
                existing_video.display = display_payload

                if not self._video_repo.save(existing_video):
                    raise RuntimeError("save appended local video episodes failed")
                self._remember_local_video_in_cache(local_video_cache, existing_video)

                return {
                    "status": "imported",
                    "video_id": video_id,
                    "attached": True,
                    "code": code,
                    "episode_count": len(new_entries),
                    "duplicate_files": duplicate_files,
                }

            payload = {
                "id": video_id,
                "title": fallback_title,
                "code": code,
                "date": "",
                "series": "",
                "creator": "",
                "actors": [],
                "desc": "",
                "score": None,
                "tag_ids": [],
                "list_ids": [],
                "magnets": [],
                "thumbnail_images": [],
                "preview_video": "",
                "cover_path": "",
                "thumbnail_images_local": [],
                "preview_video_local": "",
                "cover_path_local": "",
                "local_video_path": storage_info["local_video_path"],
                "local_source_path": storage_info["local_source_path"],
                "local_asset_dir_name": storage_info["local_asset_dir_name"] or local_asset_dir_name,
                "local_source_filename": storage_info["local_source_filename"] or local_source_filename,
                "source_origin": self.SOURCE_ORIGIN_LOCAL_IMPORT,
                "source_updated_time": get_current_time(),
                "local_metadata_enriched": False,
                "storage_path_relative": storage_info["storage_path_relative"],
                "storage_path_kind": storage_info["storage_path_kind"],
                "total_units": len(merged_entries),
                "current_unit": 1,
                "display": {"local_episodes": merged_entries},
            }
            result = self.import_video(payload, local_video_cache=local_video_cache)
            if not result.success:
                raise RuntimeError(result.message or "import_failed")

            return {
                "status": "imported",
                "video_id": video_id,
                "attached": False,
                "code": code,
                "episode_count": len(new_entries),
                "duplicate_files": duplicate_files,
            }
        except Exception:
            for source_file, target_file in reversed(moved_pairs):
                try:
                    if os.path.exists(target_file) and not os.path.exists(source_file):
                        os.makedirs(os.path.dirname(source_file), exist_ok=True)
                        shutil.move(target_file, source_file)
                except Exception:
                    pass
            if target_dir and os.path.isdir(target_dir) and not os.listdir(target_dir):
                shutil.rmtree(target_dir, ignore_errors=True)
            raise

    def import_local_videos_from_path(
        self,
        source_path: str,
        import_mode: str = "",
        grouping_mode: str = "",
    ) -> ServiceResult:
        try:
            source_dir = os.path.abspath(os.path.expandvars(os.path.expanduser(str(source_path or "").strip())))
            if not source_dir:
                return ServiceResult.error("source_path is required")
            if not os.path.exists(source_dir):
                return ServiceResult.error("source_path does not exist")
            if not os.path.isdir(source_dir):
                return ServiceResult.error("source_path must be a directory")
            normalized_mode = self.normalize_local_import_mode(import_mode)
            normalized_grouping_mode = self.normalize_local_import_grouping_mode(grouping_mode)

            import_plan = self._build_video_import_units(source_dir, grouping_mode=normalized_grouping_mode)
            scanned_files = int(import_plan.get("scanned_files") or 0)
            scanned_video_files = int(import_plan.get("scanned_video_files") or 0)
            imported_count = 0
            attached_source_count = 0
            appended_episode_count = 0
            duplicate_episode_count = 0
            skipped_count = int(import_plan.get("skipped_count") or 0)
            failed_count = 0
            imported_ids: List[str] = []
            seen_imported_ids = set()
            skipped_items: List[Dict[str, str]] = []
            skipped_items.extend(list(import_plan.get("skipped_items") or []))
            failed_items: List[Dict[str, str]] = []
            sync_started_at = time.perf_counter()
            local_video_cache = self._build_local_video_duplicate_cache()
            with JsonStorage.defer_catalog_index_sync():
                for unit in list(import_plan.get("units") or []):
                    unit_root = str(unit.get("root") or source_dir).strip() or source_dir
                    unit_filenames = list(unit.get("filenames") or [])
                    try:
                        group_result = self._import_local_video_group(
                            unit_root,
                            unit_filenames,
                            normalized_mode=normalized_mode,
                            title_hint=str(unit.get("title_hint") or "").strip(),
                            code_hint=str(unit.get("code_hint") or "").strip(),
                            local_video_cache=local_video_cache,
                        )
                        if group_result.get("status") == "imported":
                            imported_count += 1
                            imported_video_id = str(group_result.get("video_id") or "").strip()
                            if imported_video_id and imported_video_id not in seen_imported_ids:
                                imported_ids.append(imported_video_id)
                                seen_imported_ids.add(imported_video_id)
                            if group_result.get("attached"):
                                attached_source_count += 1
                            appended_episode_count += int(group_result.get("episode_count") or 0)
                            duplicate_files = list(group_result.get("duplicate_files") or [])
                            duplicate_episode_count += len(duplicate_files)
                            for duplicate_file in duplicate_files:
                                skipped_count += 1
                                skipped_items.append(
                                    {
                                        "file": str(duplicate_file or ""),
                                        "reason": "duplicate_episode_exists",
                                        "duplicate_id": str(group_result.get("video_id") or ""),
                                        "code": str(group_result.get("code") or ""),
                                    }
                                )
                            continue

                        duplicate_files = list(group_result.get("duplicate_files") or [])
                        if duplicate_files:
                            duplicate_episode_count += len(duplicate_files)
                            for duplicate_file in duplicate_files:
                                skipped_count += 1
                                skipped_items.append(
                                    {
                                        "file": str(duplicate_file or ""),
                                        "reason": str(group_result.get("reason") or "duplicate_episode_exists"),
                                        "duplicate_id": str(group_result.get("duplicate_id") or ""),
                                        "code": str(group_result.get("code") or ""),
                                    }
                                )
                        else:
                            skipped_count += 1
                            skipped_items.append(
                                {
                                    "file": unit_root,
                                    "reason": str(group_result.get("reason") or "group_skipped"),
                                    "duplicate_id": str(group_result.get("duplicate_id") or ""),
                                    "code": str(group_result.get("code") or ""),
                                }
                            )
                    except Exception as item_error:
                        failed_count += 1
                        failed_items.append(
                            {
                                "file": unit_root,
                                "reason": str(item_error),
                            }
                        )

                if imported_ids:
                    recent_result = self.apply_recent_import_tags(imported_ids, source="local", clear_previous=True)
                    if not recent_result.success:
                        app_logger.warning(
                            f"update recent import tags failed after local video import: {recent_result.message}"
                        )
            sync_elapsed_ms = (time.perf_counter() - sync_started_at) * 1000
            app_logger.info(
                "本地视频导入写入与索引同步完成: "
                f"mode={normalized_mode}, grouping={normalized_grouping_mode}, imported={imported_count}, "
                f"attached={attached_source_count}, elapsed_ms={sync_elapsed_ms:.2f}"
            )

            mode_label = "软连接（保留源文件）" if normalized_mode == self.LOCAL_IMPORT_MODE_SOFTLINK_REF else "硬链接（移动源文件）"
            grouping_label = "逐文件导入" if normalized_grouping_mode == self.LOCAL_IMPORT_GROUPING_PER_FILE else "叶子目录合并"
            summary = (
                f"本地视频导入完成（{mode_label}，{grouping_label}）："
                f"扫描 {scanned_video_files} 个视频，"
                f"成功 {imported_count}，并入已有视频 {attached_source_count}，新增分集 {appended_episode_count}，"
                f"重复跳过 {duplicate_episode_count}，总跳过 {skipped_count}，失败 {failed_count}"
            )
            return ServiceResult.ok(
                {
                    "source_path": source_dir,
                    "import_mode": normalized_mode,
                    "grouping_mode": normalized_grouping_mode,
                    "scanned_files": scanned_files,
                    "scanned_video_files": scanned_video_files,
                    "imported_count": imported_count,
                    "attached_source_count": attached_source_count,
                    "appended_episode_count": appended_episode_count,
                    "duplicate_episode_count": duplicate_episode_count,
                    "skipped_count": skipped_count,
                    "failed_count": failed_count,
                    "imported_ids": imported_ids,
                    "skipped_items": skipped_items,
                    "failed_items": failed_items,
                    "summary": summary,
                },
                "local video import completed",
            )
        except Exception as e:
            error_logger.error(f"import local videos from path failed: {e}")
            return ServiceResult.error("import local videos failed")

    def resolve_local_video_file_path(self, video_id: str, episode_index: int = 0) -> Optional[str]:
        video = self._video_repo.get_by_id(str(video_id or "").strip())
        if not video:
            return None

        normalized_episode = int(episode_index or 0)
        if normalized_episode > 0:
            display = getattr(video, "display", {}) if video else {}
            episodes = display.get("local_episodes") if isinstance(display, dict) else []
            if isinstance(episodes, list) and normalized_episode <= len(episodes):
                episode_path = self._extract_local_episode_path(video, episodes[normalized_episode - 1])
                if episode_path:
                    return episode_path

        stored_relative = str(getattr(video, "storage_path_relative", "") or "").strip()
        if stored_relative:
            stored_abs = resolve_data_relative_path(stored_relative)
            if stored_abs:
                if os.path.isfile(stored_abs):
                    return stored_abs
                if os.path.isdir(stored_abs):
                    preferred_filename = self._resolve_video_source_filename(video)
                    preferred_candidate = os.path.join(stored_abs, preferred_filename)
                    if preferred_filename and os.path.isfile(preferred_candidate):
                        return preferred_candidate
                    for ext in self.VIDEO_FILE_EXTENSIONS:
                        candidate = os.path.join(stored_abs, f"{self.LOCAL_VIDEO_FILENAME}{ext}")
                        if os.path.isfile(candidate):
                            return candidate

        local_video_url = str(getattr(video, "local_video_path", "") or "").strip()
        if local_video_url.startswith("/media/"):
            file_relative = local_video_url[len("/media/"):].lstrip("/")
            candidate = os.path.abspath(os.path.join(DATA_DIR, file_relative.replace("/", os.sep)))
            data_root = os.path.abspath(DATA_DIR)
            try:
                if os.path.commonpath([data_root, candidate]) == data_root and os.path.isfile(candidate):
                    return candidate
            except Exception:
                pass

        source_path = str(getattr(video, "local_source_path", "") or "").strip()
        if source_path:
            expanded_source = os.path.abspath(os.path.expandvars(os.path.expanduser(source_path)))
            if os.path.isfile(expanded_source):
                return expanded_source

        candidate_dirs = []
        resolved_asset_dir = self._resolve_video_local_asset_dir(video)
        if resolved_asset_dir:
            candidate_dirs.append(resolved_asset_dir)
        for legacy_dir in self._get_video_storage_dirs(video.id):
            if legacy_dir not in candidate_dirs:
                candidate_dirs.append(legacy_dir)

        preferred_filename = self._resolve_video_source_filename(video)
        for base_dir in candidate_dirs:
            if not os.path.isdir(base_dir):
                continue
            preferred_candidate = os.path.join(base_dir, preferred_filename)
            if preferred_filename and os.path.isfile(preferred_candidate):
                return preferred_candidate
            for ext in self.VIDEO_FILE_EXTENSIONS:
                candidate = os.path.join(base_dir, f"{self.LOCAL_VIDEO_FILENAME}{ext}")
                if os.path.isfile(candidate):
                    return candidate
        return None

    def _refresh_video_persisted_metadata(self, video: Any, *, source: str) -> bool:
        if not video:
            return False

        payload = video.to_dict() if hasattr(video, "to_dict") else dict(video or {})
        video_id = str(payload.get("id") or "").strip()
        platform_name = str(payload.get("platform") or "").strip()
        plugin_id = str(payload.get("plugin_id") or "").strip()

        context = self._resolve_video_protocol_context(video_id=video_id, platform_name=platform_name)
        if not platform_name:
            platform_name = str(context.get("platform_name") or "").strip()
        manifest = context.get("manifest")
        if manifest is not None and not plugin_id:
            plugin_id = str(getattr(manifest, "plugin_id", "") or "").strip()

        storage_path = ""
        storage_kind = str(payload.get("storage_path_kind") or "").strip()
        if source == "local":
            storage_path = self._resolve_video_storage_path(video if hasattr(video, "id") else Video.from_dict(payload))
            if storage_path and os.path.isfile(storage_path):
                storage_kind = "local_file"
            elif storage_path and normalize_data_relative_path(storage_path):
                storage_kind = storage_kind or "preview_asset_dir"
            elif str(payload.get("local_source_path") or "").strip():
                storage_kind = storage_kind or "source"
            elif video_id:
                try:
                    root_dir, _, _source_key = self._build_preview_asset_root(video_id, "local")
                    storage_path = os.path.join(root_dir, self._sanitize_video_asset_id(video_id))
                    storage_kind = storage_kind or "preview_asset_dir"
                except Exception:
                    storage_path = ""
        else:
            try:
                root_dir, _, _source_key = self._build_preview_asset_root(video_id, "preview")
                storage_path = os.path.join(root_dir, self._sanitize_video_asset_id(video_id))
                storage_kind = storage_kind or "preview_asset_dir"
            except Exception:
                storage_path = ""

        updates = self._build_video_persisted_metadata(
            payload,
            storage_path=storage_path,
            storage_kind=storage_kind,
            platform_name=platform_name,
            plugin_id=plugin_id,
        )
        display_updates = self._build_video_display_from_cover_asset({**payload, **updates})
        if display_updates:
            raw_display = dict(updates.get("display") or payload.get("display") or {})
            raw_display.update(dict(display_updates.get("display") or {}))
            updates["display"] = raw_display

        return self._apply_persisted_fields(video, updates)

    def import_video(
        self,
        video_data: Dict,
        *,
        local_video_cache: Optional[Dict[str, Dict[str, Video]]] = None,
    ) -> ServiceResult:
        try:
            incoming_id = str(video_data.get("id") or "").strip()
            incoming_code = self._normalize_code_for_storage(video_data.get("code"))
            duplicate_id = self._find_local_video_duplicate(
                incoming_id,
                incoming_code,
                local_video_cache=local_video_cache,
            )
            if duplicate_id and duplicate_id != incoming_id:
                return ServiceResult.error("该番号已存在")

            video = self._build_video_entity(video_data)

            if not self._video_repo.save(video):
                return ServiceResult.error("保存视频失败")
            self._remember_local_video_in_cache(local_video_cache, video)

            app_logger.info(f"导入视频成功: {video.code}")
            return ServiceResult.ok(video.to_dict(), "导入成功")
        except Exception as e:
            error_logger.error(f"导入视频失败: {e}")
            return ServiceResult.error("导入失败")

    def _build_video_entity(self, video_data: Dict) -> Video:
        video = Video(
            id=str(video_data.get("id") or "").strip() or generate_id("video"),
            title=video_data.get("title", ""),
            code=self._normalize_code_for_storage(video_data.get("code")),
            date=video_data.get("date", ""),
            series=video_data.get("series", ""),
            creator=video_data.get("creator", ""),
            desc=video_data.get("desc", ""),
            score=video_data.get("score"),
            tag_ids=video_data.get("tag_ids", []),
            platform=video_data.get("platform", ""),
            plugin_id=video_data.get("plugin_id", ""),
            plugin_name=video_data.get("plugin_name", ""),
            display=dict(video_data.get("display") or {}),
            storage_path_relative=video_data.get("storage_path_relative", ""),
            storage_path_kind=video_data.get("storage_path_kind", ""),
            magnets=video_data.get("magnets", []),
            thumbnail_images=video_data.get("thumbnail_images", []),
            preview_video=video_data.get("preview_video", ""),
            cover_path_local=video_data.get("cover_path_local", ""),
            thumbnail_images_local=video_data.get("thumbnail_images_local", []),
            preview_video_local=video_data.get("preview_video_local", ""),
            local_video_path=video_data.get("local_video_path", ""),
            local_source_path=video_data.get("local_source_path", ""),
            local_asset_dir_name=video_data.get("local_asset_dir_name", ""),
            local_source_filename=video_data.get("local_source_filename", ""),
            source_origin=video_data.get("source_origin", ""),
            source_updated_time=video_data.get("source_updated_time", ""),
            local_metadata_enriched=bool(video_data.get("local_metadata_enriched", False)),
            actor_refs=[
                dict(item or {})
                for item in (video_data.get("actor_refs") or [])
                if isinstance(item, dict)
            ],
            create_time=video_data.get("create_time") or get_current_time(),
            last_access_time=video_data.get("last_access_time") or get_current_time()
        )
        video.actors = video_data.get("actors", [])
        video.list_ids = video_data.get("list_ids", [])
        return video

    def import_videos(
        self,
        video_data_list: List[Dict],
        *,
        local_video_cache: Optional[Dict[str, Dict[str, Video]]] = None,
    ) -> ServiceResult:
        """批量导入视频：去重后一次读、一次写、一次索引同步。"""
        try:
            items = [item for item in (video_data_list or []) if isinstance(item, dict)]
            if not items:
                return ServiceResult.error("没有可导入的视频")

            failed_items = []
            videos = []
            seen_ids: set[str] = set()
            seen_codes: Dict[str, str] = {}
            for video_data in items:
                incoming_id = str(video_data.get("id") or "").strip()
                incoming_code = self._normalize_code_for_storage(video_data.get("code"))
                normalized_compare_code = self._normalize_code_for_compare(incoming_code)

                if incoming_id and incoming_id in seen_ids:
                    failed_items.append(
                        {"lookup": incoming_id, "reason": "批次内视频ID重复"}
                    )
                    continue

                if normalized_compare_code:
                    previous_id = seen_codes.get(normalized_compare_code)
                    if previous_id is not None and previous_id != incoming_id:
                        failed_items.append(
                            {"lookup": incoming_code or incoming_id, "reason": "批次内番号重复"}
                        )
                        continue

                duplicate_id = self._find_local_video_duplicate(
                    incoming_id,
                    incoming_code,
                    local_video_cache=local_video_cache,
                )
                if duplicate_id and duplicate_id != incoming_id:
                    failed_items.append(
                        {"lookup": incoming_code or incoming_id, "reason": "该番号已存在"}
                    )
                    continue
                video = self._build_video_entity(video_data)
                videos.append(video)
                if video.id:
                    seen_ids.add(video.id)
                if normalized_compare_code:
                    seen_codes[normalized_compare_code] = video.id

            if not videos:
                reason = failed_items[0]["reason"] if failed_items else "导入失败"
                return ServiceResult.error(reason)

            if hasattr(self._video_repo, "save_many"):
                saved_count = self._video_repo.save_many(videos)
                saved_videos = videos if saved_count == len(videos) else []
            else:
                saved_videos = [video for video in videos if self._video_repo.save(video)]
                saved_count = len(saved_videos)

            if saved_count == 0:
                return ServiceResult.error("保存视频失败")
            if saved_count != len(videos):
                return ServiceResult.error("部分视频保存失败")

            for video in saved_videos:
                self._remember_local_video_in_cache(local_video_cache, video)

            app_logger.info(f"批量导入视频成功: {saved_count} 个")
            return ServiceResult.ok(
                {
                    "videos": [video.to_dict() for video in saved_videos],
                    "imported_count": saved_count,
                    "failed_items": failed_items,
                },
                "导入成功",
            )
        except Exception as e:
            error_logger.error(f"批量导入视频失败: {e}")
            return ServiceResult.error("导入失败")


    @staticmethod
    def _normalize_code_for_compare(code: str) -> str:
        raw = str(code or "").upper()
        return "".join(ch for ch in raw if ch.isalnum())

    def _build_local_video_duplicate_cache(self) -> Dict[str, Dict[str, Video]]:
        cache: Dict[str, Dict[str, Video]] = {"by_id": {}, "by_code": {}}
        for local_video in self._video_repo.get_all():
            self._remember_local_video_in_cache(cache, local_video)
        return cache

    def _remember_local_video_in_cache(
        self,
        local_video_cache: Optional[Dict[str, Dict[str, Video]]],
        video: Optional[Video],
    ) -> None:
        if local_video_cache is None or not isinstance(video, Video):
            return

        video_id = str(getattr(video, "id", "") or "").strip()
        if video_id:
            local_video_cache.setdefault("by_id", {})[video_id] = video

        normalized_code = self._normalize_code_for_compare(getattr(video, "code", ""))
        if normalized_code:
            local_video_cache.setdefault("by_code", {})[normalized_code] = video

    def _find_local_video_duplicate_entity(
        self,
        video_id: str,
        code: str,
        *,
        local_video_cache: Optional[Dict[str, Dict[str, Video]]] = None,
    ) -> Optional[Video]:
        if local_video_cache is not None:
            if video_id:
                existing_by_id = local_video_cache.get("by_id", {}).get(video_id)
                if existing_by_id:
                    return existing_by_id

            normalized_code = self._normalize_code_for_compare(code)
            if not normalized_code:
                return None
            return local_video_cache.get("by_code", {}).get(normalized_code)

        if video_id:
            existing_by_id = self._video_repo.get_by_id(video_id)
            if existing_by_id:
                return existing_by_id

        normalized_code = self._normalize_code_for_compare(code)
        if not normalized_code:
            return None

        for local_video in self._video_repo.get_all():
            if self._normalize_code_for_compare(local_video.code) == normalized_code:
                return local_video
        return None

    def _find_local_video_duplicate(
        self,
        video_id: str,
        code: str,
        *,
        local_video_cache: Optional[Dict[str, Dict[str, Video]]] = None,
    ) -> Optional[str]:
        duplicate_video = self._find_local_video_duplicate_entity(
            video_id,
            code,
            local_video_cache=local_video_cache,
        )
        if not duplicate_video:
            return None
        return duplicate_video.id

    @staticmethod
    def _deduplicate_video_collection(records: List[Dict[str, Any]]) -> Dict[str, int]:
        seen = {}
        moved_to_trash = 0
        duplicate_group_keys = set()
        scanned = 0

        for item in records:
            if not isinstance(item, dict):
                continue
            if bool(item.get("is_deleted", False)):
                continue

            scanned += 1
            normalized_code = VideoAppService._normalize_code_for_compare(item.get("code", ""))
            if not normalized_code:
                continue

            if normalized_code not in seen:
                seen[normalized_code] = item
                continue

            item["is_deleted"] = True
            moved_to_trash += 1
            duplicate_group_keys.add(normalized_code)

        return {
            "scanned": scanned,
            "duplicate_groups": len(duplicate_group_keys),
            "moved_to_trash": moved_to_trash,
            "kept": len(seen),
        }

    def organize_deduplicate_by_code(self) -> ServiceResult:
        try:
            home_records = self._video_document_repo.read_items()
            recommendation_records = self._video_recommendation_document_repo.read_items()

            home_stats = self._deduplicate_video_collection(home_records)
            recommendation_stats = self._deduplicate_video_collection(recommendation_records)

            if not self._video_document_repo.write_items(home_records):
                return ServiceResult.error("failed to write local video database")
            if not self._video_recommendation_document_repo.write_items(recommendation_records):
                return ServiceResult.error("failed to write recommendation video database")

            summary = (
                f"视频去重完成：本地库 {home_stats.get('moved_to_trash', 0)} 条，"
                f"预览库 {recommendation_stats.get('moved_to_trash', 0)} 条已移入回收站"
            )
            return ServiceResult.ok(
                {
                    "home": home_stats,
                    "recommendation": recommendation_stats,
                    "summary": summary,
                },
                "video deduplicate completed",
            )
        except Exception as e:
            error_logger.error(f"organize deduplicate by code failed: {e}")
            return ServiceResult.error("video deduplicate failed")

    @staticmethod
    def _normalize_video_remote_tags(raw_tags: Any) -> List[str]:
        if not isinstance(raw_tags, list):
            return []
        normalized = []
        seen = set()
        for item in raw_tags:
            if isinstance(item, dict):
                tag_name = str(item.get("name") or item.get("tag") or "").strip()
            else:
                tag_name = str(item or "").strip()
            if not tag_name:
                continue
            key = tag_name.lower()
            if key in seen:
                continue
            seen.add(key)
            normalized.append(tag_name)
        return normalized

    @staticmethod
    def _normalize_actor_names(raw_actors: Any) -> List[str]:
        if not isinstance(raw_actors, list):
            return []
        normalized = []
        seen = set()
        for actor in raw_actors:
            name = str(actor or "").strip()
            if not name:
                continue
            key = name.lower()
            if key in seen:
                continue
            seen.add(key)
            normalized.append(name)
        return normalized

    def _ensure_video_tags_for_record(
        self,
        video: Video,
        remote_tags: Any,
        tag_name_to_id: Dict[str, str],
    ) -> Tuple[int, int]:
        remote_tag_names = self._normalize_video_remote_tags(remote_tags)
        if not remote_tag_names:
            return 0, 0

        current_tag_ids = list(video.tag_ids or [])
        created_count = 0
        bound_count = 0

        for tag_name in remote_tag_names:
            key = tag_name.lower()
            tag_id = tag_name_to_id.get(key, "")
            if not tag_id:
                created_tag = self._tag_repo.create(tag_name, ContentType.VIDEO)
                if created_tag:
                    tag_id = created_tag.id
                    tag_name_to_id[key] = tag_id
                    created_count += 1
                else:
                    for tag in self._tag_repo.get_all(ContentType.VIDEO):
                        if str(tag.name or "").strip().lower() == key:
                            tag_id = tag.id
                            tag_name_to_id[key] = tag_id
                            break

            if not tag_id:
                continue

            if tag_id in current_tag_ids:
                continue
            current_tag_ids.append(tag_id)
            bound_count += 1

        if bound_count > 0:
            video.tag_ids = current_tag_ids
        return created_count, bound_count

    @staticmethod
    def _first_item_from_search_result(search_result: Dict[str, Any]) -> Dict[str, Any]:
        videos = (search_result or {}).get("videos", [])
        if not isinstance(videos, list) or not videos:
            return {}
        first = videos[0]
        return first if isinstance(first, dict) else {}

    def _search_first_video_detail(self, adapter: Any, code: str) -> Dict[str, Any]:
        search_result = adapter.search_videos(code, page=1, max_pages=1) or {}
        first_result = self._first_item_from_search_result(search_result)
        if not first_result:
            return {}

        video_id = str(first_result.get("video_id") or first_result.get("id") or "").strip()
        detail = {}
        should_skip_detail = False
        if hasattr(adapter, "should_skip_remote_detail"):
            try:
                should_skip_detail = bool(adapter.should_skip_remote_detail(first_result))
            except Exception as detail_policy_error:
                error_logger.error(
                    f"resolve video detail policy failed: code={code}, error={detail_policy_error}"
                )

        if should_skip_detail:
            detail = first_result if isinstance(first_result, dict) else {}
        elif video_id and hasattr(adapter, "get_video_detail"):
            try:
                detail = adapter.get_video_detail(video_id) or {}
            except Exception as detail_error:
                error_logger.error(f"fetch video detail failed: code={code}, video_id={video_id}, error={detail_error}")

        if not detail and hasattr(adapter, "get_video_by_code"):
            try:
                detail = adapter.get_video_by_code(code) or {}
            except Exception as detail_error:
                error_logger.error(f"fetch video by code failed: code={code}, error={detail_error}")

        if not detail:
            detail = first_result

        return {
            "video_id": video_id or str(detail.get("video_id") or "").strip(),
            "detail": detail if isinstance(detail, dict) else {},
        }

    @staticmethod
    def _pick_first_non_empty(*values) -> str:
        for value in values:
            normalized = str(value or "").strip()
            if normalized:
                return normalized
        return ""

    def _apply_remote_detail_to_video(
        self,
        video: Video,
        detail: Dict[str, Any],
        tag_name_to_id: Dict[str, str],
    ) -> Dict[str, int]:
        updated_fields = 0

        remote_title = self._pick_first_non_empty(detail.get("title"))
        if remote_title and remote_title != str(video.title or ""):
            video.title = remote_title
            updated_fields += 1

        remote_date = self._pick_first_non_empty(detail.get("date"))
        if remote_date and remote_date != str(video.date or ""):
            video.date = remote_date
            updated_fields += 1

        remote_series = self._pick_first_non_empty(detail.get("series"))
        if remote_series and remote_series != str(video.series or ""):
            video.series = remote_series
            updated_fields += 1

        remote_actors = self._normalize_actor_names(detail.get("actors"))
        if remote_actors and remote_actors != list(video.actors or []):
            video.actors = remote_actors
            updated_fields += 1

        remote_actor_refs = [
            dict(item or {})
            for item in (detail.get("actor_refs") or [])
            if isinstance(item, dict)
        ]
        if remote_actor_refs and remote_actor_refs != list(getattr(video, "actor_refs", []) or []):
            video.actor_refs = remote_actor_refs
            updated_fields += 1

        remote_creator = self._pick_first_non_empty(
            detail.get("creator"),
            detail.get("author"),
            remote_actors[0] if remote_actors else "",
        )
        if remote_creator and remote_creator != str(video.creator or ""):
            video.creator = remote_creator
            updated_fields += 1

        remote_cover = self._pick_first_non_empty(detail.get("cover_url"), detail.get("cover_path"))
        if remote_cover and remote_cover != str(video.cover_path or ""):
            video.cover_path = remote_cover
            updated_fields += 1

        remote_preview = self._sanitize_preview_video_url(detail.get("preview_video", ""))
        if remote_preview and remote_preview != str(video.preview_video or ""):
            video.preview_video = remote_preview
            updated_fields += 1

        remote_thumbnails = []
        for item in list(detail.get("thumbnail_images") or []):
            thumb = str(item or "").strip()
            if thumb:
                remote_thumbnails.append(thumb)
        if remote_thumbnails and remote_thumbnails != list(video.thumbnail_images or []):
            video.thumbnail_images = remote_thumbnails
            updated_fields += 1

        remote_magnets = list(detail.get("magnets") or [])
        if remote_magnets and remote_magnets != list(video.magnets or []):
            video.magnets = remote_magnets
            updated_fields += 1

        created_tags, bound_tags = self._ensure_video_tags_for_record(video, detail.get("tags"), tag_name_to_id)
        if bound_tags > 0:
            updated_fields += 1

        if not bool(getattr(video, "local_metadata_enriched", False)):
            video.local_metadata_enriched = True
            updated_fields += 1

        return {
            "updated_fields": updated_fields,
            "created_tags": created_tags,
            "bound_tags": bound_tags,
        }

    @staticmethod
    def _can_enrich_local_video(video: Video) -> bool:
        if not video:
            return False
        if bool(video.is_deleted):
            return False
        if not VideoAppService._is_local_video_id(video.id):
            return False
        if bool(getattr(video, "local_metadata_enriched", False)):
            return False
        if not str(video.code or "").strip():
            return False
        return True

    def _build_video_metadata_adapters(self) -> Dict[str, Any]:
        adapters: Dict[str, Any] = {}
        gateway = get_protocol_gateway()
        manifests = gateway.list_manifests(media_type="video", capability="catalog.search")

        for manifest in manifests:
            platform_name = str(
                resolve_manifest_platform_label(
                    manifest,
                    fallback=getattr(manifest, "config_key", "") or getattr(manifest, "plugin_id", ""),
                )
                or ""
            ).strip().lower()
            if not platform_name:
                continue

            try:
                configured = True
                status_message = ""
                if manifest.has_capability("health.query.status"):
                    status = gateway.get_query_status(manifest.plugin_id) or {}
                    configured = bool(status.get("configured", False))
                    status_message = str(status.get("message") or "").strip()

                if not configured:
                    app_logger.info(f"skip {platform_name} metadata adapter: {status_message}")
                    continue

                adapters[platform_name] = _ProtocolVideoMetadataAdapter(gateway, manifest)
            except Exception as e:
                error_logger.error(f"init {platform_name or manifest.plugin_id} protocol adapter failed: {e}")

        return adapters

    def organize_enrich_local_metadata(self) -> ServiceResult:
        try:
            from core.runtime_profile import is_third_party_enabled

            stats = {
                "total_records": 0,
                "total_local_candidates": 0,
                "processed_candidates": 0,
                "skipped_deleted": 0,
                "skipped_no_code": 0,
                "skipped_already_enriched": 0,
                "skipped_no_match": 0,
                "skipped_third_party_disabled": 0,
                "search_platform_order": [],
                "matched_by_platform": {},
                "updated_records": 0,
                "updated_titles": 0,
                "updated_creators": 0,
                "updated_tag_bindings": 0,
                "created_tags": 0,
                "failed_records": 0,
                "updated_ids": [],
            }

            videos = self._video_repo.get_all()
            stats["total_records"] = len(videos)

            if not is_third_party_enabled():
                for video in videos:
                    if not isinstance(video, Video):
                        continue
                    if bool(video.is_deleted):
                        continue
                    if self._is_local_video_id(video.id):
                        stats["total_local_candidates"] += 1
                        stats["skipped_third_party_disabled"] += 1
                stats["summary"] = (
                    f"LOCAL 补全已跳过：当前运行配置关闭第三方能力，跳过 {stats['skipped_third_party_disabled']} 条"
                )
                return ServiceResult.ok(stats, "local video metadata enrich skipped")

            adapters = self._build_video_metadata_adapters()
            platform_order = list(adapters.keys())
            stats["search_platform_order"] = platform_order
            stats["matched_by_platform"] = {platform: 0 for platform in platform_order}

            video_tags = self._tag_repo.get_all(ContentType.VIDEO)
            tag_name_to_id = {
                str(tag.name or "").strip().lower(): tag.id
                for tag in video_tags
                if str(tag.name or "").strip()
            }

            for video in videos:
                if not isinstance(video, Video):
                    continue

                if bool(video.is_deleted):
                    stats["skipped_deleted"] += 1
                    continue

                if not self._is_local_video_id(video.id):
                    continue

                stats["total_local_candidates"] += 1

                if bool(getattr(video, "local_metadata_enriched", False)):
                    stats["skipped_already_enriched"] += 1
                    continue

                code = str(video.code or "").strip()
                if not code:
                    stats["skipped_no_code"] += 1
                    continue

                stats["processed_candidates"] += 1
                matched_platform = ""
                detail = {}

                for platform_name, adapter in adapters.items():
                    if detail:
                        break
                    try:
                        matched = self._search_first_video_detail(adapter, code)
                        detail = matched.get("detail", {}) if isinstance(matched, dict) else {}
                        if detail:
                            matched_platform = platform_name
                    except Exception as search_error:
                        error_logger.error(
                            f"search on {platform_name} failed: code={code}, error={search_error}"
                        )

                if not detail:
                    stats["skipped_no_match"] += 1
                    continue

                update_stats = self._apply_remote_detail_to_video(video, detail, tag_name_to_id)
                if self._refresh_video_persisted_metadata(video, source="local"):
                    update_stats["updated_fields"] = int(update_stats.get("updated_fields", 0)) + 1
                if matched_platform:
                    matched_by_platform = stats.get("matched_by_platform")
                    if isinstance(matched_by_platform, dict):
                        matched_by_platform[matched_platform] = int(matched_by_platform.get(matched_platform, 0)) + 1

                if update_stats.get("updated_fields", 0) > 0:
                    stats["updated_records"] += 1
                    stats["updated_ids"].append(video.id)

                if str(detail.get("title") or "").strip():
                    stats["updated_titles"] += 1
                if str(video.creator or "").strip():
                    stats["updated_creators"] += 1
                stats["updated_tag_bindings"] += int(update_stats.get("bound_tags", 0))
                stats["created_tags"] += int(update_stats.get("created_tags", 0))

                if not self._video_repo.save(video):
                    stats["failed_records"] += 1
                    error_logger.error(f"save enriched local video failed: id={video.id}, code={code}")
                    continue

                if str(video.cover_path or "").strip():
                    self.cache_cover_to_static_async(video.id, video.cover_path, source="local")
                if list(video.thumbnail_images or []):
                    self.cache_thumbnail_images_async(video.id, list(video.thumbnail_images or []), source="local", force=True)
                if str(video.preview_video or "").strip():
                    self.cache_preview_video_async(video.id, video.preview_video, source="local", force=True)

            matched_by_platform = stats.get("matched_by_platform") if isinstance(stats.get("matched_by_platform"), dict) else {}
            platform_summary_parts = []
            for platform_name in stats.get("search_platform_order", []):
                platform_summary_parts.append(
                    f"{str(platform_name or '').upper()} 命中 {int(matched_by_platform.get(platform_name, 0))}"
                )
            platform_summary = f"{'，'.join(platform_summary_parts)}，" if platform_summary_parts else ""
            stats["summary"] = (
                f"视频 LOCAL 补全完成：成功 {stats['updated_records']}，"
                f"{platform_summary}"
                f"无匹配 {stats['skipped_no_match']}"
            )
            return ServiceResult.ok(stats, "local video metadata enrich completed")
        except Exception as e:
            error_logger.error(f"organize enrich local video metadata failed: {e}")
            return ServiceResult.error("local video metadata enrich failed")

    def organize_refresh_persisted_metadata(self) -> ServiceResult:
        try:
            home_stats = {
                "total_records": 0,
                "updated_records": 0,
                "skipped_deleted": 0,
            }
            recommendation_stats = {
                "total_records": 0,
                "updated_records": 0,
                "skipped_deleted": 0,
            }

            updated_home = []
            updated_recommendations = []

            # 批量补全期间延迟并合并 catalog index 同步；落库合并为每库一次写
            with JsonStorage.defer_catalog_index_sync():
                for video in self._video_repo.get_all():
                    if not isinstance(video, Video):
                        continue
                    home_stats["total_records"] += 1
                    if bool(video.is_deleted):
                        home_stats["skipped_deleted"] += 1
                        continue
                    if self._refresh_video_persisted_metadata(video, source="local"):
                        updated_home.append(video)

                for recommendation in self._video_rec_repo.get_all():
                    recommendation_stats["total_records"] += 1
                    if bool(getattr(recommendation, "is_deleted", False)):
                        recommendation_stats["skipped_deleted"] += 1
                        continue
                    if self._refresh_video_persisted_metadata(recommendation, source="preview"):
                        updated_recommendations.append(recommendation)

                if hasattr(self._video_repo, "save_many"):
                    home_stats["updated_records"] = self._video_repo.save_many(updated_home)
                else:
                    home_stats["updated_records"] = sum(1 for v in updated_home if self._video_repo.save(v))

                if hasattr(self._video_rec_repo, "save_many"):
                    recommendation_stats["updated_records"] = self._video_rec_repo.save_many(updated_recommendations)
                else:
                    recommendation_stats["updated_records"] = sum(
                        1 for r in updated_recommendations if self._video_rec_repo.save(r)
                    )

            summary = (
                f"视频新版元数据补全完成：本地库更新 {home_stats['updated_records']} 条，"
                f"预览库更新 {recommendation_stats['updated_records']} 条"
            )
            return ServiceResult.ok(
                {
                    "home": home_stats,
                    "recommendation": recommendation_stats,
                    "summary": summary,
                },
                "video persisted metadata refresh completed",
            )
        except Exception as e:
            error_logger.error(f"refresh video persisted metadata failed: {e}")
            return ServiceResult.error("refresh video persisted metadata failed")

    def refresh_local_video_metadata(self, video_id: str) -> ServiceResult:
        try:
            from core.runtime_profile import is_third_party_enabled

            target_video_id = str(video_id or "").strip()
            if not target_video_id:
                return ServiceResult.error("missing parameter: video_id")

            video = self._video_repo.get_by_id(target_video_id)
            if not video:
                return ServiceResult.error("video not found")
            if bool(video.is_deleted):
                return ServiceResult.error("video is deleted")
            if not self._is_local_video_id(video.id):
                return ServiceResult.error("only LOCAL videos support metadata refresh")

            if not is_third_party_enabled():
                return ServiceResult.error("third-party integration is disabled in current runtime profile")

            code = str(video.code or "").strip()
            if not code:
                return ServiceResult.error("video code is empty")

            adapters = self._build_video_metadata_adapters()
            platform_order = list(adapters.keys())

            matched_platform = ""
            detail: Dict[str, Any] = {}
            for platform_name, adapter in adapters.items():
                if detail:
                    break
                try:
                    matched = self._search_first_video_detail(adapter, code)
                    detail = matched.get("detail", {}) if isinstance(matched, dict) else {}
                    if detail:
                        matched_platform = platform_name
                except Exception as search_error:
                    error_logger.error(
                        f"refresh local video metadata search on {platform_name} failed: code={code}, error={search_error}"
                    )

            if not detail:
                return ServiceResult.error("no remote match found for current video code")

            video_tags = self._tag_repo.get_all(ContentType.VIDEO)
            tag_name_to_id = {
                str(tag.name or "").strip().lower(): tag.id
                for tag in video_tags
                if str(tag.name or "").strip()
            }
            update_stats = self._apply_remote_detail_to_video(video, detail, tag_name_to_id)
            if self._refresh_video_persisted_metadata(video, source="local"):
                update_stats["updated_fields"] = int(update_stats.get("updated_fields", 0)) + 1

            if not self._video_repo.save(video):
                return ServiceResult.error("save video metadata failed")

            if str(video.cover_path or "").strip():
                self.cache_cover_to_static_async(video.id, video.cover_path, source="local")
            if list(video.thumbnail_images or []):
                self.cache_thumbnail_images_async(video.id, list(video.thumbnail_images or []), source="local", force=True)
            if str(video.preview_video or "").strip():
                self.cache_preview_video_async(video.id, video.preview_video, source="local", force=True)

            detail_result = self.get_video_detail(video.id)
            detail_payload = detail_result.data if detail_result.success else (video.to_dict() if hasattr(video, "to_dict") else {})
            if isinstance(detail_payload, dict):
                detail_payload["metadata_refresh"] = {
                    "matched_platform": matched_platform,
                    "search_platform_order": platform_order,
                    "updated_fields": int(update_stats.get("updated_fields", 0)),
                    "created_tags": int(update_stats.get("created_tags", 0)),
                    "bound_tags": int(update_stats.get("bound_tags", 0)),
                }
            return ServiceResult.ok(detail_payload, "local video metadata refreshed")
        except Exception as e:
            error_logger.error(f"refresh local video metadata failed: {e}")
            return ServiceResult.error("refresh local video metadata failed")

    def _build_preview_asset_prefixes(self, video_id: str) -> tuple:
        preview_dir, preview_relative_dir = self._build_preview_asset_dir(video_id, "preview")
        local_dir, local_relative_dir = self._build_preview_asset_dir(video_id, "local")
        preview_prefix = f"{preview_relative_dir}/"
        local_prefix = f"{local_relative_dir}/"
        return preview_dir, local_dir, preview_prefix, local_prefix

    def _map_preview_asset_url_to_local(
        self,
        asset_url: str,
        preview_prefix: str,
        local_prefix: str,
    ) -> str:
        raw_url = str(asset_url or "").strip()
        if not raw_url:
            return ""
        if not raw_url.startswith(preview_prefix):
            return raw_url

        mapped = f"{local_prefix}{raw_url[len(preview_prefix):]}"
        mapped_abs = self._resolve_static_asset_abs_path(mapped)
        if mapped_abs and os.path.exists(mapped_abs):
            return mapped

        # Source points to preview cache but target does not exist after copy.
        # Clear it so later fallback download/cache logic can repopulate local fields.
        return ""

    def _migrate_recommendation_assets_to_local(self, recommendation_video: VideoRecommendation, local_video: Video) -> dict:
        """
        Migrate cached preview assets from recommendation cache into local video asset directory.
        When copied, refresh local-field URLs from preview-cache path to local-library path.
        """
        video_id = str(getattr(recommendation_video, "id", "") or "").strip()
        if not video_id:
            return {"success": True, "handled": False, "strategy": "no_video_id"}

        preview_dir, local_dir, preview_prefix, local_prefix = self._build_preview_asset_prefixes(video_id)
        copied = False
        try:
            if os.path.isdir(preview_dir):
                os.makedirs(os.path.dirname(local_dir), exist_ok=True)
                shutil.copytree(preview_dir, local_dir, dirs_exist_ok=True)
                copied = True
        except Exception as copy_error:
            error_logger.error(f"复制预览缓存到本地失败: id={video_id}, error={copy_error}")
            return {"success": False, "reason": "copy_preview_cache_failed"}

        preview_video_local = self._map_preview_asset_url_to_local(
            getattr(recommendation_video, "preview_video_local", "") or "",
            preview_prefix,
            local_prefix,
        )
        cover_path_local = self._map_preview_asset_url_to_local(
            getattr(recommendation_video, "cover_path_local", "") or "",
            preview_prefix,
            local_prefix,
        )
        thumbnail_images_local = []
        for item in list(getattr(recommendation_video, "thumbnail_images_local", []) or []):
            mapped_item = self._map_preview_asset_url_to_local(item, preview_prefix, local_prefix)
            if mapped_item:
                thumbnail_images_local.append(mapped_item)

        local_video.preview_video_local = preview_video_local
        local_video.cover_path_local = cover_path_local
        local_video.thumbnail_images_local = thumbnail_images_local

        return {
            "success": True,
            "handled": copied,
            "strategy": "copy_preview_cache" if copied else "no_preview_cache"
        }

    @staticmethod
    def _get_teledrive_video_payload(video: VideoRecommendation) -> Dict[str, Any]:
        display = getattr(video, "display", {}) if video else {}
        if not isinstance(display, dict):
            return {}
        teledrive = display.get("teledrive")
        if not isinstance(teledrive, dict):
            return {}
        if str(teledrive.get("type") or "").strip().lower() != "video":
            return {}
        episodes = teledrive.get("episodes")
        if not isinstance(episodes, list) or not episodes:
            return {}
        return teledrive

    @classmethod
    def _safe_teledrive_asset_relative_path(cls, raw_path: str, fallback_name: str) -> str:
        raw = str(raw_path or "").replace("\\", "/").strip("/")
        parts = [
            cls._sanitize_local_fs_name(part, fallback="part")
            for part in raw.split("/")
            if part and part not in {".", ".."}
        ]
        if not parts:
            parts = [cls._sanitize_local_fs_name(fallback_name, fallback="source.mp4")]
        return os.path.join(*parts)

    @staticmethod
    def _format_download_size(byte_count: int) -> str:
        value = max(0, int(byte_count or 0))
        units = ["B", "KB", "MB", "GB", "TB"]
        size = float(value)
        unit = units[0]
        for unit in units:
            if size < 1024 or unit == units[-1]:
                break
            size /= 1024
        if unit == "B":
            return f"{int(size)} {unit}"
        return f"{size:.1f} {unit}"

    def _build_teledrive_local_video_dir(
        self,
        recommendation_video: VideoRecommendation,
        teledrive: Dict[str, Any],
    ) -> str:
        folder_id = str(teledrive.get("folder_id") or recommendation_video.id or "").strip()
        suffix = self._sanitize_local_fs_name(folder_id, fallback="folder")[:12]
        label = (
            str(teledrive.get("work_id") or "").strip()
            or str(getattr(recommendation_video, "title", "") or "").strip()
            or str(getattr(recommendation_video, "id", "") or "").strip()
        )
        dir_name = self._sanitize_local_fs_name(label, fallback="video")
        if suffix and suffix.lower() not in dir_name.lower():
            dir_name = f"{dir_name}__{suffix}"

        base_dir = os.path.join(VIDEO_DIR, "TeleDrive")
        candidate = os.path.abspath(os.path.join(base_dir, dir_name))
        if not os.path.exists(candidate):
            return candidate

        for index in range(2, 10_000):
            next_candidate = os.path.abspath(os.path.join(base_dir, f"{dir_name}__{index}"))
            if not os.path.exists(next_candidate):
                return next_candidate
        raise RuntimeError(f"failed to allocate TeleDrive video directory: {candidate}")

    @staticmethod
    def _build_local_teledrive_video_display(display: Dict[str, Any], local_episodes: List[Dict[str, Any]]) -> Dict[str, Any]:
        local_display = dict(display or {})
        teledrive = local_display.pop("teledrive", None)
        if isinstance(teledrive, dict):
            origin = {
                key: teledrive.get(key)
                for key in (
                    "type",
                    "root",
                    "path",
                    "folder_id",
                    "work_id",
                    "platform_segment",
                    "provider_key",
                    "provider_label",
                    "plugin_id",
                    "plugin_name",
                )
                if teledrive.get(key) not in (None, "", [], {})
            }
            origin["episode_count"] = len(teledrive.get("episodes") or [])
            origin["thumbnail_count"] = len(teledrive.get("thumbnails") or [])
            local_display["teledrive_origin"] = origin
        if local_episodes:
            local_display["local_episodes"] = local_episodes
        return local_display

    def _download_teledrive_video_file(
        self,
        downloader,
        item: Dict[str, Any],
        tmp_dir: str,
        *,
        fallback_name: str,
        index: int,
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> Dict[str, Any]:
        file_id = str(item.get("file_id") or "").strip()
        if not file_id:
            raise RuntimeError(f"TeleDrive video item has no file id: index={index}")

        item_name = str(item.get("name") or "").strip() or fallback_name
        relative = self._safe_teledrive_asset_relative_path(
            str(item.get("relative_path") or item_name),
            item_name,
        )
        target_path = os.path.abspath(os.path.join(tmp_dir, relative))
        tmp_root = os.path.abspath(tmp_dir)
        try:
            if os.path.commonpath([tmp_root, target_path]) != tmp_root:
                raise RuntimeError("invalid TeleDrive video path")
        except Exception as exc:
            raise RuntimeError("invalid TeleDrive video path") from exc

        if os.path.exists(target_path):
            stem, ext = os.path.splitext(target_path)
            target_path = f"{stem}__{index}{ext or os.path.splitext(item_name)[1] or '.mp4'}"

        downloader.download_file_to_path(
            file_id,
            target_path,
            name=item_name,
            progress_callback=progress_callback,
        )
        return {
            "name": item_name,
            "path": target_path,
            "relative_path": os.path.relpath(target_path, tmp_dir).replace("\\", "/"),
        }

    def _migrate_teledrive_video_content_to_local(
        self,
        recommendation_video: VideoRecommendation,
        local_video: Video,
        *,
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
        item_index: int = 1,
        total_items: int = 1,
    ) -> dict:
        teledrive = self._get_teledrive_video_payload(recommendation_video)
        if not teledrive:
            return {"success": True, "handled": False, "strategy": "not_teledrive"}

        from application.teledrive_app_service import get_teledrive_app_service

        local_dir = self._build_teledrive_local_video_dir(recommendation_video, teledrive)
        tmp_dir = f"{local_dir}.tmp"
        if os.path.isdir(tmp_dir):
            shutil.rmtree(tmp_dir, ignore_errors=True)
        os.makedirs(tmp_dir, exist_ok=True)

        downloader = get_teledrive_app_service()
        downloaded_episodes: List[Dict[str, Any]] = []
        episodes = [item for item in (teledrive.get("episodes") or []) if isinstance(item, dict)]
        cover = teledrive.get("cover") if isinstance(teledrive.get("cover"), dict) else {}
        thumbnails = [item for item in (teledrive.get("thumbnails") or []) if isinstance(item, dict)]
        asset_specs: List[Dict[str, Any]] = []
        for index, episode in enumerate(episodes, start=1):
            asset_specs.append({
                "item": episode,
                "label": f"视频 {index}/{len(episodes)}",
            })
        if cover:
            asset_specs.append({"item": cover, "label": "封面"})
        for index, thumb in enumerate(thumbnails, start=1):
            asset_specs.append({
                "item": thumb,
                "label": f"预览图 {index}/{len(thumbnails)}",
            })

        total_known_bytes = sum(
            max(0, int((spec.get("item") or {}).get("size") or 0))
            for spec in asset_specs
        )
        completed_asset_bytes = 0
        total_assets = max(len(asset_specs), 1)
        normalized_total_items = max(1, int(total_items or 1))
        normalized_item_index = min(max(1, int(item_index or 1)), normalized_total_items)
        overall_start = 10 + ((normalized_item_index - 1) / normalized_total_items) * 80
        overall_span = 80 / normalized_total_items

        def emit_progress(progress: int, message: str, *, force: bool = False) -> None:
            if not progress_callback:
                return
            try:
                progress_callback({
                    "progress": max(10, min(90, int(progress))),
                    "message": message,
                    "force": force,
                })
            except Exception as exc:
                app_logger.warning(f"TeleDrive video migration progress callback failed: {exc}")

        def build_file_progress(
            item: Dict[str, Any],
            *,
            label: str,
            asset_order: int,
        ) -> Callable[[Dict[str, Any]], None]:
            item_known_bytes = max(0, int(item.get("size") or 0))
            item_name = str(item.get("name") or "").strip() or label

            def on_file_progress(update: Dict[str, Any]) -> None:
                nonlocal completed_asset_bytes
                bytes_written = max(0, int((update or {}).get("bytes_written") or 0))
                response_total = max(0, int((update or {}).get("total_bytes") or 0))
                if total_known_bytes > 0:
                    current_bytes = completed_asset_bytes + min(
                        bytes_written,
                        item_known_bytes or response_total or bytes_written,
                    )
                    fraction = min(1.0, current_bytes / max(total_known_bytes, 1))
                else:
                    fallback_total = response_total or item_known_bytes or max(bytes_written, 50 * 1024 * 1024)
                    file_fraction = min(0.98, bytes_written / max(fallback_total, 1)) if bytes_written else 0.0
                    fraction = min(0.99, ((asset_order - 1) + file_fraction) / total_assets)

                progress = int(overall_start + fraction * overall_span)
                total_text = response_total or item_known_bytes
                if total_text:
                    size_text = f"{self._format_download_size(bytes_written)}/{self._format_download_size(total_text)}"
                else:
                    size_text = self._format_download_size(bytes_written)
                emit_progress(
                    progress,
                    f"正在下载 TeleDrive {label}: {item_name} ({size_text})",
                    force=bool((update or {}).get("force")),
                )

            return on_file_progress

        try:
            asset_order = 0
            for index, episode in enumerate(episodes, start=1):
                asset_order += 1
                downloaded = self._download_teledrive_video_file(
                    downloader,
                    episode,
                    tmp_dir,
                    fallback_name=f"episode-{index:03d}.mp4",
                    index=index,
                    progress_callback=build_file_progress(
                        episode,
                        label=f"视频 {index}/{len(episodes)}",
                        asset_order=asset_order,
                    ),
                )
                completed_asset_bytes += max(0, int(episode.get("size") or downloaded.get("bytes") or 0))
                downloaded_episodes.append(downloaded)

            if not downloaded_episodes:
                shutil.rmtree(tmp_dir, ignore_errors=True)
                return {"success": False, "reason": "teledrive_episodes_empty"}

            cover_local_url = ""
            if cover:
                asset_order += 1
                cover_download = self._download_teledrive_video_file(
                    downloader,
                    cover,
                    tmp_dir,
                    fallback_name="cover.jpg",
                    index=1,
                    progress_callback=build_file_progress(
                        cover,
                        label="封面",
                        asset_order=asset_order,
                    ),
                )
                completed_asset_bytes += max(0, int(cover.get("size") or cover_download.get("bytes") or 0))
                cover_local_url = self._to_media_url(cover_download["path"].replace(tmp_dir, local_dir, 1))

            thumbnail_local_urls: List[str] = []
            for index, thumb in enumerate(thumbnails, start=1):
                asset_order += 1
                thumb_download = self._download_teledrive_video_file(
                    downloader,
                    thumb,
                    tmp_dir,
                    fallback_name=f"thumbs/thumb-{index:04d}.jpg",
                    index=index,
                    progress_callback=build_file_progress(
                        thumb,
                        label=f"预览图 {index}/{len(thumbnails)}",
                        asset_order=asset_order,
                    ),
                )
                completed_asset_bytes += max(0, int(thumb.get("size") or thumb_download.get("bytes") or 0))
                thumbnail_local_urls.append(
                    self._to_media_url(thumb_download["path"].replace(tmp_dir, local_dir, 1))
                )

            if os.path.isdir(local_dir):
                shutil.rmtree(local_dir, ignore_errors=True)
            os.makedirs(os.path.dirname(local_dir), exist_ok=True)
            shutil.move(tmp_dir, local_dir)
        except Exception:
            shutil.rmtree(tmp_dir, ignore_errors=True)
            raise

        local_episodes: List[Dict[str, Any]] = []
        for index, episode in enumerate(downloaded_episodes, start=1):
            local_path = episode["path"].replace(tmp_dir, local_dir, 1)
            media_url = self._to_media_url(local_path)
            if not media_url:
                continue
            local_episodes.append(
                {
                    "name": episode["name"],
                    "relative_path": episode["relative_path"],
                    "url": media_url,
                    "index": index,
                }
            )

        first_episode_path = downloaded_episodes[0]["path"].replace(tmp_dir, local_dir, 1)
        first_episode_url = self._to_media_url(first_episode_path)
        local_video.local_video_path = first_episode_url
        local_video.local_source_path = os.path.abspath(first_episode_path)
        local_video.local_asset_dir_name = os.path.basename(local_dir)
        local_video.local_source_filename = os.path.basename(first_episode_path)
        local_video.preview_video_local = first_episode_url
        local_video.source_origin = "teledrive_migrate"
        local_video.source_updated_time = get_current_time()
        local_video.storage_path_relative = normalize_data_relative_path(first_episode_path)
        local_video.storage_path_kind = "local_file" if local_video.storage_path_relative else "source"
        local_video.cover_path_local = cover_local_url
        local_video.thumbnail_images_local = [url for url in thumbnail_local_urls if url]
        local_video.display = self._build_local_teledrive_video_display(
            getattr(recommendation_video, "display", {}) or {},
            local_episodes,
        )

        return {
            "success": True,
            "handled": True,
            "strategy": "download_teledrive",
            "local_dir": local_dir,
            "episode_count": len(local_episodes),
        }

    def migrate_recommendations_to_local(
        self,
        video_ids: List[str],
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> ServiceResult:
        try:
            if not video_ids:
                return ServiceResult.error("video_ids is required")

            total_items = max(1, len(video_ids))
            imported_count = 0
            skipped_count = 0
            failed_count = 0
            imported_ids = []
            skipped_items = []
            failed_items = []

            def emit_progress(update: Dict[str, Any]) -> None:
                if not progress_callback:
                    return
                try:
                    progress_callback(update)
                except Exception as exc:
                    app_logger.warning(f"video migration progress callback failed: {exc}")

            def emit_item_progress(index: int, message: str, *, force: bool = False) -> None:
                progress = 10 + int((min(max(index, 0), total_items) / total_items) * 80)
                emit_progress({
                    "progress": min(90, max(10, progress)),
                    "message": message,
                    "completed_items": imported_count + skipped_count + failed_count,
                    "total_items": total_items,
                    "force": force,
                })

            for item_index, video_id in enumerate(video_ids, start=1):
                try:
                    recommendation_video = self._video_rec_repo.get_by_id(video_id)
                    if not recommendation_video or recommendation_video.is_deleted:
                        skipped_count += 1
                        skipped_items.append({
                            "id": video_id,
                            "reason": "not_found_or_deleted"
                        })
                        emit_item_progress(item_index, f"跳过不存在的预览视频: {video_id}", force=True)
                        continue

                    display_title = (
                        str(getattr(recommendation_video, "title", "") or "").strip()
                        or str(video_id or "").strip()
                    )
                    emit_item_progress(
                        item_index - 1,
                        f"正在迁移预览视频 {item_index}/{total_items}: {display_title}",
                        force=True,
                    )

                    duplicate_id = self._find_local_video_duplicate(
                        recommendation_video.id,
                        recommendation_video.code
                    )
                    if duplicate_id:
                        skipped_count += 1
                        skipped_items.append({
                            "id": video_id,
                            "reason": "duplicate_in_local",
                            "duplicate_id": duplicate_id
                        })
                        emit_item_progress(item_index, f"已跳过本地已存在的视频: {display_title}", force=True)
                        continue

                    create_time = recommendation_video.create_time or get_current_time()
                    last_access_time = recommendation_video.last_access_time or create_time

                    local_video = Video(
                        id=recommendation_video.id,
                        title=recommendation_video.title or "",
                        title_jp=recommendation_video.title_jp or "",
                        creator=recommendation_video.creator or "",
                        desc=recommendation_video.desc or "",
                        cover_path=recommendation_video.cover_path or "",
                        total_units=recommendation_video.total_units or 0,
                        current_unit=max(1, recommendation_video.current_unit or 1),
                        score=recommendation_video.score,
                        tag_ids=list(recommendation_video.tag_ids or []),
                        list_ids=list(recommendation_video.list_ids or []),
                        create_time=create_time,
                        last_access_time=last_access_time,
                        is_deleted=False,
                        code=recommendation_video.code or "",
                        date=recommendation_video.date or "",
                        series=recommendation_video.series or "",
                        magnets=list(recommendation_video.magnets or []),
                        thumbnail_images=list(recommendation_video.thumbnail_images or []),
                        preview_video=recommendation_video.preview_video or "",
                        cover_path_local=getattr(recommendation_video, "cover_path_local", "") or "",
                        thumbnail_images_local=list(getattr(recommendation_video, "thumbnail_images_local", []) or []),
                        preview_video_local=getattr(recommendation_video, "preview_video_local", "") or "",
                        platform=getattr(recommendation_video, "platform", "") or "",
                        plugin_id=getattr(recommendation_video, "plugin_id", "") or "",
                        plugin_name=getattr(recommendation_video, "plugin_name", "") or "",
                        display=dict(getattr(recommendation_video, "display", {}) or {}),
                        storage_path_relative=getattr(recommendation_video, "storage_path_relative", "") or "",
                        storage_path_kind=getattr(recommendation_video, "storage_path_kind", "") or "",
                        actor_refs=[
                            dict(item or {})
                            for item in (getattr(recommendation_video, "actor_refs", []) or [])
                            if isinstance(item, dict)
                        ],
                    )
                    local_video.actors = list(recommendation_video.actors or [])

                    assets_result = self._migrate_teledrive_video_content_to_local(
                        recommendation_video,
                        local_video,
                        progress_callback=emit_progress,
                        item_index=item_index,
                        total_items=total_items,
                    )
                    if assets_result.get("success") and not assets_result.get("handled"):
                        assets_result = self._migrate_recommendation_assets_to_local(recommendation_video, local_video)
                    if not assets_result.get("success"):
                        failed_count += 1
                        failed_items.append({
                            "id": video_id,
                            "reason": assets_result.get("reason", "asset_migrate_failed")
                        })
                        emit_item_progress(item_index, f"迁移失败: {display_title}", force=True)
                        continue

                    self._refresh_video_persisted_metadata(local_video, source="local")

                    if not self._video_repo.save(local_video):
                        failed_count += 1
                        failed_items.append({
                            "id": video_id,
                            "reason": "save_local_failed"
                        })
                        emit_item_progress(item_index, f"保存本地视频失败: {display_title}", force=True)
                        continue

                    if local_video.cover_path and not local_video.cover_path_local:
                        self.cache_cover_to_static_async(
                            local_video.id,
                            local_video.cover_path,
                            source="local"
                        )

                    if local_video.thumbnail_images and not local_video.thumbnail_images_local:
                        self.cache_thumbnail_images_async(
                            local_video.id,
                            local_video.thumbnail_images,
                            source="local"
                        )

                    if (
                        local_video.preview_video and
                        not local_video.preview_video_local and
                        self._video_platform_allows_preview_download(video_id=local_video.id)
                    ):
                        self.cache_preview_video_async(
                            local_video.id,
                            local_video.preview_video,
                            source="local"
                        )

                    imported_count += 1
                    imported_ids.append(video_id)
                    emit_item_progress(item_index, f"已迁移预览视频 {item_index}/{total_items}: {display_title}", force=True)
                except Exception as item_error:
                    failed_count += 1
                    failed_items.append({
                        "id": video_id,
                        "reason": str(item_error)
                    })
                    emit_item_progress(item_index, f"迁移异常: {video_id}", force=True)
                    error_logger.error(f"migrate recommendation video failed: {video_id}, {item_error}")

            app_logger.info(
                f"migrate recommendation videos to local finished: imported={imported_count}, "
                f"skipped={skipped_count}, failed={failed_count}"
            )
            return ServiceResult.ok(
                {
                    "imported_count": imported_count,
                    "skipped_count": skipped_count,
                    "failed_count": failed_count,
                    "imported_ids": imported_ids,
                    "skipped_items": skipped_items,
                    "failed_items": failed_items
                },
                f"导入完成：成功{imported_count}，跳过{skipped_count}，失败{failed_count}"
            )
        except Exception as e:
            error_logger.error(f"migrate recommendation videos to local failed: {e}")
            return ServiceResult.error("导入本地库失败")

    def get_trash_list(self) -> ServiceResult:
        try:
            videos = self._video_repo.get_all()
            trash_list = [v.to_dict() for v in videos if v.is_deleted]
            trash_list = self._annotate_video_records(trash_list)
            return ServiceResult.ok(trash_list)
        except Exception as e:
            error_logger.error(f"获取回收站列表失败: {e}")
            return ServiceResult.error("获取回收站失败")
    
    def get_videos_by_tag(self, tag_id: str) -> ServiceResult:
        try:
            videos = self._video_repo.get_by_tag(tag_id)
            videos = [v for v in videos if not v.is_deleted]
            return ServiceResult.ok(self._annotate_video_records([v.to_dict() for v in videos]))
        except Exception as e:
            error_logger.error(f"获取标签视频失败: {e}")
            return ServiceResult.error("获取视频失败")
    
    def get_videos_by_actor(self, actor_name: str) -> ServiceResult:
        try:
            videos = self._video_repo.get_all()
            filtered = []
            for v in videos:
                if v.is_deleted:
                    continue
                if actor_name in v.actors:
                    filtered.append(v.to_dict())
            return ServiceResult.ok(self._annotate_video_records(filtered))
        except Exception as e:
            error_logger.error(f"获取演员视频失败: {e}")
            return ServiceResult.error("获取视频失败")
    
    def bind_tags(self, video_id: str, tag_ids: List[str]) -> ServiceResult:
        try:
            validated_tag_ids, validation_error = validate_tag_ids_for_content_type(
                self._tag_repo,
                tag_ids,
                ContentType.VIDEO,
            )
            if validation_error:
                return ServiceResult.error(validation_error)
            
            video = self._video_repo.get_by_id(video_id)
            if not video:
                return ServiceResult.error("视频不存在")
            
            video.bind_tags(validated_tag_ids)
            
            if not self._video_repo.save(video):
                return ServiceResult.error("绑定标签失败")
            
            app_logger.info(f"绑定视频标签成功: {video_id}, 标签: {validated_tag_ids}")
            return ServiceResult.ok({"video_id": video_id, "tag_ids": validated_tag_ids}, "标签绑定成功")
        except Exception as e:
            error_logger.error(f"绑定视频标签失败: {e}")
            return ServiceResult.error("绑定标签失败")
    
    def update_meta(self, video_id: str, meta: Dict) -> ServiceResult:
        try:
            video = self._video_repo.get_by_id(video_id)
            if not video:
                return ServiceResult.error("video not found")

            target_code = meta.get("code")
            if target_code is not None:
                target_code = str(target_code).strip()
                if target_code:
                    existing = self._video_repo.get_by_code(target_code)
                    if existing and existing.id != video_id:
                        return ServiceResult.error("code already exists")
                video.code = target_code

            if "title" in meta and meta.get("title") is not None:
                video.title = str(meta.get("title")).strip()

            if "date" in meta and meta.get("date") is not None:
                video.date = str(meta.get("date")).strip()

            if "series" in meta and meta.get("series") is not None:
                video.series = str(meta.get("series")).strip()

            if "desc" in meta and meta.get("desc") is not None:
                video.desc = str(meta.get("desc")).strip()

            if "cover_path" in meta and meta.get("cover_path"):
                video.cover_path = meta.get("cover_path")

            actors = meta.get("actors")
            if actors is not None:
                if isinstance(actors, str):
                    actors = actors.replace(chr(65292), ",").split(",")
                if isinstance(actors, list):
                    normalized_actors = []
                    for actor in actors:
                        actor_name = str(actor).strip()
                        if actor_name and actor_name not in normalized_actors:
                            normalized_actors.append(actor_name)
                    video.actors = normalized_actors
                else:
                    video.actors = []

            if "creator" in meta and meta.get("creator") is not None:
                video.creator = str(meta.get("creator")).strip()
            elif "author" in meta and meta.get("author") is not None:
                video.creator = str(meta.get("author")).strip()
            elif video.actors:
                video.creator = video.actors[0]
            else:
                video.creator = ""

            if not self._video_repo.save(video):
                return ServiceResult.error("failed to save video")

            app_logger.info(f"update video meta success: {video_id}")
            return ServiceResult.ok(self._annotate_video_record(video.to_dict()), "updated")
        except Exception as e:
            error_logger.error(f"update video meta failed: {e}")
            return ServiceResult.error("update failed")

    def filter_by_tags(self, include_tags: List[str], exclude_tags: List[str]) -> ServiceResult:
        try:
            videos = self._video_repo.filter_by_tags(include_tags, exclude_tags)
            tags = self._tag_repo.get_all()
            tag_map = {t.id: t.name for t in tags}
            
            results = []
            for v in videos:
                video_info = v.to_dict()
                video_info["tags"] = [{"id": tid, "name": tag_map.get(tid, tid)} for tid in v.tag_ids]
                results.append(video_info)
            results = self._annotate_video_records(results)
            
            app_logger.info(f"筛选成功: 包含 {include_tags}, 排除 {exclude_tags}, 结果数量: {len(results)}")
            return ServiceResult.ok(results)
        except Exception as e:
            error_logger.error(f"筛选失败: {e}")
            return ServiceResult.error("筛选失败")
    
    def filter_multi(self, include_tags: List[str] = None, exclude_tags: List[str] = None,
                     authors: List[str] = None, list_ids: List[str] = None) -> ServiceResult:
        try:
            videos = self._video_repo.filter_multi(include_tags, exclude_tags, authors, list_ids)
            tags = self._tag_repo.get_all()
            tag_map = {t.id: t.name for t in tags}
            
            results = []
            for v in videos:
                video_info = v.to_dict()
                video_info["tags"] = [{"id": tid, "name": tag_map.get(tid, tid)} for tid in v.tag_ids]
                results.append(video_info)
            results = self._annotate_video_records(results)
            
            app_logger.info(f"筛选成功: 包含 {include_tags}, 排除 {exclude_tags}, 作者{authors}, 清单 {list_ids}, 结果数量: {len(results)}")
            return ServiceResult.ok(results)
        except Exception as e:
            error_logger.error(f"筛选失败: {e}")
            return ServiceResult.error("筛选失败")
    
    def batch_add_tags(self, video_ids: List[str], tag_ids: List[str]) -> ServiceResult:
        try:
            validated_tag_ids, validation_error = validate_tag_ids_for_content_type(
                self._tag_repo,
                tag_ids,
                ContentType.VIDEO,
            )
            if validation_error:
                return ServiceResult.error(validation_error)
            
            if hasattr(self._video_repo, "update_many_by_ids"):
                updated_count = self._video_repo.update_many_by_ids(
                    video_ids,
                    lambda video: video.add_tags(validated_tag_ids),
                )
            else:
                updated_count = 0
                for video_id in video_ids:
                    video = self._video_repo.get_by_id(video_id)
                    if video:
                        video.add_tags(validated_tag_ids)
                        if self._video_repo.save(video):
                            updated_count += 1
            
            if updated_count == 0:
                return ServiceResult.error("没有找到有效视频")
            
            app_logger.info(f"批量添加标签成功: {updated_count}个视频, 标签: {validated_tag_ids}")
            return ServiceResult.ok({"updated_count": updated_count, "tag_ids": validated_tag_ids}, f"成功为 {updated_count} 个视频添加标签")
        except Exception as e:
            error_logger.error(f"批量添加标签失败: {e}")
            return ServiceResult.error("批量添加标签失败")
    
    def batch_remove_tags(self, video_ids: List[str], tag_ids: List[str]) -> ServiceResult:
        try:
            if hasattr(self._video_repo, "update_many_by_ids"):
                updated_count = self._video_repo.update_many_by_ids(
                    video_ids,
                    lambda video: video.remove_tags(tag_ids),
                )
            else:
                updated_count = 0
                for video_id in video_ids:
                    video = self._video_repo.get_by_id(video_id)
                    if video:
                        video.remove_tags(tag_ids)
                        if self._video_repo.save(video):
                            updated_count += 1
            
            if updated_count == 0:
                return ServiceResult.error("没有找到有效视频")
            
            app_logger.info(f"批量移除标签成功: {updated_count}个视频, 标签: {tag_ids}")
            return ServiceResult.ok({"updated_count": updated_count, "tag_ids": tag_ids}, f"成功为 {updated_count} 个视频移除标签")
        except Exception as e:
            error_logger.error(f"批量移除标签失败: {e}")
            return ServiceResult.error("批量移除标签失败")

    @staticmethod
    def _normalize_preview_source(source: str) -> str:
        return "preview" if str(source or "").strip().lower() == "preview" else "local"

    @staticmethod
    def _is_preview_import_asset_download_enabled() -> bool:
        try:
            from application.config_app_service import ConfigAppService

            result = ConfigAppService().get_config()
            if not result.success or not isinstance(result.data, dict):
                return True
            return bool(result.data.get("auto_download_preview_assets_for_preview_import", False))
        except Exception as e:
            app_logger.warning(f"读取预览库资源下载配置失败: {e}")
            return True

    def _allow_asset_cache_for_source(self, source_key: str) -> bool:
        if source_key != "preview":
            return True
        return self._is_preview_import_asset_download_enabled()

    @staticmethod
    def _sanitize_video_asset_id(video_id: str) -> str:
        return re.sub(r"[^0-9A-Za-z._-]+", "_", str(video_id or "").strip()) or "video"

    @classmethod
    def _get_default_video_manifest(cls):
        manifests = list(get_protocol_gateway().list_manifests(media_type="video", capability="catalog.search"))
        return manifests[0] if manifests else None

    @classmethod
    def _resolve_video_protocol_context(cls, video_id: str = "", platform_name: str = "") -> Dict[str, Any]:
        normalized_id = str(video_id or "").strip()
        normalized_platform = str(platform_name or "").strip()
        if normalized_id.upper().startswith("LOCAL"):
            return {
                "platform_key": "LOCAL",
                "platform_name": "local",
                "original_id": normalized_id,
                "manifest": None,
            }

        manifest = None
        original_id = normalized_id

        if normalized_id:
            parsed_platform, parsed_original_id, parsed_manifest = split_prefixed_id(
                normalized_id,
                media_type="video",
            )
            if parsed_manifest is not None:
                manifest = parsed_manifest
                normalized_platform = str(parsed_platform or "").strip() or normalized_platform
                original_id = str(parsed_original_id or "").strip() or normalized_id

        if manifest is None and normalized_platform:
            manifest = resolve_platform_manifest(normalized_platform, media_type="video")

        if manifest is None:
            manifest = cls._get_default_video_manifest()

        platform_key = str(normalized_platform or "").strip().upper()
        platform_label = str(normalized_platform or "").strip().lower()
        if manifest is not None:
            platform_key = resolve_manifest_host_prefix(manifest, fallback=platform_key)
            platform_label = str(
                resolve_manifest_platform_label(
                    manifest,
                    fallback=platform_key,
                )
                or ""
            ).strip().lower()

        return {
            "platform_key": platform_key or "LOCAL",
            "platform_name": platform_label or "local",
            "original_id": str(original_id or normalized_id or "").strip(),
            "manifest": manifest,
        }

    @classmethod
    def _get_video_platform_key(cls, video_id: str, platform_name: str = "") -> str:
        return str(cls._resolve_video_protocol_context(video_id=video_id, platform_name=platform_name).get("platform_key") or "LOCAL")

    @classmethod
    def _get_video_original_id(cls, video_id: str, platform_name: str = "") -> str:
        context = cls._resolve_video_protocol_context(video_id=video_id, platform_name=platform_name)
        original_id = str(context.get("original_id") or "").strip()
        return original_id or str(video_id or "").strip()

    @staticmethod
    def _get_manifest_asset_policy(manifest, asset_kind: str) -> Dict[str, Any]:
        resource_policy = dict(getattr(manifest, "resource_policy", {}) or {}) if manifest is not None else {}
        assets = resource_policy.get("assets") if isinstance(resource_policy, dict) else {}
        if not isinstance(assets, dict):
            return {}
        policy = assets.get(str(asset_kind or "").strip()) or {}
        return dict(policy) if isinstance(policy, dict) else {}

    @classmethod
    def _iter_video_asset_manifests(cls, video_id: str = "", platform_name: str = ""):
        yielded = set()
        primary_manifest = cls._resolve_video_protocol_context(video_id=video_id, platform_name=platform_name).get("manifest")
        if primary_manifest is not None:
            yielded.add(primary_manifest.plugin_id)
            yield primary_manifest

        for manifest in get_protocol_gateway().list_manifests(media_type="video"):
            if manifest.plugin_id in yielded:
                continue
            yielded.add(manifest.plugin_id)
            yield manifest

    @staticmethod
    def _request_profile_matches(url: str, profile: Dict[str, Any]) -> bool:
        parsed = urlparse(str(url or "").strip())
        host = str(parsed.netloc or "").strip().lower()
        lowered_url = str(url or "").strip().lower()

        match_hosts = [
            str(item or "").strip().lower()
            for item in (profile.get("match_hosts") or [])
            if str(item or "").strip()
        ]
        if match_hosts:
            if any(candidate in host for candidate in match_hosts):
                return True

        path_prefixes = [
            str(item or "").strip().lower()
            for item in (profile.get("path_prefixes") or [])
            if str(item or "").strip()
        ]
        if path_prefixes:
            return any(lowered_url.startswith(prefix) for prefix in path_prefixes)

        return False

    @classmethod
    def _find_asset_request_profile(
        cls,
        asset_url: str,
        asset_kind: str,
        video_id: str = "",
        platform_name: str = "",
    ) -> Tuple[Any, Dict[str, Any]]:
        for manifest in cls._iter_video_asset_manifests(video_id=video_id, platform_name=platform_name):
            policy = cls._get_manifest_asset_policy(manifest, asset_kind)
            for raw_profile in (policy.get("request_profiles") or []):
                if not isinstance(raw_profile, dict):
                    continue
                profile = dict(raw_profile)
                if cls._request_profile_matches(asset_url, profile):
                    return manifest, profile
        return None, {}

    @staticmethod
    def _extract_nested_mapping(payload: Dict[str, Any], field_path: str) -> Dict[str, Any]:
        current: Any = dict(payload or {})
        for part in [str(item or "").strip() for item in str(field_path or "").split(".") if str(item or "").strip()]:
            if not isinstance(current, dict):
                return {}
            current = current.get(part)
        return dict(current or {}) if isinstance(current, dict) else {}

    @classmethod
    def _load_profile_cookie_header(cls, manifest, profile: Dict[str, Any]) -> str:
        config_key = str(profile.get("cookie_config_key") or getattr(manifest, "config_key", "") or "").strip()
        if not config_key:
            return ""

        cookie_field_path = str(profile.get("cookie_field_path") or "cookies").strip() or "cookies"
        config = get_protocol_config_store().get_plugin_config(config_key, reload=True) or {}
        cookies = cls._extract_nested_mapping(config, cookie_field_path)
        if not cookies:
            return ""

        cookie_pairs = []
        for key, value in cookies.items():
            normalized_key = str(key or "").strip()
            normalized_value = str(value or "").strip()
            if not normalized_key or not normalized_value:
                continue
            cookie_pairs.append(f"{normalized_key}={normalized_value}")
        return "; ".join(cookie_pairs)

    @classmethod
    def _build_protocol_asset_headers(
        cls,
        asset_url: str,
        asset_kind: str,
        video_id: str = "",
        platform_name: str = "",
        content_id: str = "",
    ) -> Dict[str, str]:
        if str(asset_kind or "").strip() == "preview_video":
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "*/*",
            }
        else:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
            }

        normalized_url = str(asset_url or "").strip()
        parsed = urlparse(normalized_url)
        if parsed.scheme and parsed.netloc:
            headers["Referer"] = f"{parsed.scheme}://{parsed.netloc}/"

        manifest, profile = cls._find_asset_request_profile(
            normalized_url,
            asset_kind,
            video_id=video_id,
            platform_name=platform_name,
        )
        if not profile:
            return headers

        effective_content_id = str(content_id or cls._get_video_original_id(video_id, platform_name=platform_name) or "").strip()

        referer_template = str(profile.get("referer_template") or "").strip()
        referer = str(profile.get("referer") or "").strip()
        if referer_template:
            try:
                referer = referer_template.format(content_id=effective_content_id)
            except Exception:
                referer = referer_template
        if referer:
            headers["Referer"] = referer

        origin = str(profile.get("origin") or "").strip()
        if origin:
            headers["Origin"] = origin

        cookie_header = cls._load_profile_cookie_header(manifest, profile)
        if cookie_header:
            headers["Cookie"] = cookie_header

        extra_headers = dict(profile.get("headers") or {})
        for header_key, header_value in extra_headers.items():
            normalized_key = str(header_key or "").strip()
            normalized_value = str(header_value or "").strip()
            if normalized_key and normalized_value:
                headers[normalized_key] = normalized_value

        return headers

    @classmethod
    def _normalize_protocol_asset_url(
        cls,
        asset_url: str,
        asset_kind: str,
        video_id: str = "",
        platform_name: str = "",
    ) -> str:
        normalized_url = str(asset_url or "").strip()
        if not normalized_url:
            return ""
        if normalized_url.startswith("//"):
            return f"https:{normalized_url}"
        if normalized_url.startswith(("/static/", "/media/", "/api/", "/v1/")):
            return normalized_url
        if not normalized_url.startswith("/"):
            return normalized_url

        manifest = cls._resolve_video_protocol_context(video_id=video_id, platform_name=platform_name).get("manifest")
        policy = cls._get_manifest_asset_policy(manifest, asset_kind)
        base_url = str(policy.get("url_base") or "").strip()
        if not base_url:
            return normalized_url
        return urljoin(f"{base_url.rstrip('/')}/", normalized_url.lstrip("/"))

    @classmethod
    def _video_platform_allows_preview_download(cls, video_id: str = "", platform_name: str = "") -> bool:
        manifest = cls._resolve_video_protocol_context(video_id=video_id, platform_name=platform_name).get("manifest")
        policy = cls._get_manifest_asset_policy(manifest, "preview_video")
        download_enabled = policy.get("download_enabled")
        if download_enabled is None:
            return True
        return bool(download_enabled)

    def _build_preview_asset_root(self, video_id: str, source: str) -> tuple:
        source_key = self._normalize_preview_source(source)
        context = self._resolve_video_protocol_context(video_id=video_id)
        platform_key = str(context.get("platform_key") or "LOCAL")
        manifest = context.get("manifest")
        base_root = VIDEO_RECOMMENDATION_CACHE_DIR if source_key == "preview" else VIDEO_DIR
        root_dir = build_platform_root_dir(base_root, manifest=manifest, platform_name=platform_key)

        root_relative = os.path.relpath(os.path.abspath(root_dir), os.path.abspath(DATA_DIR)).replace("\\", "/").strip("/")
        root_url = f"/media/{root_relative}"

        return root_dir, root_url, source_key

    def _build_preview_asset_prefix(self, video_id: str, source: str) -> str:
        _, relative_dir = self._build_preview_asset_dir(video_id, source)
        return f"{relative_dir}/"

    @classmethod
    def _sanitize_preview_video_url(cls, preview_url: str) -> str:
        if not preview_url:
            return ""

        url = str(preview_url).strip()
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
            return url if any(ext in lowered for ext in cls.PREVIEW_VIDEO_EXTENSIONS) else ""

        if lowered.startswith("http://") or lowered.startswith("https://"):
            return url if any(ext in lowered for ext in cls.PREVIEW_VIDEO_EXTENSIONS) else ""

        relative = normalize_data_relative_path(url)
        if not relative:
            normalized_candidate = url.replace("\\", "/").lstrip("/").strip()
            if normalized_candidate and "://" not in normalized_candidate and not url.startswith("//"):
                candidate_abs = os.path.abspath(os.path.join(DATA_DIR, normalized_candidate.replace("/", os.sep)))
                data_root = os.path.abspath(DATA_DIR)
                try:
                    if os.path.commonpath([data_root, candidate_abs]) == data_root and os.path.exists(candidate_abs):
                        relative = normalized_candidate
                except Exception:
                    relative = ""
        if relative:
            media_url = f"/media/{str(relative or '').lstrip('/')}"
            return media_url if any(ext in media_url.lower() for ext in cls.PREVIEW_VIDEO_EXTENSIONS) else ""

        return url if any(ext in lowered for ext in cls.PREVIEW_VIDEO_EXTENSIONS) else ""

    @staticmethod
    def _decode_proxy_url_value(raw_value: str) -> str:
        raw = str(raw_value or "").strip()
        if not raw:
            return ""

        for candidate in (raw, unquote(raw)):
            value = candidate.strip()
            if not value:
                continue

            padded = value + ("=" * (-len(value) % 4))
            for decoder in (base64.b64decode, base64.urlsafe_b64decode):
                try:
                    decoded = decoder(padded.encode("utf-8")).decode("utf-8").strip()
                    if decoded and (
                        decoded.startswith("http://")
                        or decoded.startswith("https://")
                        or decoded.startswith("//")
                        or decoded.startswith("/")
                    ):
                        return decoded
                except Exception:
                    continue

            if value:
                return value

        return ""

    @classmethod
    def _resolve_proxy_source_url(cls, raw_url: str) -> str:
        url = str(raw_url or "").strip()
        if not url:
            return ""

        lowered = url.lower()
        if lowered.startswith("//"):
            return f"https:{url}"

        if (
            lowered.startswith("/api/v1/video/proxy2")
            or lowered.startswith("/v1/video/proxy2")
            or lowered.startswith("/proxy2?")
        ):
            parsed = urlparse(url)
            encoded_url = ""
            for param in (parsed.query or "").split("&"):
                if param.startswith("url="):
                    encoded_url = param[4:]
                    break
            if not encoded_url:
                return ""
            decoded = cls._decode_proxy_url_value(encoded_url)
            if decoded.startswith("//"):
                return f"https:{decoded}"
            return decoded

        if lowered.startswith("/proxy/"):
            parsed = urlparse(url)
            path_segments = [seg for seg in (parsed.path or "").split("/") if seg]
            if len(path_segments) >= 3:
                domain = path_segments[1]
                suffix = "/".join(path_segments[2:])
                target = f"https://{domain}/{suffix}"
                if parsed.query:
                    target = f"{target}?{parsed.query}"
                return target

        return url

    @classmethod
    def to_frontend_asset_url(
        cls,
        asset_url: str,
        *,
        asset_kind: str = "image",
        video_id: str = "",
        platform_name: str = "",
        content_id: str = "",
        proxy_base_path: str = "/api/v1/video/proxy2",
    ) -> str:
        normalized_input = str(asset_url or "").strip()
        if not normalized_input:
            return ""

        resolved_url = cls._resolve_proxy_source_url(normalized_input) or normalized_input
        normalized_url = cls._normalize_protocol_asset_url(
            resolved_url,
            asset_kind=asset_kind,
            video_id=video_id,
            platform_name=platform_name,
        )

        manifest, profile = cls._find_asset_request_profile(
            normalized_url,
            asset_kind,
            video_id=video_id,
            platform_name=platform_name,
        )
        _ = manifest

        should_proxy = False
        if isinstance(profile, dict):
            proxy_mode = str(profile.get("proxy_mode") or "").strip().lower()
            if proxy_mode in {"frontend", "browser", "always"}:
                should_proxy = True
            elif profile.get("frontend_proxy") is True:
                should_proxy = True

        if not should_proxy:
            return normalized_url

        encoded_url = base64.b64encode(normalized_url.encode("utf-8")).decode("utf-8")
        return f"{proxy_base_path}?url={encoded_url}"

    def _begin_asset_download(self, task_key: str) -> bool:
        with self.__class__._asset_download_lock:
            if task_key in self.__class__._asset_download_tasks:
                return False
            self.__class__._asset_download_tasks.add(task_key)
            return True

    def _end_asset_download(self, task_key: str):
        with self.__class__._asset_download_lock:
            self.__class__._asset_download_tasks.discard(task_key)

    @classmethod
    def _guess_preview_video_extension(cls, preview_url: str, content_type: str = "") -> str:
        lowered_url = (preview_url or "").lower()
        for ext in cls.PREVIEW_VIDEO_EXTENSIONS:
            if ext in lowered_url:
                return ext

        lowered_type = (content_type or "").lower()
        if "webm" in lowered_type:
            return ".webm"
        if "quicktime" in lowered_type:
            return ".mov"
        if "mp4" in lowered_type or "video/" in lowered_type:
            return ".mp4"
        return ""

    def _build_preview_video_headers(self, preview_url: str) -> Dict[str, str]:
        return self._build_protocol_asset_headers(
            preview_url,
            asset_kind="preview_video",
        )

    def _request_preview_url(
        self,
        url: str,
        headers: Dict[str, str],
        stream: bool = False,
        timeout: int = 0,
        allow_redirects: bool = True,
    ):
        # Prefer protocol-declared transport client to reuse anti-bot request stacks.
        try:
            client = get_preview_request_client(proxy_base_path="/api/v1/video")
            return client.request(
                "GET",
                url,
                headers=headers,
                stream=stream,
                timeout=timeout,
                allow_redirects=allow_redirects,
            )
        except Exception as e:
            app_logger.warning(f"preview request fallback to requests: url={url}, error={e}")

        return requests.get(
            url,
            headers=headers,
            stream=stream,
            timeout=timeout,
            allow_redirects=allow_redirects,
        )

    def _build_preview_asset_dir(self, video_id: str, source: str) -> tuple:
        source_dir, root_url, source_key = self._build_preview_asset_root(video_id, source)

        os.makedirs(source_dir, exist_ok=True)
        if source_key == "local":
            local_video = self._video_repo.get_by_id(str(video_id or "").strip())
            asset_dir = self._resolve_video_local_asset_dir(local_video)
            if not asset_dir:
                asset_dir = os.path.join(source_dir, self._sanitize_video_asset_id(video_id))
        else:
            asset_dir = os.path.join(source_dir, self._sanitize_video_asset_id(video_id))
        os.makedirs(asset_dir, exist_ok=True)

        relative_dir = self._to_media_url(asset_dir) or f"{root_url}/{self._sanitize_video_asset_id(video_id)}"
        return asset_dir, relative_dir

    def _build_preview_cover_save_paths(self, video_id: str, source: str) -> tuple:
        asset_dir, relative_dir = self._build_preview_asset_dir(video_id, source)
        abs_path = os.path.join(asset_dir, self.PREVIEW_ASSET_COVER_NAME)
        relative_path = f"{relative_dir}/{self.PREVIEW_ASSET_COVER_NAME}"
        return abs_path, relative_path

    def _build_preview_thumbnail_save_paths(self, video_id: str, source: str, index: int) -> tuple:
        asset_dir, relative_dir = self._build_preview_asset_dir(video_id, source)
        thumbs_dir = os.path.join(asset_dir, "thumbs")
        os.makedirs(thumbs_dir, exist_ok=True)
        filename = f"thumb-{index:04d}.jpg"
        abs_path = os.path.join(thumbs_dir, filename)
        relative_path = f"{relative_dir}/thumbs/{filename}"
        return abs_path, relative_path

    def _build_preview_video_save_paths(self, video_id: str, source: str, extension: str) -> tuple:
        asset_dir, relative_dir = self._build_preview_asset_dir(video_id, source)
        filename = f"preview{extension}"
        abs_path = os.path.join(asset_dir, filename)
        relative_path = f"{relative_dir}/{filename}"
        return abs_path, relative_path

    def _build_preview_hls_paths(self, video_id: str, source: str) -> tuple:
        asset_dir, relative_dir = self._build_preview_asset_dir(video_id, source)
        hls_dir = os.path.join(asset_dir, "hls")
        os.makedirs(hls_dir, exist_ok=True)
        playlist_abs = os.path.join(hls_dir, "index.m3u8")
        playlist_rel = f"{relative_dir}/hls/index.m3u8"
        return hls_dir, playlist_abs, playlist_rel

    @staticmethod
    def _extract_m3u8_uri(line: str) -> str:
        match = re.search(r'URI="([^"]+)"', line or "")
        return match.group(1).strip() if match else ""

    @staticmethod
    def _select_hls_variant_playlist(playlist_text: str, playlist_url: str) -> str:
        lines = (playlist_text or "").splitlines()
        best_url = ""
        best_bandwidth = -1

        for idx, line in enumerate(lines):
            current = (line or "").strip()
            if not current.upper().startswith("#EXT-X-STREAM-INF"):
                continue

            bandwidth = 0
            bandwidth_match = re.search(r"BANDWIDTH=(\d+)", current)
            if bandwidth_match:
                try:
                    bandwidth = int(bandwidth_match.group(1))
                except Exception:
                    bandwidth = 0

            candidate_uri = ""
            for next_line in lines[idx + 1:]:
                candidate = (next_line or "").strip()
                if not candidate:
                    continue
                if candidate.startswith("#"):
                    continue
                candidate_uri = candidate
                break

            if not candidate_uri:
                continue

            absolute_url = urljoin(playlist_url, candidate_uri)
            if bandwidth > best_bandwidth:
                best_bandwidth = bandwidth
                best_url = absolute_url

        return best_url

    def _download_preview_hls_to_local(
        self,
        video_id: str,
        preview_video_url: str,
        source: str = "local",
        force: bool = False
    ) -> str:
        source_key = self._normalize_preview_source(source)
        if not force and not self._allow_asset_cache_for_source(source_key):
            app_logger.info(f"预览库资源下载已关闭，终止 HLS 缓存: id={video_id}")
            return ""

        hls_dir, _, playlist_rel = self._build_preview_hls_paths(video_id, source)
        tmp_dir = f"{hls_dir}.tmp"

        if os.path.isdir(tmp_dir):
            shutil.rmtree(tmp_dir, ignore_errors=True)
        os.makedirs(tmp_dir, exist_ok=True)

        try:
            playlist_url = preview_video_url
            playlist_text = ""

            # Handle possible master playlists by choosing highest BANDWIDTH stream.
            for _ in range(3):
                response = self._request_preview_url(
                    playlist_url,
                    headers=self._build_preview_video_headers(playlist_url),
                    stream=False,
                    timeout=0,
                    allow_redirects=True,
                )
                if response.status_code != 200:
                    app_logger.warning(
                        f"下载预览 m3u8 失败: id={video_id}, status={response.status_code}, url={playlist_url}"
                    )
                    return ""

                playlist_url = response.url or playlist_url
                playlist_text = response.text or ""
                variant_url = self._select_hls_variant_playlist(playlist_text, playlist_url)
                if not variant_url:
                    break
                playlist_url = variant_url

            if not playlist_text:
                return ""

            rewritten_lines = []
            downloaded_total = 0
            key_index = 0
            map_index = 0
            seg_index = 0
            asset_cache = {}

            def download_asset(asset_url: str, prefix: str, index: int, fallback_ext: str) -> str:
                nonlocal downloaded_total

                if asset_url in asset_cache:
                    return asset_cache[asset_url]

                if not force and not self._allow_asset_cache_for_source(source_key):
                    app_logger.info(f"预览库资源下载已关闭，终止 HLS 分片缓存: id={video_id}")
                    return ""

                ext = os.path.splitext(urlparse(asset_url).path or "")[1].lower()
                if not ext or len(ext) > 8:
                    ext = fallback_ext

                filename = f"{prefix}-{index:04d}{ext}"
                target_path = os.path.join(tmp_dir, filename)

                resp = self._request_preview_url(
                    asset_url,
                    headers=self._build_preview_video_headers(asset_url),
                    stream=True,
                    timeout=0,
                    allow_redirects=True,
                )
                if resp.status_code not in (200, 206):
                    app_logger.warning(
                        f"下载预览分片失败: id={video_id}, status={resp.status_code}, url={asset_url}"
                    )
                    return ""

                written = 0
                try:
                    with open(target_path, "wb") as f:
                        for chunk in resp.iter_content(chunk_size=256 * 1024):
                            if not chunk:
                                continue
                            if not force and not self._allow_asset_cache_for_source(source_key):
                                app_logger.info(f"预览库资源下载已关闭，终止 HLS 写入: id={video_id}")
                                return ""
                            written += len(chunk)
                            downloaded_total += len(chunk)
                            if downloaded_total > self.PREVIEW_VIDEO_MAX_BYTES:
                                app_logger.warning(
                                    f"预览 HLS 资源过大，停止缓存: id={video_id}, bytes={downloaded_total}"
                                )
                                return ""
                            f.write(chunk)
                finally:
                    try:
                        resp.close()
                    except Exception:
                        pass

                if written == 0:
                    try:
                        os.remove(target_path)
                    except Exception:
                        pass
                    return ""

                asset_cache[asset_url] = filename
                return filename

            for raw_line in playlist_text.splitlines():
                stripped = (raw_line or "").strip()
                if not stripped:
                    rewritten_lines.append(raw_line)
                    continue

                upper_line = stripped.upper()
                if upper_line.startswith("#EXT-X-KEY"):
                    key_uri = self._extract_m3u8_uri(raw_line)
                    if key_uri and not key_uri.startswith("data:"):
                        key_url = urljoin(playlist_url, key_uri)
                        local_key = download_asset(key_url, "key", key_index, ".key")
                        if not local_key:
                            return ""
                        key_index += 1
                        rewritten_lines.append(raw_line.replace(key_uri, local_key, 1))
                    else:
                        rewritten_lines.append(raw_line)
                    continue

                if upper_line.startswith("#EXT-X-MAP"):
                    map_uri = self._extract_m3u8_uri(raw_line)
                    if map_uri and not map_uri.startswith("data:"):
                        map_url = urljoin(playlist_url, map_uri)
                        local_map = download_asset(map_url, "map", map_index, ".mp4")
                        if not local_map:
                            return ""
                        map_index += 1
                        rewritten_lines.append(raw_line.replace(map_uri, local_map, 1))
                    else:
                        rewritten_lines.append(raw_line)
                    continue

                if stripped.startswith("#"):
                    rewritten_lines.append(raw_line)
                    continue

                segment_url = urljoin(playlist_url, stripped)
                local_segment = download_asset(segment_url, "seg", seg_index, ".ts")
                if not local_segment:
                    return ""
                seg_index += 1
                rewritten_lines.append(local_segment)

            if seg_index == 0:
                app_logger.warning(f"m3u8 中未发现可用分片: id={video_id}, url={playlist_url}")
                return ""

            playlist_tmp_path = os.path.join(tmp_dir, "index.m3u8")
            with open(playlist_tmp_path, "w", encoding="utf-8", newline="\n") as f:
                f.write("\n".join(rewritten_lines))

            if os.path.isdir(hls_dir):
                shutil.rmtree(hls_dir, ignore_errors=True)
            shutil.move(tmp_dir, hls_dir)
            return playlist_rel
        except Exception as e:
            error_logger.error(f"缓存预览 HLS 失败: id={video_id}, error={e}")
            return ""
        finally:
            if os.path.isdir(tmp_dir):
                shutil.rmtree(tmp_dir, ignore_errors=True)

    def _download_preview_video_to_local(
        self,
        video_id: str,
        preview_video_url: str,
        source: str = "local",
        force: bool = False
    ) -> str:
        source_key = self._normalize_preview_source(source)
        if not force and not self._allow_asset_cache_for_source(source_key):
            app_logger.info(f"预览库资源下载已关闭，终止预览视频缓存: id={video_id}")
            return ""

        sanitized_url = self._sanitize_preview_video_url(preview_video_url)
        if not sanitized_url:
            return ""

        resolved_url = self._resolve_proxy_source_url(sanitized_url)
        if resolved_url:
            sanitized_url = resolved_url

        if sanitized_url.startswith("/media/"):
            return sanitized_url

        lowered = sanitized_url.lower()
        if ".m3u8" in lowered:
            return self._download_preview_hls_to_local(
                video_id,
                sanitized_url,
                source=source_key,
                force=force
            )

        if not (lowered.startswith("http://") or lowered.startswith("https://")):
            return ""

        response = None
        try:
            response = self._request_preview_url(
                sanitized_url,
                headers=self._build_preview_video_headers(sanitized_url),
                stream=True,
                timeout=0,
                allow_redirects=True,
            )
            if response.status_code not in (200, 206):
                app_logger.warning(
                    f"预览视频下载失败: id={video_id}, status={response.status_code}, url={sanitized_url}"
                )
                return ""

            content_type = (response.headers.get("content-type", "") or "").lower()
            if "mpegurl" in content_type or "m3u8" in content_type:
                final_playlist_url = response.url or sanitized_url
                return self._download_preview_hls_to_local(
                    video_id,
                    final_playlist_url,
                    source=source_key,
                    force=force
                )

            extension = self._guess_preview_video_extension(sanitized_url, content_type)
            if not extension:
                app_logger.warning(
                    f"无法识别预览视频后缀: id={video_id}, content_type={content_type}, url={sanitized_url}"
                )
                return ""

            abs_path, relative_path = self._build_preview_video_save_paths(video_id, source, extension)
            tmp_path = f"{abs_path}.tmp"

            downloaded_bytes = 0
            with open(tmp_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=256 * 1024):
                    if not chunk:
                        continue
                    if not force and not self._allow_asset_cache_for_source(source_key):
                        app_logger.info(f"预览库资源下载已关闭，终止预览视频写入: id={video_id}")
                        f.close()
                        try:
                            os.remove(tmp_path)
                        except Exception:
                            pass
                        return ""
                    downloaded_bytes += len(chunk)
                    if downloaded_bytes > self.PREVIEW_VIDEO_MAX_BYTES:
                        app_logger.warning(f"预览视频过大，跳过缓存: id={video_id}, bytes={downloaded_bytes}")
                        f.close()
                        try:
                            os.remove(tmp_path)
                        except Exception:
                            pass
                        return ""
                    f.write(chunk)

            if downloaded_bytes == 0:
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass
                return ""

            os.replace(tmp_path, abs_path)
            return relative_path
        except Exception as e:
            error_logger.error(f"下载预览视频失败: id={video_id}, error={e}")
            return ""
        finally:
            if response is not None:
                try:
                    response.close()
                except Exception:
                    pass

    def update_preview_video(self, video_id: str, preview_video: str, source: str = "local") -> bool:
        source_key = self._normalize_preview_source(source)
        repo = self._get_repo_by_source(source_key)
        video = repo.get_by_id(video_id)
        if not video:
            return False

        video.preview_video = preview_video or ""
        return bool(repo.save(video))

    def update_cover_path(self, video_id: str, cover_path: str, source: str = "local") -> bool:
        source_key = self._normalize_preview_source(source)
        repo = self._get_repo_by_source(source_key)
        video = repo.get_by_id(video_id)
        if not video:
            return False

        video.cover_path = cover_path or ""
        return bool(repo.save(video))

    def update_thumbnail_images(self, video_id: str, thumbnail_images: List[str], source: str = "local") -> bool:
        source_key = self._normalize_preview_source(source)
        repo = self._get_repo_by_source(source_key)
        video = repo.get_by_id(video_id)
        if not video:
            return False

        video.thumbnail_images = list(thumbnail_images or [])
        return bool(repo.save(video))

    def update_preview_video_local(self, video_id: str, preview_video_local: str, source: str = "local") -> bool:
        source_key = self._normalize_preview_source(source)
        repo = self._get_repo_by_source(source_key)
        video = repo.get_by_id(video_id)
        if not video:
            return False

        video.preview_video_local = preview_video_local or ""
        return bool(repo.save(video))

    def update_cover_path_local(self, video_id: str, cover_path_local: str, source: str = "local") -> bool:
        source_key = self._normalize_preview_source(source)
        repo = self._get_repo_by_source(source_key)
        video = repo.get_by_id(video_id)
        if not video:
            return False

        video.cover_path_local = cover_path_local or ""
        return bool(repo.save(video))

    def update_thumbnail_images_local(self, video_id: str, thumbnail_images_local: List[str], source: str = "local") -> bool:
        source_key = self._normalize_preview_source(source)
        repo = self._get_repo_by_source(source_key)
        video = repo.get_by_id(video_id)
        if not video:
            return False

        video.thumbnail_images_local = list(thumbnail_images_local or [])
        return bool(repo.save(video))

    @staticmethod
    def _resolve_static_asset_abs_path(static_url: str) -> str:
        url = str(static_url or "").strip()
        if url.startswith("/media/"):
            file_relative = url[len("/media/"):].lstrip("/")
            abs_path = os.path.join(DATA_DIR, file_relative.replace("/", os.sep))
            try:
                data_root = os.path.abspath(DATA_DIR)
                target_abs = os.path.abspath(abs_path)
                common = os.path.commonpath([data_root, target_abs])
                if common != data_root:
                    return ""
            except Exception:
                return ""
            return abs_path

        if not url.startswith("/static/"):
            return ""

        static_relative = url.lstrip("/")
        if not static_relative.startswith("static/"):
            return ""

        file_relative = static_relative[len("static/"):]
        abs_path = os.path.join(STATIC_DIR, file_relative.replace("/", os.sep))

        try:
            static_root = os.path.abspath(STATIC_DIR)
            target_abs = os.path.abspath(abs_path)
            common = os.path.commonpath([static_root, target_abs])
            if common != static_root:
                return ""
        except Exception:
            return ""

        return abs_path

    def _read_static_asset_bytes(self, static_url: str) -> Optional[bytes]:
        abs_path = self._resolve_static_asset_abs_path(static_url)
        if not abs_path or not os.path.isfile(abs_path):
            return None

        try:
            with open(abs_path, "rb") as f:
                return f.read()
        except Exception as e:
            app_logger.warning(f"读取本地静态资源失败: url={static_url}, error={e}")
            return None

    def cache_preview_video_async(
        self,
        video_id: str,
        preview_video_url: str,
        source: str = "local",
        force: bool = False
    ):
        source_key = self._normalize_preview_source(source)
        if not force and not self._allow_asset_cache_for_source(source_key):
            app_logger.info(f"预览库资源下载已关闭，跳过预览视频缓存: id={video_id}")
            return

        sanitized_url = self._sanitize_preview_video_url(preview_video_url)
        if not video_id or not sanitized_url:
            return

        resolved_url = self._resolve_proxy_source_url(sanitized_url)
        if resolved_url:
            sanitized_url = resolved_url

        if sanitized_url.startswith("/media/"):
            self.update_preview_video_local(video_id, sanitized_url, source=source_key)
            return

        task_key = f"preview:{source_key}:{video_id}"
        if not self._begin_asset_download(task_key):
            app_logger.info(f"预览视频缓存任务已在进行中: id={video_id}, source={source_key}")
            return

        def download():
            try:
                local_path = self._download_preview_video_to_local(
                    video_id,
                    sanitized_url,
                    source=source_key,
                    force=force
                )
                if not local_path:
                    return
                if self.update_preview_video_local(video_id, local_path, source=source_key):
                    app_logger.info(f"预览视频缓存成功: id={video_id}, source={source_key}, path={local_path}")
            except Exception as e:
                error_logger.error(f"缓存预览视频失败: id={video_id}, error={e}")
            finally:
                self._end_asset_download(task_key)

        thread = threading.Thread(target=download, daemon=True)
        thread.start()

    def _build_video_cover_save_paths(self, video_id: str) -> tuple:
        context = self._resolve_video_protocol_context(video_id=video_id)
        platform_key = str(context.get("platform_key") or "LOCAL")
        manifest = context.get("manifest")
        cover_root = os.path.join(STATIC_DIR, "cover")
        cover_dir = build_platform_root_dir(cover_root, manifest=manifest, platform_name=platform_key)
        os.makedirs(cover_dir, exist_ok=True)

        cover_name = self._get_video_original_id(video_id)
        cover_name = re.sub(r"[^0-9A-Za-z._-]+", "_", cover_name).strip("._")
        if not cover_name:
            cover_name = self._sanitize_video_asset_id(video_id)

        abs_path = os.path.join(cover_dir, f"{cover_name}.jpg")
        relative_path = f"/static/cover/{platform_key}/{cover_name}.jpg"
        return abs_path, relative_path

    def cache_cover_to_static_async(
        self,
        video_id: str,
        cover_url: str,
        source: str = "local"
    ):
        source_key = self._normalize_preview_source(source)
        target_url = str(cover_url or "").strip()
        if not video_id or not target_url:
            return

        if target_url.startswith("/static/cover/"):
            self.update_cover_path(video_id, target_url, source=source_key)
            return

        task_key = f"cover_static:{source_key}:{video_id}"
        if not self._begin_asset_download(task_key):
            app_logger.info(f"静态封面缓存任务已在进行中: id={video_id}, source={source_key}")
            return

        def download():
            tmp_path = ""
            try:
                image_content = self._read_static_asset_bytes(target_url) if target_url.startswith(("/static/", "/media/")) else None
                if not image_content:
                    image_content = self._download_image_content(target_url, video_id)
                if not image_content:
                    return

                image = Image.open(BytesIO(image_content))
                abs_path, relative_path = self._build_video_cover_save_paths(video_id)
                tmp_path = f"{abs_path}.tmp"
                image.convert("RGB").save(tmp_path, "JPEG", quality=95)
                os.replace(tmp_path, abs_path)
                tmp_path = ""

                if self.update_cover_path(video_id, relative_path, source=source_key):
                    app_logger.info(f"静态封面缓存成功: id={video_id}, source={source_key}, path={relative_path}")
            except Exception as e:
                error_logger.error(f"缓存静态封面失败: id={video_id}, source={source_key}, error={e}")
            finally:
                if tmp_path and os.path.exists(tmp_path):
                    try:
                        os.remove(tmp_path)
                    except Exception:
                        pass
                self._end_asset_download(task_key)

        thread = threading.Thread(target=download, daemon=True)
        thread.start()

    def cache_thumbnail_images_async(self, video_id: str, thumbnail_images: List[str], source: str = "local", force: bool = False):
        source_key = self._normalize_preview_source(source)
        if not force and not self._allow_asset_cache_for_source(source_key):
            app_logger.info(f"预览库资源下载已关闭，跳过缩略图缓存: id={video_id}")
            return

        original_images = [str(item or "").strip() for item in (thumbnail_images or [])]
        if not video_id or not original_images:
            return

        task_key = f"thumbs:{source_key}:{video_id}"
        if not self._begin_asset_download(task_key):
            app_logger.info(f"缩略图缓存任务已在进行中: id={video_id}, source={source_key}")
            return

        def download():
            changed = False
            merged_images = list(original_images)
            expected_prefix = self._build_preview_asset_prefix(video_id, source_key)
            all_local = True

            try:
                for idx, raw_url in enumerate(original_images):
                    if not raw_url:
                        continue

                    if raw_url.startswith(expected_prefix):
                        continue

                    all_local = False

                    image_content = None
                    if raw_url.startswith(("/static/", "/media/")):
                        image_content = self._read_static_asset_bytes(raw_url)
                    if not image_content:
                        image_content = self._download_image_content(raw_url, video_id)
                    if not image_content:
                        continue

                    try:
                        tmp_path = ""
                        image = Image.open(BytesIO(image_content))
                        abs_path, relative_path = self._build_preview_thumbnail_save_paths(video_id, source_key, idx + 1)
                        tmp_path = f"{abs_path}.tmp"
                        image.convert("RGB").save(tmp_path, "JPEG", quality=95)
                        os.replace(tmp_path, abs_path)
                        merged_images[idx] = relative_path
                        changed = True
                    except Exception as image_error:
                        error_logger.error(
                            f"缓存缩略图失败: id={video_id}, source={source_key}, index={idx}, error={image_error}"
                        )
                        try:
                            if os.path.exists(tmp_path):
                                os.remove(tmp_path)
                        except Exception:
                            pass

                should_update_local_field = changed or all_local
                if should_update_local_field and self.update_thumbnail_images_local(video_id, merged_images, source=source_key):
                    app_logger.info(f"缩略图缓存成功: id={video_id}, source={source_key}")
            except Exception as e:
                error_logger.error(f"缓存缩略图任务失败: id={video_id}, source={source_key}, error={e}")
            finally:
                self._end_asset_download(task_key)

        thread = threading.Thread(target=download, daemon=True)
        thread.start()

    def _remove_preview_video_file(self, preview_video_url: str):
        url = str(preview_video_url or "").strip()
        if not url:
            return

        removable_roots = []
        if url.startswith("/media/"):
            file_relative = url[len("/media/"):].lstrip("/")
            abs_path = os.path.join(DATA_DIR, file_relative.replace("/", os.sep))
            removable_roots = [
                os.path.abspath(VIDEO_RECOMMENDATION_CACHE_DIR),
                os.path.abspath(VIDEO_DIR),
            ]
        else:
            return

        abs_path = os.path.abspath(abs_path)
        in_allowed_root = False
        for root in removable_roots:
            try:
                if os.path.commonpath([root, abs_path]) == root:
                    in_allowed_root = True
                    break
            except ValueError:
                continue
        if not in_allowed_root:
            return

        if not os.path.exists(abs_path):
            return

        try:
            if os.path.isfile(abs_path):
                os.remove(abs_path)

            candidate_asset_dir = os.path.dirname(abs_path)
            if os.path.basename(candidate_asset_dir).lower() in {"hls", "thumbs"}:
                candidate_asset_dir = os.path.dirname(candidate_asset_dir)

            candidate_abs = os.path.abspath(candidate_asset_dir)
            if os.path.isdir(candidate_abs):
                for root in removable_roots:
                    try:
                        common = os.path.commonpath([root, candidate_abs])
                    except ValueError:
                        continue
                    if common != root:
                        continue

                    relative = os.path.relpath(candidate_abs, root)
                    # Keep root and first-level platform/source directories.
                    if relative in (".", "") or os.sep not in relative:
                        continue
                    shutil.rmtree(candidate_abs, ignore_errors=True)
                    break

            app_logger.info(f"已删除预览资源文件: {abs_path}")
        except Exception as e:
            error_logger.error(f"删除预览资源文件失败: {abs_path}, error={e}")

    def _build_image_request_headers(self, image_url: str, video_id: str = "") -> Dict[str, str]:
        return self._build_protocol_asset_headers(
            image_url,
            asset_kind="image",
            video_id=video_id,
        )

    def _download_image_content(self, image_url: str, video_id: str = "") -> Optional[bytes]:
        resolved_url = self._resolve_proxy_source_url(image_url) or str(image_url or "").strip()
        resolved_url = self._normalize_protocol_asset_url(
            resolved_url,
            asset_kind="image",
            video_id=video_id,
        )

        lowered = resolved_url.lower()
        if not (lowered.startswith("http://") or lowered.startswith("https://")):
            app_logger.warning(f"图片URL无效，跳过下载: url={image_url}")
            return None

        headers = self._build_image_request_headers(resolved_url, video_id)
        response = None
        try:
            response = self._request_preview_url(
                resolved_url,
                headers=headers,
                stream=False,
                timeout=0,
                allow_redirects=True,
            )
            if response.status_code != 200:
                app_logger.warning(f"下载图片失败: url={resolved_url}, status={response.status_code}")
                return None

            content_type = (response.headers.get("content-type", "") or "").lower()
            if "image" not in content_type:
                app_logger.warning(f"下载内容不是图片: url={resolved_url}, content-type={content_type}")
                return None

            return response.content
        finally:
            if response is not None:
                try:
                    response.close()
                except Exception:
                    pass
    
    def batch_move_to_trash(self, video_ids: List[str]) -> ServiceResult:
        """批量移动视频到回收站"""
        try:
            if hasattr(self._video_repo, "update_many_by_ids"):
                updated_count = self._video_repo.update_many_by_ids(
                    video_ids,
                    lambda video: video.move_to_trash(),
                )
            else:
                updated_count = 0
                for video_id in video_ids:
                    video = self._video_repo.get_by_id(video_id)
                    if video:
                        video.move_to_trash()
                        if self._video_repo.save(video):
                            updated_count += 1
            
            if updated_count == 0:
                return ServiceResult.error("没有找到有效视频")
            
            app_logger.info(f"批量移入回收站成功: {updated_count}个视频")
            return ServiceResult.ok({"updated_count": updated_count}, f"已将{updated_count}个视频移入回收站")
        except Exception as e:
            error_logger.error(f"批量移入回收站失败: {e}")
            return ServiceResult.error("批量移入回收站失败")
    
    def batch_restore_from_trash(self, video_ids: List[str]) -> ServiceResult:
        """批量从回收站恢复视频"""
        try:
            if hasattr(self._video_repo, "update_many_by_ids"):
                updated_count = self._video_repo.update_many_by_ids(
                    video_ids,
                    lambda video: video.restore_from_trash(),
                )
            else:
                updated_count = 0
                for video_id in video_ids:
                    video = self._video_repo.get_by_id(video_id)
                    if video:
                        video.restore_from_trash()
                        if self._video_repo.save(video):
                            updated_count += 1
            
            if updated_count == 0:
                return ServiceResult.error("没有找到有效视频")
            
            app_logger.info(f"批量从回收站恢复成功: {updated_count}个视频")
            return ServiceResult.ok({"updated_count": updated_count}, f"已恢复 {updated_count} 个视频")
        except Exception as e:
            error_logger.error(f"批量从回收站恢复失败: {e}")
            return ServiceResult.error("批量从回收站恢复失败")
    
    def batch_delete_permanently(self, video_ids: List[str]) -> ServiceResult:
        """批量永久删除视频"""
        try:
            if hasattr(self._video_repo, "get_many_by_ids") and hasattr(self._video_repo, "delete_many_by_ids"):
                for video in self._video_repo.get_many_by_ids(video_ids):
                    self._cleanup_video_files(video)
                deleted_count = self._video_repo.delete_many_by_ids(video_ids)
            else:
                deleted_count = 0
                for video_id in video_ids:
                    video = self._video_repo.get_by_id(video_id)
                    if video:
                        self._cleanup_video_files(video)
                    if self._video_repo.delete(video_id):
                        deleted_count += 1
            
            if deleted_count == 0:
                return ServiceResult.error("没有找到有效视频")
            
            app_logger.info(f"批量永久删除成功: {deleted_count}个视频")
            return ServiceResult.ok({"deleted_count": deleted_count}, f"已永久删除 {deleted_count} 个视频")
        except Exception as e:
            error_logger.error(f"批量永久删除失败: {e}")
            return ServiceResult.error("批量永久删除失败")
    
    def batch_import_videos(self, videos_data: List[Dict]) -> ServiceResult:
        try:
            items = [item for item in (videos_data or []) if isinstance(item, dict)]
            if not items:
                return ServiceResult.ok({
                    "imported": [],
                    "imported_ids": [],
                    "skipped": [],
                    "imported_count": 0,
                    "skipped_count": 0,
                    "failed_items": [],
                    "failed_count": 0,
                })

            skipped = []
            import_candidates = []

            local_video_cache = self._build_local_video_duplicate_cache()
            for video_data in items:
                code = video_data.get("code", "")
                normalized_code = self._normalize_code_for_storage(code)
                if self._find_local_video_duplicate_entity(
                    str(video_data.get("id") or "").strip(),
                    normalized_code,
                    local_video_cache=local_video_cache,
                ):
                    skipped.append(code)
                    continue
                import_candidates.append(video_data)

            imported = []
            imported_ids = []
            failed_items = []
            if import_candidates:
                result = self.import_videos(import_candidates, local_video_cache=local_video_cache)
                if not result.success:
                    return result
                saved_videos = (result.data or {}).get("videos") or []
                failed_items = (result.data or {}).get("failed_items") or []
                for video in saved_videos:
                    if not isinstance(video, dict):
                        continue
                    imported.append(video.get("code", ""))
                    if video.get("id"):
                        imported_ids.append(video["id"])
            
            return ServiceResult.ok({
                "imported": imported,
                "imported_ids": imported_ids,
                "skipped": skipped,
                "imported_count": len(imported),
                "skipped_count": len(skipped),
                "failed_items": failed_items,
                "failed_count": len(failed_items),
            })
        except Exception as e:
            error_logger.error(f"批量导入视频失败: {e}")
            return ServiceResult.error("批量导入失败")
