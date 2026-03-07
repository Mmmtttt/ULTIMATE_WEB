"""
视频应用服务
"""

from typing import List, Dict, Optional
import os
import threading
import requests
from io import BytesIO
from PIL import Image

from domain.video import Video, VideoRepository
from domain.tag import Tag, TagRepository
from domain.actor import ActorSubscription, ActorRepository
from infrastructure.persistence.repositories.video_repository_impl import VideoJsonRepository
from infrastructure.persistence.repositories.tag_repository_impl import TagJsonRepository
from infrastructure.persistence.repositories.actor_repository_impl import ActorJsonRepository
from infrastructure.persistence.cache import CacheManager
from infrastructure.common.result import ServiceResult
from infrastructure.logger import app_logger, error_logger
from core.utils import get_current_time, generate_id
from core.constants import VIDEO_COVER_DIR, VIDEO_CACHE_DIR
from application.base.content_app_service import BaseContentAppService


class VideoAppService(BaseContentAppService):
    _entity_name = "视频"
    _cache_manager = CacheManager()
    
    def __init__(
        self,
        video_repo: VideoRepository = None,
        tag_repo: TagRepository = None,
        actor_repo: ActorRepository = None
    ):
        self._video_repo = video_repo or VideoJsonRepository()
        self._tag_repo = tag_repo or TagJsonRepository()
        self._actor_repo = actor_repo or ActorJsonRepository()
    
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
            
            video_list = []
            for v in videos:
                video_info = v.to_dict()
                video_info["tags"] = [{"id": tid, "name": tag_map.get(tid, tid)} for tid in v.tag_ids]
                video_list.append(video_info)
            
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
            
            app_logger.info(f"获取视频详情成功: {video_id}")
            return ServiceResult.ok(detail)
        except Exception as e:
            error_logger.error(f"获取视频详情失败: {e}")
            return ServiceResult.error("获取视频详情失败")
    
    def get_video_by_code(self, code: str) -> ServiceResult:
        try:
            video = self._video_repo.get_by_code(code)
            if not video:
                return ServiceResult.error("视频不存在")
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
            
            app_logger.info(f"搜索成功: 关键词 '{keyword}', 结果数量: {len(results)}")
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
            
            if video.cover_path:
                cover_full_path = video.cover_path.lstrip("/")
                if os.path.exists(cover_full_path):
                    os.remove(cover_full_path)
            
            success = self._video_repo.delete(video_id)
            if success:
                return ServiceResult.ok({"message": "视频已永久删除"})
            return ServiceResult.error("删除失败")
        except Exception as e:
            error_logger.error(f"永久删除视频失败: {e}")
            return ServiceResult.error("删除失败")
    
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
    
    def get_trash_list(self) -> ServiceResult:
        try:
            videos = self._video_repo.get_all()
            trash_list = [v.to_dict() for v in videos if v.is_deleted]
            return ServiceResult.ok(trash_list)
        except Exception as e:
            error_logger.error(f"获取回收站列表失败: {e}")
            return ServiceResult.error("获取回收站失败")
    
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
            
            app_logger.info(f"筛选成功: 包含 {include_tags}, 排除 {exclude_tags}, 结果数量: {len(results)}")
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
                return ServiceResult.error("没有找到有效的视频")
            
            app_logger.info(f"批量添加标签成功: {updated_count}个视频, 标签: {tag_ids}")
            return ServiceResult.ok({"updated_count": updated_count, "tag_ids": tag_ids}, f"成功为{updated_count}个视频添加标签")
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
                return ServiceResult.error("没有找到有效的视频")
            
            app_logger.info(f"批量移除标签成功: {updated_count}个视频, 标签: {tag_ids}")
            return ServiceResult.ok({"updated_count": updated_count, "tag_ids": tag_ids}, f"成功从{updated_count}个视频移除标签")
        except Exception as e:
            error_logger.error(f"批量移除标签失败: {e}")
            return ServiceResult.error("批量移除标签失败")
    
    def download_cover_async(self, video_id: str, cover_url: str):
        def download():
            try:
                if not cover_url:
                    return
                
                response = requests.get(cover_url, timeout=30)
                if response.status_code != 200:
                    return
                
                image = Image.open(BytesIO(response.content))
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
        """下载高清缩略图到JAV目录（主页导入时使用）"""
        def download():
            try:
                if not cover_url:
                    return
                
                app_logger.info(f"开始下载高清缩略图: {video_id}")
                
                response = requests.get(cover_url, timeout=30)
                if response.status_code != 200:
                    app_logger.warning(f"下载高清缩略图失败: HTTP {response.status_code}")
                    return
                
                image = Image.open(BytesIO(response.content))
                
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
                
                app_logger.info(f"下载高清缩略图成功: {video_id}")
            except Exception as e:
                error_logger.error(f"下载高清缩略图失败: {e}")
        
        thread = threading.Thread(target=download, daemon=True)
        thread.start()
    
    def download_cover_async_for_recommendation(self, video_id: str, cover_url: str, jav_cover_dir: str):
        """下载推荐页封面"""
        def download():
            try:
                if not cover_url:
                    return
                
                response = requests.get(cover_url, timeout=30)
                if response.status_code != 200:
                    return
                
                image = Image.open(BytesIO(response.content))
                os.makedirs(jav_cover_dir, exist_ok=True)
                
                cover_path = os.path.join(jav_cover_dir, f"{video_id}.jpg")
                image.convert("RGB").save(cover_path, "JPEG", quality=95)
                
                app_logger.info(f"下载推荐页封面成功: {video_id}")
            except Exception as e:
                error_logger.error(f"下载推荐页封面失败: {e}")
        
        thread = threading.Thread(target=download, daemon=True)
        thread.start()
    
    def batch_import_videos(self, videos_data: List[Dict]) -> ServiceResult:
        try:
            imported = []
            skipped = []
            
            for video_data in videos_data:
                code = video_data.get("code", "")
                if self._video_repo.get_by_code(code):
                    skipped.append(code)
                    continue
                
                result = self.import_video(video_data)
                if result.success:
                    imported.append(code)
            
            return ServiceResult.ok({
                "imported": imported,
                "skipped": skipped,
                "imported_count": len(imported),
                "skipped_count": len(skipped)
            })
        except Exception as e:
            error_logger.error(f"批量导入视频失败: {e}")
            return ServiceResult.error("批量导入失败")
