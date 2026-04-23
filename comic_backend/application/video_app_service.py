"""
视频应用服务
Mmmtttt
"""

from typing import List, Dict, Optional, Any, Tuple
import base64
import os
import re
import shutil
import threading
import requests
from io import BytesIO
from urllib.parse import urlparse, urljoin, unquote
from PIL import Image

from domain.video import Video, VideoRepository
from domain.video_recommendation import VideoRecommendationRepository, VideoRecommendation
from domain.tag import Tag, TagRepository
from domain.actor import ActorSubscription, ActorRepository
from infrastructure.persistence.repositories.video_repository_impl import VideoJsonRepository
from infrastructure.persistence.repositories.video_recommendation_repository_impl import VideoRecommendationJsonRepository
from infrastructure.persistence.repositories.tag_repository_impl import TagJsonRepository
from infrastructure.persistence.repositories.actor_repository_impl import ActorJsonRepository
from infrastructure.persistence.cache import CacheManager
from infrastructure.common.result import ServiceResult
from infrastructure.logger import app_logger, error_logger
from core.utils import get_current_time, generate_id, generate_uuid
from core.constants import (
    DATA_DIR,
    STATIC_DIR,
    VIDEO_CACHE_DIR,
    VIDEO_DIR,
    VIDEO_RECOMMENDATION_CACHE_DIR,
)
from core.enums import ContentType
from application.base.content_app_service import BaseContentAppService
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
    SOURCE_ORIGIN_LOCAL_IMPORT = "local_import"
    SOURCE_ORIGIN_MAGNET_DOWNLOAD = "magnet_download"
    VIDEO_FILE_EXTENSIONS = (
        ".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm",
        ".m4v", ".ts", ".m2ts", ".rmvb", ".mpg", ".mpeg",
    )
    ARCHIVE_FILE_EXTENSIONS = (".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz")
    CODE_PATTERN = re.compile(r"(?<![A-Za-z0-9])([A-Za-z]{2,7})[\s_-]?([0-9]{2,4})(?![A-Za-z0-9])")
    FC2_PATTERN = re.compile(
        r"(?i)(?:^|[^a-z0-9])(fc2)\s*[-_ ]?\s*(?:ppv\s*[-_ ]?)?([0-9]{4,8})(?:$|[^a-z0-9])"
    )
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

    def _get_repo_by_source(self, source: str = "local"):
        return self._video_rec_repo if source == "preview" else self._video_repo

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

        video_id = str(raw.get("id") or "").strip()
        context = cls._resolve_video_protocol_context(video_id=video_id, platform_name=explicit_platform)
        resolved_platform = str(context.get("platform_name") or "").strip().lower()
        if resolved_platform and resolved_platform != "local":
            return resolved_platform

        return ""

    @classmethod
    def _annotate_video_record(cls, video_data: Dict[str, Any]) -> Dict[str, Any]:
        raw = dict(video_data or {})
        platform_name = cls._resolve_video_annotation_platform_name(raw)
        if not platform_name:
            return raw
        return annotate_item(raw, platform_name=platform_name, media_type="video")

    @classmethod
    def _annotate_video_records(cls, video_records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [
            cls._annotate_video_record(item)
            for item in (video_records or [])
            if isinstance(item, dict)
        ]

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
            if clear_previous:
                for video in repo.get_all():
                    if tag_id in (video.tag_ids or []):
                        video.remove_tags([tag_id])
                        if repo.save(video):
                            cleared_count += 1

            updated_count = 0
            for video_id in target_ids:
                video = repo.get_by_id(video_id)
                if not video:
                    continue
                if tag_id in (video.tag_ids or []):
                    continue
                video.add_tags([tag_id])
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
    
    def get_video_list(
        self,
        sort_type: str = "create_time",
        min_score: float = None,
        max_score: float = None,
        include_deleted: bool = False
    ) -> ServiceResult:
        try:
            videos = self._video_repo.get_all()
            tags = self._tag_repo.get_all()
            tag_map = {t.id: t.name for t in tags}
            
            if not include_deleted:
                videos = [v for v in videos if not v.is_deleted]
            
            if min_score is not None:
                videos = [v for v in videos if v.score is not None and v.score >= min_score]
            if max_score is not None:
                videos = [v for v in videos if v.score is not None and v.score <= max_score]
            
            if sort_type == "create_time":
                videos = sorted(videos, key=lambda v: v.create_time or "", reverse=True)
            elif sort_type == "score":
                videos = sorted(videos, key=lambda v: v.score or 0, reverse=True)
            elif sort_type == "access_time":
                videos = sorted(videos, key=lambda v: v.last_access_time or "", reverse=True)
            elif sort_type == "date":
                videos = sorted(videos, key=lambda v: v.date or "", reverse=True)
            
            video_list = []
            for v in videos:
                video_info = v.to_dict()
                video_info["tags"] = [{"id": tid, "name": tag_map.get(tid, tid)} for tid in v.tag_ids]
                video_list.append(video_info)
            video_list = self._annotate_video_records(video_list)
            
            app_logger.info(f"获取视频列表成功，共 {len(video_list)} 个视频")
            return ServiceResult.ok(video_list)
        except Exception as e:
            error_logger.error(f"获取视频列表失败: {e}")
            return ServiceResult.error("获取视频列表失败")
    
    def get_video_detail(self, video_id: str) -> ServiceResult:
        try:
            video = self._video_repo.get_by_id(video_id)
            if not video:
                return ServiceResult.error("视频不存在")
            
            tags = self._tag_repo.get_all()
            tag_map = {t.id: t.name for t in tags}
            
            detail = video.to_dict()
            detail["tags"] = [{"id": tid, "name": tag_map.get(tid, tid)} for tid in video.tag_ids]
            detail["source"] = "local"
            detail["storage_path"] = self._resolve_video_storage_path(video)
            detail = self._annotate_video_record(detail)
            
            app_logger.info(f"获取视频详情成功: {video_id}")
            return ServiceResult.ok(detail)
        except Exception as e:
            error_logger.error(f"获取视频详情失败: {e}")
            return ServiceResult.error("获取视频详情失败")
    
    def _resolve_video_storage_path(self, video: Video) -> str:
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

    @staticmethod
    def _build_local_stream_url(video_id: str) -> str:
        safe_id = str(video_id or "").strip()
        return f"/api/v1/video/local-stream/{safe_id}" if safe_id else ""

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

    def import_local_videos_from_path(self, source_path: str, import_mode: str = "") -> ServiceResult:
        try:
            source_dir = os.path.abspath(os.path.expandvars(os.path.expanduser(str(source_path or "").strip())))
            if not source_dir:
                return ServiceResult.error("source_path is required")
            if not os.path.exists(source_dir):
                return ServiceResult.error("source_path does not exist")
            if not os.path.isdir(source_dir):
                return ServiceResult.error("source_path must be a directory")
            normalized_mode = self.normalize_local_import_mode(import_mode)

            scanned_files = 0
            scanned_video_files = 0
            imported_count = 0
            attached_source_count = 0
            skipped_count = 0
            failed_count = 0
            imported_ids: List[str] = []
            skipped_items: List[Dict[str, str]] = []
            failed_items: List[Dict[str, str]] = []

            for root, _, files in os.walk(source_dir):
                for filename in files:
                    scanned_files += 1
                    abs_file_path = os.path.join(root, filename)

                    if self._is_archive_file_path(filename):
                        skipped_count += 1
                        skipped_items.append({"file": abs_file_path, "reason": "archive_ignored"})
                        continue
                    if not self._is_video_file_path(filename):
                        continue

                    scanned_video_files += 1

                    target_dir = ""
                    target_file = ""
                    source_restore_path = ""
                    try:
                        stem, ext = os.path.splitext(filename)
                        normalized_ext = ext.lower() if ext else ".mp4"
                        code = self._extract_or_generate_code(stem)
                        duplicate_video = self._find_local_video_duplicate_entity("", code)
                        bind_existing_video = None
                        if duplicate_video:
                            if self._is_local_video_id(duplicate_video.id):
                                skipped_count += 1
                                skipped_items.append(
                                    {
                                        "file": abs_file_path,
                                        "reason": "duplicate_local_import",
                                        "duplicate_id": duplicate_video.id,
                                        "code": code,
                                    }
                                )
                                continue

                            if self._has_video_source_file(duplicate_video):
                                skipped_count += 1
                                skipped_items.append(
                                    {
                                        "file": abs_file_path,
                                        "reason": "duplicate_code_source_exists",
                                        "duplicate_id": duplicate_video.id,
                                        "code": code,
                                    }
                                )
                                continue

                            bind_existing_video = duplicate_video

                        video_id = str(getattr(bind_existing_video, "id", "") or "").strip() or self._generate_local_video_id()
                        if normalized_mode == self.LOCAL_IMPORT_MODE_HARDLINK_MOVE:
                            preferred_dir_name = ""
                            if bind_existing_video:
                                preferred_dir_name = str(
                                    getattr(bind_existing_video, "local_asset_dir_name", "") or ""
                                ).strip()
                                if not preferred_dir_name:
                                    existing_asset_dir = self._resolve_explicit_video_local_asset_dir(bind_existing_video)
                                    if existing_asset_dir:
                                        preferred_dir_name = os.path.basename(existing_asset_dir)

                            target_dir, target_file, local_asset_dir_name, local_source_filename = (
                                self._build_local_source_file_target(
                                    video_id,
                                    filename,
                                    preferred_dir_name=preferred_dir_name,
                                )
                            )
                            source_restore_path = abs_file_path
                            shutil.move(abs_file_path, target_file)

                            local_video_path = self._to_media_url(target_file)
                            if not local_video_path:
                                raise RuntimeError("failed to map local video path")
                            local_source_path = os.path.abspath(target_file)
                        else:
                            local_video_path = self._build_local_stream_url(video_id)
                            local_source_path = os.path.abspath(abs_file_path)
                            local_asset_dir_name = str(
                                getattr(bind_existing_video, "local_asset_dir_name", "") or ""
                            ).strip() if bind_existing_video else ""
                            local_source_filename = self._resolve_video_source_filename(
                                bind_existing_video,
                                default_extension=normalized_ext,
                            ) if bind_existing_video else os.path.basename(abs_file_path)
                            if not local_video_path:
                                raise RuntimeError("failed to build local stream path")

                        if bind_existing_video:
                            existing_video = self._video_repo.get_by_id(video_id) or bind_existing_video
                            existing_video.local_video_path = local_video_path
                            existing_video.local_source_path = local_source_path
                            existing_video.local_asset_dir_name = local_asset_dir_name
                            existing_video.local_source_filename = local_source_filename
                            existing_video.source_origin = self.SOURCE_ORIGIN_LOCAL_IMPORT
                            existing_video.source_updated_time = get_current_time()

                            if not self._video_repo.save(existing_video):
                                raise RuntimeError("save local source on existing video failed")

                            imported_count += 1
                            attached_source_count += 1
                            imported_ids.append(video_id)
                            continue

                        payload = {
                            "id": video_id,
                            "title": stem.strip() or filename,
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
                            "local_video_path": local_video_path,
                            "local_source_path": local_source_path,
                            "local_asset_dir_name": local_asset_dir_name,
                            "local_source_filename": local_source_filename,
                            "source_origin": self.SOURCE_ORIGIN_LOCAL_IMPORT,
                            "source_updated_time": get_current_time(),
                            "local_metadata_enriched": False,
                        }

                        result = self.import_video(payload)
                        if not result.success:
                            failed_count += 1
                            failed_items.append(
                                {
                                    "file": abs_file_path,
                                    "reason": result.message or "import_failed",
                                    "code": code,
                                }
                            )
                            try:
                                if (
                                    normalized_mode == self.LOCAL_IMPORT_MODE_HARDLINK_MOVE
                                    and source_restore_path
                                    and target_file
                                    and os.path.exists(target_file)
                                ):
                                    os.makedirs(os.path.dirname(source_restore_path), exist_ok=True)
                                    shutil.move(target_file, source_restore_path)
                                if os.path.isdir(target_dir):
                                    shutil.rmtree(target_dir, ignore_errors=True)
                            except Exception:
                                pass
                            continue

                        imported_count += 1
                        imported_ids.append(video_id)
                    except Exception as item_error:
                        try:
                            if (
                                normalized_mode == self.LOCAL_IMPORT_MODE_HARDLINK_MOVE
                                and source_restore_path
                                and target_file
                                and os.path.exists(target_file)
                            ):
                                os.makedirs(os.path.dirname(source_restore_path), exist_ok=True)
                                shutil.move(target_file, source_restore_path)
                            if target_dir and os.path.isdir(target_dir):
                                shutil.rmtree(target_dir, ignore_errors=True)
                        except Exception:
                            pass
                        failed_count += 1
                        failed_items.append({"file": abs_file_path, "reason": str(item_error)})

            if imported_ids:
                recent_result = self.apply_recent_import_tags(imported_ids, source="local", clear_previous=True)
                if not recent_result.success:
                    app_logger.warning(
                        f"update recent import tags failed after local video import: {recent_result.message}"
                    )

            mode_label = "软连接（保留源文件）" if normalized_mode == self.LOCAL_IMPORT_MODE_SOFTLINK_REF else "硬链接（移动源文件）"
            summary = (
                f"本地视频导入完成（{mode_label}）："
                f"扫描 {scanned_video_files} 个视频，"
                f"成功 {imported_count}（其中补齐source {attached_source_count}），跳过 {skipped_count}，失败 {failed_count}"
            )
            return ServiceResult.ok(
                {
                    "source_path": source_dir,
                    "import_mode": normalized_mode,
                    "scanned_files": scanned_files,
                    "scanned_video_files": scanned_video_files,
                    "imported_count": imported_count,
                    "attached_source_count": attached_source_count,
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

    def resolve_local_video_file_path(self, video_id: str) -> Optional[str]:
        video = self._video_repo.get_by_id(str(video_id or "").strip())
        if not video:
            return None

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

    def import_video(self, video_data: Dict) -> ServiceResult:
        try:
            incoming_id = str(video_data.get("id") or "").strip()
            incoming_code = self._normalize_code_for_storage(video_data.get("code"))
            duplicate_id = self._find_local_video_duplicate(incoming_id, incoming_code)
            if duplicate_id and duplicate_id != incoming_id:
                return ServiceResult.error("该番号已存在")

            video = Video(
                id=incoming_id or generate_id("video"),
                title=video_data.get("title", ""),
                code=incoming_code,
                date=video_data.get("date", ""),
                series=video_data.get("series", ""),
                creator=video_data.get("creator", ""),
                desc=video_data.get("desc", ""),
                score=video_data.get("score"),
                tag_ids=video_data.get("tag_ids", []),
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
                create_time=get_current_time(),
                last_access_time=get_current_time()
            )
            video.actors = video_data.get("actors", [])
            video.list_ids = video_data.get("list_ids", [])

            if not self._video_repo.save(video):
                return ServiceResult.error("保存视频失败")
            
            app_logger.info(f"导入视频成功: {video.code}")
            return ServiceResult.ok(video.to_dict(), "导入成功")
        except Exception as e:
            error_logger.error(f"导入视频失败: {e}")
            return ServiceResult.error("导入失败")
    
    @staticmethod
    def _normalize_code_for_compare(code: str) -> str:
        raw = str(code or "").upper()
        return "".join(ch for ch in raw if ch.isalnum())

    def _find_local_video_duplicate_entity(self, video_id: str, code: str) -> Optional[Video]:
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

    def _find_local_video_duplicate(self, video_id: str, code: str) -> Optional[str]:
        duplicate_video = self._find_local_video_duplicate_entity(video_id, code)
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
            from infrastructure.persistence.json_storage import JsonStorage
            from core.constants import VIDEO_JSON_FILE, VIDEO_RECOMMENDATION_JSON_FILE

            home_storage = JsonStorage(VIDEO_JSON_FILE)
            recommendation_storage = JsonStorage(VIDEO_RECOMMENDATION_JSON_FILE)

            home_data = home_storage.read()
            recommendation_data = recommendation_storage.read()

            home_records = home_data.get("videos", [])
            if not isinstance(home_records, list):
                home_records = []
                home_data["videos"] = home_records

            recommendation_records = recommendation_data.get("video_recommendations", [])
            if not isinstance(recommendation_records, list):
                recommendation_records = []
                recommendation_data["video_recommendations"] = recommendation_records

            home_stats = self._deduplicate_video_collection(home_records)
            recommendation_stats = self._deduplicate_video_collection(recommendation_records)

            if not home_storage.write(home_data):
                return ServiceResult.error("failed to write local video database")
            if not recommendation_storage.write(recommendation_data):
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

    def migrate_recommendations_to_local(self, video_ids: List[str]) -> ServiceResult:
        try:
            if not video_ids:
                return ServiceResult.error("video_ids is required")

            imported_count = 0
            skipped_count = 0
            failed_count = 0
            imported_ids = []
            skipped_items = []
            failed_items = []

            for video_id in video_ids:
                try:
                    recommendation_video = self._video_rec_repo.get_by_id(video_id)
                    if not recommendation_video or recommendation_video.is_deleted:
                        skipped_count += 1
                        skipped_items.append({
                            "id": video_id,
                            "reason": "not_found_or_deleted"
                        })
                        continue

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
                    )
                    local_video.actors = list(recommendation_video.actors or [])

                    assets_result = self._migrate_recommendation_assets_to_local(recommendation_video, local_video)
                    if not assets_result.get("success"):
                        failed_count += 1
                        failed_items.append({
                            "id": video_id,
                            "reason": assets_result.get("reason", "asset_migrate_failed")
                        })
                        continue

                    if not self._video_repo.save(local_video):
                        failed_count += 1
                        failed_items.append({
                            "id": video_id,
                            "reason": "save_local_failed"
                        })
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
                except Exception as item_error:
                    failed_count += 1
                    failed_items.append({
                        "id": video_id,
                        "reason": str(item_error)
                    })
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
            for tag_id in tag_ids:
                if not self._tag_repo.get_by_id(tag_id):
                    return ServiceResult.error(f"标签不存在: {tag_id}")
            
            video = self._video_repo.get_by_id(video_id)
            if not video:
                return ServiceResult.error("视频不存在")
            
            video.bind_tags(tag_ids)
            
            if not self._video_repo.save(video):
                return ServiceResult.error("绑定标签失败")
            
            app_logger.info(f"绑定视频标签成功: {video_id}, 标签: {tag_ids}")
            return ServiceResult.ok({"video_id": video_id, "tag_ids": tag_ids}, "标签绑定成功")
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
            for tag_id in tag_ids:
                if not self._tag_repo.get_by_id(tag_id):
                    return ServiceResult.error(f"标签不存在: {tag_id}")
            
            updated_count = 0
            for video_id in video_ids:
                video = self._video_repo.get_by_id(video_id)
                if video:
                    video.add_tags(tag_ids)
                    if self._video_repo.save(video):
                        updated_count += 1
            
            if updated_count == 0:
                return ServiceResult.error("没有找到有效视频")
            
            app_logger.info(f"批量添加标签成功: {updated_count}个视频, 标签: {tag_ids}")
            return ServiceResult.ok({"updated_count": updated_count, "tag_ids": tag_ids}, f"成功为 {updated_count} 个视频添加标签")
        except Exception as e:
            error_logger.error(f"批量添加标签失败: {e}")
            return ServiceResult.error("批量添加标签失败")
    
    def batch_remove_tags(self, video_ids: List[str], tag_ids: List[str]) -> ServiceResult:
        try:
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
            imported = []
            imported_ids = []
            skipped = []
            
            for video_data in videos_data:
                code = video_data.get("code", "")
                if self._video_repo.get_by_code(code):
                    skipped.append(code)
                    continue
                
                result = self.import_video(video_data)
                if result.success:
                    imported.append(code)
                    if result.data and result.data.get("id"):
                        imported_ids.append(result.data["id"])
            
            return ServiceResult.ok({
                "imported": imported,
                "imported_ids": imported_ids,
                "skipped": skipped,
                "imported_count": len(imported),
                "skipped_count": len(skipped)
            })
        except Exception as e:
            error_logger.error(f"批量导入视频失败: {e}")
            return ServiceResult.error("批量导入失败")

