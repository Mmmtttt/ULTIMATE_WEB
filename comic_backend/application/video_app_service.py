"""
视频应用服务
"""

from typing import List, Dict, Optional
import base64
import os
import re
import shutil
import threading
import json
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
from core.utils import get_current_time, generate_id
from core.constants import VIDEO_COVER_DIR, VIDEO_CACHE_DIR, JAV_PICTURES_DIR, JAV_COVER_DIR, STATIC_DIR
from core.enums import ContentType
from application.base.content_app_service import BaseContentAppService


class VideoAppService(BaseContentAppService):
    _entity_name = "视频"
    _cache_manager = CacheManager()
    RECENT_IMPORT_TAG_ID = "tag_video_recent_import"
    RECENT_IMPORT_TAG_NAME = "最近导入"
    PREVIEW_VIDEO_DIR_NAME = "preview_video"
    PREVIEW_ASSET_COVER_NAME = "cover.jpg"
    PREVIEW_VIDEO_MAX_BYTES = 180 * 1024 * 1024
    PREVIEW_VIDEO_EXTENSIONS = (".mp4", ".webm", ".mov", ".m4v", ".m3u8")
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

        error_logger.error("������Ƶ��������ǩʧ��")
        return None

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
                }, "���������������ǩ")

            tag_id = self._ensure_recent_import_tag_id()
            if not tag_id:
                return ServiceResult.error("������������ǩʧ��")

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
                f"更新视频最近导入标签完�? source={source}, tag_id={tag_id}, "
                f"cleared={cleared_count}, updated={updated_count}"
            )
            return ServiceResult.ok({
                "tag_id": tag_id,
                "updated_count": updated_count,
                "cleared_count": cleared_count
            }, "������������ǩ�ɹ�")
        except Exception as e:
            error_logger.error(f"更新视频最近导入标签失�? {e}")
            return ServiceResult.error("������������ǩʧ��")
    
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
            
            app_logger.info(f"��ȡ��Ƶ�б�ɹ����� {len(video_list)} ����Ƶ")
            return ServiceResult.ok(video_list)
        except Exception as e:
            error_logger.error(f"获取视频列表失败: {e}")
            return ServiceResult.error("获取视频列表失败")
    
    def get_video_detail(self, video_id: str) -> ServiceResult:
        try:
            video = self._video_repo.get_by_id(video_id)
            if not video:
                return ServiceResult.error("��Ƶ������")
            
            tags = self._tag_repo.get_all()
            tag_map = {t.id: t.name for t in tags}
            
            detail = video.to_dict()
            detail["tags"] = [{"id": tid, "name": tag_map.get(tid, tid)} for tid in video.tag_ids]
            detail["source"] = "local"
            
            app_logger.info(f"获取视频详情成功: {video_id}")
            return ServiceResult.ok(detail)
        except Exception as e:
            error_logger.error(f"获取视频详情失败: {e}")
            return ServiceResult.error("获取视频详情失败")
    
    def get_video_by_code(self, code: str) -> ServiceResult:
        try:
            video = self._video_repo.get_by_code(code)
            if not video:
                return ServiceResult.error("��Ƶ������")
            return ServiceResult.ok(video.to_dict())
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
            
            app_logger.info(f"搜索成功: 关键�?'{keyword}', 结果数量: {len(results)}")
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
                return ServiceResult.error("��Ƶ������")
            
            self._cleanup_video_files(video)
            
            success = self._video_repo.delete(video_id)
            if success:
                app_logger.info(f"视频已永久删�? {video_id}")
                return ServiceResult.ok({"message": "��Ƶ������ɾ��"})
            return ServiceResult.error("删除失败")
        except Exception as e:
            error_logger.error(f"永久删除视频失败: {e}")
            return ServiceResult.error("删除失败")
    
    def _cleanup_video_files(self, video):
        """������Ƶ��ص������ļ�"""
        from core.constants import COVER_DIR
        
        if video.cover_path:
            relative_path = video.cover_path.lstrip('/')
            if relative_path.startswith('static/cover/'):
                relative_path = relative_path.replace('static/cover/', '', 1)
            
            cover_path_full = os.path.join(COVER_DIR, relative_path)
            if os.path.exists(cover_path_full):
                try:
                    os.remove(cover_path_full)
                    app_logger.info(f"已删除视频封�? {cover_path_full}")
                except Exception as e:
                    error_logger.error(f"删除视频封面失败: {e}")
        
        jav_cover_path = os.path.join(JAV_COVER_DIR, f"{video.id}.jpg")
        if os.path.exists(jav_cover_path):
            try:
                os.remove(jav_cover_path)
                app_logger.info(f"已删除视频封�? {jav_cover_path}")
            except Exception as e:
                error_logger.error(f"删除视频封面失败: {e}")
        
        video_dir = os.path.join(JAV_PICTURES_DIR, video.id)
        if os.path.exists(video_dir):
            try:
                shutil.rmtree(video_dir)
                app_logger.info(f"已删除视频目�? {video_dir}")
            except Exception as e:
                error_logger.error(f"删除视频目录失败: {e}")

        self._remove_preview_video_file(getattr(video, "cover_path", ""))
        self._remove_preview_video_file(getattr(video, "preview_video", ""))
        for thumb_url in getattr(video, "thumbnail_images", []) or []:
            self._remove_preview_video_file(thumb_url)
    
    def delete_recommendation_assets(
        self,
        video_id: str,
        preview_video: str = "",
        cover_path: str = "",
        thumbnail_images: Optional[List[str]] = None,
    ):
        jav_cover_path = os.path.join(JAV_COVER_DIR, f"{video_id}.jpg")
        if os.path.exists(jav_cover_path):
            try:
                os.remove(jav_cover_path)
            except Exception as e:
                error_logger.error(f"删除推荐视频封面失败: {e}")
        
        video_dir = os.path.join(JAV_PICTURES_DIR, video_id)
        if os.path.exists(video_dir):
            try:
                shutil.rmtree(video_dir)
            except Exception as e:
                error_logger.error(f"删除推荐视频目录失败: {e}")

        if preview_video:
            self._remove_preview_video_file(preview_video)
        if cover_path:
            self._remove_preview_video_file(cover_path)
        for thumb_url in thumbnail_images or []:
            self._remove_preview_video_file(thumb_url)
    
    def import_video(self, video_data: Dict) -> ServiceResult:
        try:
            existing = self._video_repo.get_by_code(video_data.get("code", ""))
            if existing:
                return ServiceResult.error("该番号已存在")
            
            video = Video(
                id=video_data.get("id") or generate_id("video"),
                title=video_data.get("title", ""),
                code=video_data.get("code", ""),
                date=video_data.get("date", ""),
                series=video_data.get("series", ""),
                creator=video_data.get("creator", ""),
                desc=video_data.get("desc", ""),
                score=video_data.get("score"),
                tag_ids=video_data.get("tag_ids", []),
                magnets=video_data.get("magnets", []),
                thumbnail_images=video_data.get("thumbnail_images", []),
                preview_video=video_data.get("preview_video", ""),
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

    def _find_local_video_duplicate(self, video_id: str, code: str) -> Optional[str]:
        if video_id and self._video_repo.get_by_id(video_id):
            return video_id

        normalized_code = self._normalize_code_for_compare(code)
        if not normalized_code:
            return None

        for local_video in self._video_repo.get_all():
            if self._normalize_code_for_compare(local_video.code) == normalized_code:
                return local_video.id
        return None

    def _migrate_recommendation_assets_to_local(self, recommendation_video: VideoRecommendation, local_video: Video) -> dict:
        """
        Asset migration extension point.
        For now preview/local video do not persist playable files, so keep as no-op.
        """
        return {
            "success": True,
            "handled": False,
            "strategy": "reserved"
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
                        preview_video=recommendation_video.preview_video or ""
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

                    if local_video.cover_path:
                        self.cache_cover_to_preview_assets_async(
                            local_video.id,
                            local_video.cover_path,
                            source="local"
                        )

                    if local_video.thumbnail_images:
                        self.cache_thumbnail_images_async(
                            local_video.id,
                            local_video.thumbnail_images,
                            source="local"
                        )

                    if local_video.preview_video and not str(local_video.id or "").upper().startswith("JAVBUS"):
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
                f"导入完成：成�?{imported_count}，跳�?{skipped_count}，失�?{failed_count}"
            )
        except Exception as e:
            error_logger.error(f"migrate recommendation videos to local failed: {e}")
            return ServiceResult.error("���뱾�ؿ�ʧ��")

    def get_trash_list(self) -> ServiceResult:
        try:
            videos = self._video_repo.get_all()
            trash_list = [v.to_dict() for v in videos if v.is_deleted]
            return ServiceResult.ok(trash_list)
        except Exception as e:
            error_logger.error(f"获取回收站列表失�? {e}")
            return ServiceResult.error("��ȡ����վʧ��")
    
    def get_videos_by_tag(self, tag_id: str) -> ServiceResult:
        try:
            videos = self._video_repo.get_by_tag(tag_id)
            videos = [v for v in videos if not v.is_deleted]
            return ServiceResult.ok([v.to_dict() for v in videos])
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
            return ServiceResult.ok(filtered)
        except Exception as e:
            error_logger.error(f"获取演员视频失败: {e}")
            return ServiceResult.error("获取视频失败")
    
    def bind_tags(self, video_id: str, tag_ids: List[str]) -> ServiceResult:
        try:
            for tag_id in tag_ids:
                if not self._tag_repo.get_by_id(tag_id):
                    return ServiceResult.error(f"标签不存�? {tag_id}")
            
            video = self._video_repo.get_by_id(video_id)
            if not video:
                return ServiceResult.error("��Ƶ������")
            
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
            return ServiceResult.ok(video.to_dict(), "updated")
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
            
            app_logger.info(f"筛选成�? 包含 {include_tags}, 排除 {exclude_tags}, 结果数量: {len(results)}")
            return ServiceResult.ok(results)
        except Exception as e:
            error_logger.error(f"筛选失�? {e}")
            return ServiceResult.error("ɸѡʧ��")
    
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
            
            app_logger.info(f"筛选成�? 包含 {include_tags}, 排除 {exclude_tags}, 作�?{authors}, 清单 {list_ids}, 结果数量: {len(results)}")
            return ServiceResult.ok(results)
        except Exception as e:
            error_logger.error(f"筛选失�? {e}")
            return ServiceResult.error("ɸѡʧ��")
    
    def batch_add_tags(self, video_ids: List[str], tag_ids: List[str]) -> ServiceResult:
        try:
            for tag_id in tag_ids:
                if not self._tag_repo.get_by_id(tag_id):
                    return ServiceResult.error(f"标签不存�? {tag_id}")
            
            updated_count = 0
            for video_id in video_ids:
                video = self._video_repo.get_by_id(video_id)
                if video:
                    video.add_tags(tag_ids)
                    if self._video_repo.save(video):
                        updated_count += 1
            
            if updated_count == 0:
                return ServiceResult.error("û���ҵ���Ч����Ƶ")
            
            app_logger.info(f"批量添加标签成功: {updated_count}个视�? 标签: {tag_ids}")
            return ServiceResult.ok({"updated_count": updated_count, "tag_ids": tag_ids}, f"�ɹ�Ϊ {updated_count} ����Ƶ��ӱ�ǩ")
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
                return ServiceResult.error("û���ҵ���Ч����Ƶ")
            
            app_logger.info(f"批量移除标签成功: {updated_count}个视�? 标签: {tag_ids}")
            return ServiceResult.ok({"updated_count": updated_count, "tag_ids": tag_ids}, f"�ɹ��� {updated_count} ����Ƶ�Ƴ���ǩ")
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
            return bool(result.data.get("auto_download_preview_assets_for_preview_import", True))
        except Exception as e:
            app_logger.warning(f"读取预览库资源下载配置失败: {e}")
            return True

    def _allow_asset_cache_for_source(self, source_key: str) -> bool:
        if source_key != "preview":
            return True
        return self._is_preview_import_asset_download_enabled()

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

        if lowered.startswith("/static/"):
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

    @staticmethod
    def _load_javdb_cookie_header() -> str:
        try:
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            config_path = os.path.join(project_root, "third_party_config.json")
            if not os.path.exists(config_path):
                return ""

            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)

            cookies = (
                (config.get("adapters") or {})
                .get("javdb", {})
                .get("cookies", {})
            )
            if not isinstance(cookies, dict):
                return ""

            pairs = []
            for key, value in cookies.items():
                key_str = str(key or "").strip()
                if not key_str:
                    continue
                pairs.append(f"{key_str}={str(value or '')}")
            return "; ".join(pairs)
        except Exception:
            return ""

    def _build_preview_video_headers(self, preview_url: str) -> Dict[str, str]:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "*/*",
        }

        parsed = urlparse(preview_url or "")
        host = (parsed.netloc or "").lower()

        if "javdb" in host or "jdbstatic.com" in host:
            headers["Referer"] = "https://javdb.com/"
            cookie_header = self._load_javdb_cookie_header()
            if cookie_header:
                headers["Cookie"] = cookie_header
            return headers

        if parsed.scheme and parsed.netloc:
            headers["Referer"] = f"{parsed.scheme}://{parsed.netloc}/"
        return headers

    def _request_preview_url(
        self,
        url: str,
        headers: Dict[str, str],
        stream: bool = False,
        timeout: int = 30,
        allow_redirects: bool = True,
    ):
        # Prefer Missav client's request stack to reuse curl_cffi impersonation and anti-bot handling.
        try:
            from third_party.missav import get_client

            client = get_client(proxy_base_path="/api/v1/video")
            return client._request(
                "GET",
                url,
                headers=headers,
                stream=stream,
                timeout=timeout,
                allow_redirects=allow_redirects,
                impersonate=getattr(client, "impersonate", "chrome120"),
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
        source_key = self._normalize_preview_source(source)
        safe_video_id = re.sub(r"[^0-9A-Za-z._-]+", "_", str(video_id or "").strip()) or "video"

        source_dir = os.path.join(STATIC_DIR, self.PREVIEW_VIDEO_DIR_NAME, source_key)
        os.makedirs(source_dir, exist_ok=True)

        asset_dir = os.path.join(source_dir, safe_video_id)
        os.makedirs(asset_dir, exist_ok=True)

        relative_dir = f"/static/{self.PREVIEW_VIDEO_DIR_NAME}/{source_key}/{safe_video_id}"
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

    def _download_preview_hls_to_local(self, video_id: str, preview_video_url: str, source: str = "local") -> str:
        source_key = self._normalize_preview_source(source)
        if not self._allow_asset_cache_for_source(source_key):
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
                    timeout=30,
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

                if not self._allow_asset_cache_for_source(source_key):
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
                    timeout=60,
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
                            if not self._allow_asset_cache_for_source(source_key):
                                app_logger.info(f"预览库资源下载已关闭，终止 HLS 写入: id={video_id}")
                                return ""
                            written += len(chunk)
                            downloaded_total += len(chunk)
                            if downloaded_total > self.PREVIEW_VIDEO_MAX_BYTES:
                                app_logger.warning(
                                    f"预览 HLS 资源过大，停止缓�? id={video_id}, bytes={downloaded_total}"
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

    def _download_preview_video_to_local(self, video_id: str, preview_video_url: str, source: str = "local") -> str:
        source_key = self._normalize_preview_source(source)
        if not self._allow_asset_cache_for_source(source_key):
            app_logger.info(f"预览库资源下载已关闭，终止预览视频缓存: id={video_id}")
            return ""

        sanitized_url = self._sanitize_preview_video_url(preview_video_url)
        if not sanitized_url:
            return ""

        resolved_url = self._resolve_proxy_source_url(sanitized_url)
        if resolved_url:
            sanitized_url = resolved_url

        if sanitized_url.startswith("/static/"):
            return sanitized_url

        lowered = sanitized_url.lower()
        if ".m3u8" in lowered:
            return self._download_preview_hls_to_local(video_id, sanitized_url, source=source_key)

        if not (lowered.startswith("http://") or lowered.startswith("https://")):
            return ""

        response = None
        try:
            response = self._request_preview_url(
                sanitized_url,
                headers=self._build_preview_video_headers(sanitized_url),
                stream=True,
                timeout=60,
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
                return self._download_preview_hls_to_local(video_id, final_playlist_url, source=source_key)

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
                    if not self._allow_asset_cache_for_source(source_key):
                        app_logger.info(f"预览库资源下载已关闭，终止预览视频写入: id={video_id}")
                        f.close()
                        try:
                            os.remove(tmp_path)
                        except Exception:
                            pass
                        return ""
                    downloaded_bytes += len(chunk)
                    if downloaded_bytes > self.PREVIEW_VIDEO_MAX_BYTES:
                        app_logger.warning(f"预览视频过大，跳过缓�? id={video_id}, bytes={downloaded_bytes}")
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

    @staticmethod
    def _resolve_static_asset_abs_path(static_url: str) -> str:
        url = str(static_url or "").strip()
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

    def cache_preview_video_async(self, video_id: str, preview_video_url: str, source: str = "local"):
        source_key = self._normalize_preview_source(source)
        if not self._allow_asset_cache_for_source(source_key):
            app_logger.info(f"预览库资源下载已关闭，跳过预览视频缓存: id={video_id}")
            return

        sanitized_url = self._sanitize_preview_video_url(preview_video_url)
        if not video_id or not sanitized_url:
            return

        resolved_url = self._resolve_proxy_source_url(sanitized_url)
        if resolved_url:
            sanitized_url = resolved_url

        if sanitized_url.startswith("/static/"):
            self.update_preview_video(video_id, sanitized_url, source=source_key)
            return

        task_key = f"preview:{source_key}:{video_id}"
        if not self._begin_asset_download(task_key):
            app_logger.info(f"预览视频缓存任务已在进行中: id={video_id}, source={source_key}")
            return

        def download():
            try:
                local_path = self._download_preview_video_to_local(video_id, sanitized_url, source=source_key)
                if not local_path:
                    return
                if self.update_preview_video(video_id, local_path, source=source_key):
                    app_logger.info(f"预览视频缓存成功: id={video_id}, source={source_key}, path={local_path}")
            except Exception as e:
                error_logger.error(f"缓存预览视频失败: id={video_id}, error={e}")
            finally:
                self._end_asset_download(task_key)

        thread = threading.Thread(target=download, daemon=True)
        thread.start()

    def cache_cover_to_preview_assets_async(self, video_id: str, cover_url: str, source: str = "local"):
        source_key = self._normalize_preview_source(source)
        if not self._allow_asset_cache_for_source(source_key):
            app_logger.info(f"预览库资源下载已关闭，跳过封面缓存: id={video_id}")
            return

        target_url = str(cover_url or "").strip()
        if not video_id or not target_url:
            return

        expected_prefix = f"/static/{self.PREVIEW_VIDEO_DIR_NAME}/{source_key}/"
        if target_url.startswith(expected_prefix):
            self.update_cover_path(video_id, target_url, source=source_key)
            return

        task_key = f"cover:{source_key}:{video_id}"
        if not self._begin_asset_download(task_key):
            app_logger.info(f"封面缓存任务已在进行中: id={video_id}, source={source_key}")
            return

        def download():
            tmp_path = ""
            try:
                image_content = self._read_static_asset_bytes(target_url) if target_url.startswith("/static/") else None
                if not image_content:
                    image_content = self._download_image_content(target_url, video_id)
                if not image_content:
                    return

                image = Image.open(BytesIO(image_content))
                abs_path, relative_path = self._build_preview_cover_save_paths(video_id, source_key)
                tmp_path = f"{abs_path}.tmp"
                image.convert("RGB").save(tmp_path, "JPEG", quality=95)
                os.replace(tmp_path, abs_path)
                tmp_path = ""

                if self.update_cover_path(video_id, relative_path, source=source_key):
                    app_logger.info(f"预览资源封面缓存成功: id={video_id}, source={source_key}, path={relative_path}")
            except Exception as e:
                error_logger.error(f"缓存预览资源封面失败: id={video_id}, source={source_key}, error={e}")
            finally:
                if tmp_path and os.path.exists(tmp_path):
                    try:
                        os.remove(tmp_path)
                    except Exception:
                        pass
                self._end_asset_download(task_key)

        thread = threading.Thread(target=download, daemon=True)
        thread.start()

    def cache_thumbnail_images_async(self, video_id: str, thumbnail_images: List[str], source: str = "local"):
        source_key = self._normalize_preview_source(source)
        if not self._allow_asset_cache_for_source(source_key):
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
            expected_prefix = f"/static/{self.PREVIEW_VIDEO_DIR_NAME}/{source_key}/"

            try:
                for idx, raw_url in enumerate(original_images):
                    if not raw_url:
                        continue

                    if raw_url.startswith(expected_prefix):
                        continue

                    image_content = None
                    if raw_url.startswith("/static/"):
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

                if changed and self.update_thumbnail_images(video_id, merged_images, source=source_key):
                    app_logger.info(f"缩略图缓存成功: id={video_id}, source={source_key}")
            except Exception as e:
                error_logger.error(f"缓存缩略图任务失败: id={video_id}, source={source_key}, error={e}")
            finally:
                self._end_asset_download(task_key)

        thread = threading.Thread(target=download, daemon=True)
        thread.start()

    def _remove_preview_video_file(self, preview_video_url: str):
        url = str(preview_video_url or "").strip()
        if not url or not url.startswith("/static/"):
            return

        static_relative = url.lstrip("/")
        prefix = f"static/{self.PREVIEW_VIDEO_DIR_NAME}/"
        if not static_relative.startswith(prefix):
            return

        file_relative = static_relative[len("static/"):]
        abs_path = os.path.join(STATIC_DIR, file_relative.replace("/", os.sep))
        if not os.path.exists(abs_path):
            return

        try:
            if os.path.isfile(abs_path):
                os.remove(abs_path)

            preview_root = os.path.join(STATIC_DIR, self.PREVIEW_VIDEO_DIR_NAME)
            source_local_root = os.path.join(preview_root, "local")
            source_preview_root = os.path.join(preview_root, "preview")

            candidate_asset_dir = os.path.dirname(abs_path)
            if os.path.basename(candidate_asset_dir).lower() == "hls":
                candidate_asset_dir = os.path.dirname(candidate_asset_dir)

            candidate_abs = os.path.abspath(candidate_asset_dir)
            if (
                os.path.isdir(candidate_abs) and
                candidate_abs not in {
                    os.path.abspath(preview_root),
                    os.path.abspath(source_local_root),
                    os.path.abspath(source_preview_root),
                }
            ):
                try:
                    common = os.path.commonpath([os.path.abspath(preview_root), candidate_abs])
                except ValueError:
                    common = ""
                if common == os.path.abspath(preview_root):
                    shutil.rmtree(candidate_abs, ignore_errors=True)

            app_logger.info(f"已删除预览资源文件: {abs_path}")
        except Exception as e:
            error_logger.error(f"删除预览资源文件失败: {abs_path}, error={e}")

    def _build_image_request_headers(self, image_url: str, video_id: str = "") -> Dict[str, str]:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8"
        }

        if image_url and "javbus.com" in image_url.lower():
            from core.platform import remove_platform_prefix
            _, raw_id = remove_platform_prefix(str(video_id or ""))
            referer_id = (raw_id or video_id or "").strip()
            headers["Referer"] = f"https://www.javbus.com/{referer_id}" if referer_id else "https://www.javbus.com/"

        return headers

    def _download_image_content(self, image_url: str, video_id: str = "") -> Optional[bytes]:
        resolved_url = self._resolve_proxy_source_url(image_url) or str(image_url or "").strip()
        if resolved_url.startswith("//"):
            resolved_url = f"https:{resolved_url}"

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
                timeout=30,
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
    
    def download_cover_async(self, video_id: str, cover_url: str):
        def download():
            try:
                if not cover_url:
                    return

                image_content = self._download_image_content(cover_url, video_id)
                if not image_content:
                    return

                image = Image.open(BytesIO(image_content))
                os.makedirs(VIDEO_COVER_DIR, exist_ok=True)
                
                cover_path = os.path.join(VIDEO_COVER_DIR, f"{video_id}.jpg")
                image.convert("RGB").save(cover_path, "JPEG", quality=95)
                
                video = self._video_repo.get_by_id(video_id)
                if video:
                    video.cover_path = f"/static/cover/video/{video_id}.jpg"
                    self._video_repo.save(video)
                
                app_logger.info(f"下载视频封面成功: {video_id}")
            except Exception as e:
                error_logger.error(f"下载视频封面失败: {e}")
        
        thread = threading.Thread(target=download, daemon=True)
        thread.start()
    
    def download_high_quality_thumbnail_async(self, video_id: str, cover_url: str, jav_pictures_dir: str, jav_cover_dir: str):
        """���ظ�����Ƶ����ͼ�� JAV Ŀ¼����ҳ����ʱʹ�ã�"""
        def download():
            try:
                if not cover_url:
                    return
                
                app_logger.info(f"开始下载高清缩略图: {video_id}")

                image_content = self._download_image_content(cover_url, video_id)
                if not image_content:
                    return

                image = Image.open(BytesIO(image_content))
                
                os.makedirs(jav_pictures_dir, exist_ok=True)
                os.makedirs(jav_cover_dir, exist_ok=True)
                
                video_dir = os.path.join(jav_pictures_dir, video_id)
                os.makedirs(video_dir, exist_ok=True)
                
                thumbnail_path = os.path.join(video_dir, "cover.jpg")
                image.convert("RGB").save(thumbnail_path, "JPEG", quality=95)
                
                cover_path = os.path.join(jav_cover_dir, f"{video_id}.jpg")
                image.convert("RGB").save(cover_path, "JPEG", quality=95)
                
                video = self._video_repo.get_by_id(video_id)
                if video:
                    video.cover_path = f"/static/cover/JAV/{video_id}.jpg"
                    self._video_repo.save(video)
                
                app_logger.info(f"下载高清缩略图成�? {video_id}")
            except Exception as e:
                error_logger.error(f"下载高清缩略图失�? {e}")
        
        thread = threading.Thread(target=download, daemon=True)
        thread.start()
    
    def download_cover_async_for_recommendation(self, video_id: str, cover_url: str, jav_cover_dir: str):
        """�����Ƽ�ҳ����"""
        def download():
            try:
                if not cover_url:
                    return

                image_content = self._download_image_content(cover_url, video_id)
                if not image_content:
                    return

                image = Image.open(BytesIO(image_content))
                os.makedirs(jav_cover_dir, exist_ok=True)
                
                cover_path = os.path.join(jav_cover_dir, f"{video_id}.jpg")
                image.convert("RGB").save(cover_path, "JPEG", quality=95)
                
                from domain.video_recommendation.repository import VideoRecommendationRepository
                from infrastructure.persistence.repositories.video_recommendation_repository_impl import VideoRecommendationJsonRepository
                
                video_recommendation_repo = VideoRecommendationJsonRepository()
                video = video_recommendation_repo.get_by_id(video_id)
                if video:
                    video.cover_path = f"/static/cover/JAV/{video_id}.jpg"
                    video_recommendation_repo.save(video)
                
                app_logger.info(f"下载推荐页封面成�? {video_id}")
            except Exception as e:
                error_logger.error(f"下载推荐页封面失�? {e}")
        
        thread = threading.Thread(target=download, daemon=True)
        thread.start()
    
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
                return ServiceResult.error("û���ҵ���Ч����Ƶ")
            
            app_logger.info(f"�����������վ�ɹ�: {updated_count}����Ƶ")
            return ServiceResult.ok({"updated_count": updated_count}, f"已将{updated_count}个视频移入回收站")
        except Exception as e:
            error_logger.error(f"批量移入回收站失�? {e}")
            return ServiceResult.error("�����������վʧ��")
    
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
                return ServiceResult.error("û���ҵ���Ч����Ƶ")
            
            app_logger.info(f"�����ӻ���վ�ָ��ɹ�: {updated_count}����Ƶ")
            return ServiceResult.ok({"updated_count": updated_count}, f"�ѻָ� {updated_count} ����Ƶ")
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
                return ServiceResult.error("û���ҵ���Ч����Ƶ")
            
            app_logger.info(f"��������ɾ���ɹ�: {deleted_count}����Ƶ")
            return ServiceResult.ok({"deleted_count": deleted_count}, f"������ɾ�� {deleted_count} ����Ƶ")
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

