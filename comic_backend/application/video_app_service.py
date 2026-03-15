"""
视频应用服务
"""

from typing import List, Dict, Optional
import os
import shutil
import threading
import requests
from io import BytesIO
from PIL import Image

from domain.video import Video, VideoRepository
from domain.video_recommendation import VideoRecommendationRepository
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
from core.constants import VIDEO_COVER_DIR, VIDEO_CACHE_DIR, JAV_PICTURES_DIR, JAV_COVER_DIR
from core.enums import ContentType
from application.base.content_app_service import BaseContentAppService


class VideoAppService(BaseContentAppService):
    _entity_name = "视频"
    _cache_manager = CacheManager()
    RECENT_IMPORT_TAG_ID = "tag_video_recent_import"
    RECENT_IMPORT_TAG_NAME = "最近导入"
    
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

        error_logger.error("创建视频最近导入标签失败")
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
            
            self._cleanup_video_files(video)
            
            success = self._video_repo.delete(video_id)
            if success:
                app_logger.info(f"视频已永久删除: {video_id}")
                return ServiceResult.ok({"message": "视频已永久删除"})
            return ServiceResult.error("删除失败")
        except Exception as e:
            error_logger.error(f"永久删除视频失败: {e}")
            return ServiceResult.error("删除失败")
    
    def _cleanup_video_files(self, video):
        """清理视频相关的所有文件"""
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
        
        jav_cover_path = os.path.join(JAV_COVER_DIR, f"{video.id}.jpg")
        if os.path.exists(jav_cover_path):
            try:
                os.remove(jav_cover_path)
                app_logger.info(f"已删除视频封面: {jav_cover_path}")
            except Exception as e:
                error_logger.error(f"删除视频封面失败: {e}")
        
        video_dir = os.path.join(JAV_PICTURES_DIR, video.id)
        if os.path.exists(video_dir):
            try:
                shutil.rmtree(video_dir)
                app_logger.info(f"已删除视频目录: {video_dir}")
            except Exception as e:
                error_logger.error(f"删除视频目录失败: {e}")
    
    def delete_recommendation_assets(self, video_id: str):
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
            
            app_logger.info(f"筛选成功: 包含 {include_tags}, 排除 {exclude_tags}, 作者 {authors}, 清单 {list_ids}, 结果数量: {len(results)}")
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
        headers = self._build_image_request_headers(image_url, video_id)
        response = requests.get(image_url, headers=headers, timeout=30)
        if response.status_code != 200:
            app_logger.warning(f"下载图片失败: url={image_url}, status={response.status_code}")
            return None

        content_type = (response.headers.get("content-type", "") or "").lower()
        if "image" not in content_type:
            app_logger.warning(f"下载内容不是图片: url={image_url}, content-type={content_type}")
            return None

        return response.content
    
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
        """下载高清缩略图到JAV目录（主页导入时使用）"""
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
                
                app_logger.info(f"下载推荐页封面成功: {video_id}")
            except Exception as e:
                error_logger.error(f"下载推荐页封面失败: {e}")
        
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
                return ServiceResult.error("没有找到有效的视频")
            
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
                return ServiceResult.error("没有找到有效的视频")
            
            app_logger.info(f"批量从回收站恢复成功: {updated_count}个视频")
            return ServiceResult.ok({"updated_count": updated_count}, f"已恢复{updated_count}个视频")
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
                return ServiceResult.error("没有找到有效的视频")
            
            app_logger.info(f"批量永久删除成功: {deleted_count}个视频")
            return ServiceResult.ok({"deleted_count": deleted_count}, f"已永久删除{deleted_count}个视频")
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
