"""
演员应用服务
"""

from typing import List, Dict, Optional, Set
import os
import threading
import requests
from io import BytesIO
from PIL import Image

from domain.actor import ActorSubscription, ActorRepository
from domain.video import VideoRepository
from infrastructure.persistence.repositories.actor_repository_impl import ActorJsonRepository
from infrastructure.persistence.repositories.video_repository_impl import VideoJsonRepository
from infrastructure.persistence.cache import CacheManager
from infrastructure.persistence.json_storage import JsonStorage
from infrastructure.common.result import ServiceResult
from infrastructure.logger import app_logger, error_logger
from core.utils import get_current_time, generate_id
from core.constants import (
    CACHE_ROOT_DIR,
    VIDEO_JSON_FILE,
    VIDEO_RECOMMENDATION_JSON_FILE
)
from application.base.content_app_service import BaseCreatorAppService
from core.enums import ContentType


class ActorAppService(BaseCreatorAppService):
    _entity_name: str = "演员"
    _content_type: ContentType = ContentType.VIDEO
    
    def __init__(self, actor_repo: ActorRepository = None, video_repo: VideoRepository = None):
        self._actor_repo = actor_repo or ActorJsonRepository()
        self._video_repo = video_repo or VideoJsonRepository()

    @staticmethod
    def _normalize_platform(platform: str) -> str:
        raw = str(platform or "").strip().lower()
        if raw == "javbus":
            return "JAVBUS"
        return "JAVDB"

    @classmethod
    def _get_actor_cover_cache_dir(cls, platform: str) -> str:
        platform_key = cls._normalize_platform(platform)
        return os.path.join(CACHE_ROOT_DIR, "author_cover", platform_key)

    @classmethod
    def _build_actor_cover_url(cls, content_id: str, platform: str) -> str:
        platform_key = cls._normalize_platform(platform)
        safe_id = str(content_id or "").strip()
        return f"/static/cover/{platform_key}/author_cache/{safe_id}.jpg"

    def _resolve_cover_url_for_work(self, work: Dict) -> str:
        if not isinstance(work, dict):
            return ""
        content_id = str(work.get("id", "")).strip()
        if not content_id:
            return ""
        platform = work.get("platform", "")
        cache_dir = self._get_actor_cover_cache_dir(platform)
        local_file = os.path.join(cache_dir, f"{content_id}.jpg")
        if os.path.exists(local_file):
            return self._build_actor_cover_url(content_id, platform)
        return ""
    
    def _search_works(self, creator_name: str, page: int = 1, max_pages: int = 1) -> Dict:
        """搜索演员作品 - 支持分页
        
        Args:
            creator_name: 演员名称
            page: 起始页码
            max_pages: 最大搜索页数
            
        Returns:
            Dict: {
                "works": List[Dict],  # 作品列表
                "has_more": bool,     # 是否还有更多
                "page": int           # 当前页码
            }
        """
        from api.v1.video import get_video_adapter
        
        works = []
        has_more = False
        
        try:
            platforms_to_search = ["javdb", "javbus"]
            platform_videos = {}
            max_result_count = 0
            
            for plat in platforms_to_search:
                try:
                    adapter = get_video_adapter(plat)
                    result = {}

                    if plat == "javdb" and hasattr(adapter, "search_actor") and hasattr(adapter, "get_actor_works"):
                        actor_id = ""
                        actors = adapter.search_actor(creator_name) or []
                        if isinstance(actors, list) and actors:
                            actor = actors[0] if isinstance(actors[0], dict) else {}
                            actor_id = str(
                                actor.get("id")
                                or actor.get("actor_id")
                                or actor.get("uid")
                                or ""
                            ).strip()

                        if actor_id:
                            result = adapter.get_actor_works(actor_id, page=page, max_pages=max_pages) or {}
                        else:
                            result = adapter.search_videos(creator_name, page=page, max_pages=max_pages) or {}
                    else:
                        result = adapter.search_videos(creator_name, page=page, max_pages=max_pages) or {}

                    videos = result.get("videos", []) if isinstance(result, dict) else []
                    has_more = has_more or bool(result.get("has_next", False) if isinstance(result, dict) else False)
                    
                    if videos:
                        platform_videos[plat] = videos
                        max_result_count = max(max_result_count, len(videos))
                except Exception as e:
                    error_logger.error(f"搜索演员 {creator_name} 在平台 {plat} 的作品失败: {e}")
                    continue
            
            for i in range(max_result_count):
                for plat in platforms_to_search:
                    if plat not in platform_videos or i >= len(platform_videos[plat]):
                        continue
                    
                    video = platform_videos[plat][i]
                    work_id = str(video.get("video_id") or video.get("code") or "")
                    if not work_id:
                        continue
                    
                    cover_url = video.get("cover_url", "")
                    local_cover = self._build_actor_cover_url(work_id, plat)
                    if os.path.exists(os.path.join(self._get_actor_cover_cache_dir(plat), f"{work_id}.jpg")):
                        cover_url = local_cover
                    
                    works.append({
                        "id": work_id,
                        "title": video.get("title", ""),
                        "actor": creator_name,
                        "cover_url": cover_url,
                        "duration": video.get("duration", 0),
                        "has_detail": False,
                        "is_new": True,
                        "platform": plat
                    })
        except Exception as e:
            error_logger.error(f"搜索演员 {creator_name} 作品失败: {e}")
        
        return {
            "works": works,
            "has_more": has_more,
            "page": page
        }
    
    def _get_existing_content_ids(self) -> Set[str]:
        """获取已存在的视频ID集合"""
        existing_ids = set()
        
        try:
            home_storage = JsonStorage(VIDEO_JSON_FILE)
            home_data = home_storage.read()
            for video in home_data.get('videos', []):
                existing_ids.add(video.get('id', ''))
        except Exception as e:
            error_logger.error(f"获取主页视频ID失败: {e}")
        
        try:
            rec_storage = JsonStorage(VIDEO_RECOMMENDATION_JSON_FILE)
            rec_data = rec_storage.read()
            for video in rec_data.get('video_recommendations', []):
                existing_ids.add(video.get('id', ''))
        except Exception as e:
            error_logger.error(f"获取推荐页视频ID失败: {e}")
        
        return existing_ids
    
    def _download_cover(self, content_id: str, cover_url: str, platform: str) -> str:
        """下载演员作品封面"""
        if not cover_url:
            return ""

        platform_key = self._normalize_platform(platform)
        cache_dir = self._get_actor_cover_cache_dir(platform_key)
        local_path = os.path.join(cache_dir, f"{content_id}.jpg")

        if os.path.exists(local_path):
            return self._build_actor_cover_url(content_id, platform_key)
        
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            if 'javbus.com' in cover_url.lower():
                headers['Referer'] = f"https://www.javbus.com/{content_id}"
            
            response = requests.get(cover_url, headers=headers, timeout=10)
            if response.status_code != 200:
                return cover_url
            if "image" not in (response.headers.get("content-type", "") or "").lower():
                return cover_url
            response.raise_for_status()
            
            os.makedirs(cache_dir, exist_ok=True)
            
            with Image.open(BytesIO(response.content)) as img:
                if img.mode in ('RGBA', 'P'):
                    img = img.convert('RGB')
                img.save(local_path, 'JPEG', quality=85)

            return self._build_actor_cover_url(content_id, platform_key)
        except Exception as e:
            error_logger.error(f"下载演员作品封面失败 {content_id}: {e}")
            return cover_url
    
    def _get_cache_key_prefix(self) -> str:
        """获取缓存键前缀"""
        return "actor_works"
    
    def get_all_actors(self) -> ServiceResult:
        """获取所有演员（主页+推荐页）"""
        try:
            actor_set = set()
            
            videos = self._video_repo.get_all()
            for video in videos:
                for actor in video.actors or []:
                    if actor and actor.strip():
                        actor_set.add(actor.strip())
            
            from infrastructure.persistence.repositories.video_recommendation_repository_impl import VideoRecommendationJsonRepository
            rec_repo = VideoRecommendationJsonRepository()
            recommendations = rec_repo.get_all()
            for rec in recommendations:
                for actor in rec.actors or []:
                    if actor and actor.strip():
                        actor_set.add(actor.strip())
            
            subscribed_actors = self._actor_repo.get_all()
            subscribed_actor_names = {a.name for a in subscribed_actors}
            
            all_actors = []
            for name in sorted(actor_set):
                is_subscribed = name in subscribed_actor_names
                all_actors.append({
                    "name": name,
                    "is_subscribed": is_subscribed,
                    "subscription": next((a.to_dict() for a in subscribed_actors if a.name == name), None)
                })
            
            app_logger.info(f"获取所有演员成功，共 {len(all_actors)} 个")
            return ServiceResult.ok(all_actors)
        except Exception as e:
            error_logger.error(f"获取所有演员失败: {e}")
            return ServiceResult.error("获取所有演员失败")
    
    def get_subscription_list(self) -> ServiceResult:
        try:
            actors = self._actor_repo.get_all()
            actor_list = [a.to_dict() for a in actors]
            app_logger.info(f"获取演员订阅列表成功，共 {len(actor_list)} 个")
            return ServiceResult.ok(actor_list)
        except Exception as e:
            error_logger.error(f"获取演员订阅列表失败: {e}")
            return ServiceResult.error("获取演员订阅列表失败")
    
    def subscribe_actor(self, name: str) -> ServiceResult:
        try:
            if not name or not name.strip():
                return ServiceResult.error("演员名称不能为空")
            
            name = name.strip()
            
            if self._actor_repo.exists_by_name(name):
                return ServiceResult.error("已订阅该演员")
            
            actor = ActorSubscription(
                id=generate_id("actor"),
                name=name,
                subscribe_time=get_current_time()
            )
            
            if not self._actor_repo.save(actor):
                return ServiceResult.error("订阅演员失败")
            
            app_logger.info(f"订阅演员成功: {name}")
            return ServiceResult.ok(actor.to_dict(), "订阅成功")
        except Exception as e:
            error_logger.error(f"订阅演员失败: {e}")
            return ServiceResult.error("订阅演员失败")
    
    def unsubscribe_actor(self, actor_id: str) -> ServiceResult:
        try:
            actor = self._actor_repo.get_by_id(actor_id)
            if not actor:
                return ServiceResult.error("订阅不存在")
            
            if not self._actor_repo.delete(actor_id):
                return ServiceResult.error("取消订阅失败")
            
            app_logger.info(f"取消订阅演员成功: {actor_id}")
            return ServiceResult.ok({"id": actor_id}, "取消订阅成功")
        except Exception as e:
            error_logger.error(f"取消订阅演员失败: {e}")
            return ServiceResult.error("取消订阅演员失败")
    
    def check_actor_updates(self, actor_id: str = None) -> ServiceResult:
        try:
            if actor_id:
                actors = [self._actor_repo.get_by_id(actor_id)]
                actors = [a for a in actors if a]
            else:
                actors = self._actor_repo.get_all()
            
            if not actors:
                return ServiceResult.ok({"updated_actors": [], "total_new_works": 0})
            
            updated_actors = []
            total_new_works = 0
            
            for actor in actors:
                try:
                    cache_key = f"{self._get_cache_key_prefix()}_{actor.name}"
                    cached_works = self._cache_manager.get_persistent(cache_key, self._get_cache_key_prefix())
                    
                    search_result = self._search_works(actor.name, page=1, max_pages=3)
                    works = search_result.get("works", [])
                    
                    if not works:
                        continue
                    
                    latest_work = works[0]
                    latest_work_id = latest_work.get("id", "")
                    latest_work_title = latest_work.get("title", "")
                    
                    cached_latest_id = None
                    if cached_works:
                        first_cached = cached_works[0] if isinstance(cached_works, list) and cached_works else None
                        if first_cached:
                            cached_latest_id = first_cached.get("id", "")
                    
                    has_update = cached_latest_id is None or cached_latest_id != latest_work_id
                    new_count = 0
                    
                    if has_update:
                        new_count = 1
                        works_for_cache = works[:20]
                        self._cache_manager.set_persistent(cache_key, works_for_cache, self._get_cache_key_prefix())
                    
                    actor.update_check_info(
                        latest_work_id,
                        latest_work_title,
                        new_count
                    )
                    self._actor_repo.save(actor)
                    
                    if has_update:
                        updated_actors.append({
                            "actor": actor.to_dict(),
                            "new_works": [latest_work]
                        })
                        total_new_works += new_count
                        
                except Exception as e:
                    error_logger.error(f"检查演员 {actor.name} 更新失败: {e}")
                    continue
            
            app_logger.info(f"检查演员更新完成，{len(updated_actors)} 个演员有更新，共 {total_new_works} 个新作品")
            return ServiceResult.ok({
                "updated_actors": updated_actors,
                "total_new_works": total_new_works
            })
        except Exception as e:
            error_logger.error(f"检查演员更新失败: {e}")
            return ServiceResult.error("检查演员更新失败")
    
    def get_actor_new_works(self, actor_id: str) -> ServiceResult:
        try:
            actor = self._actor_repo.get_by_id(actor_id)
            if not actor:
                return ServiceResult.error("订阅不存在")
            
            works = []
            try:
                search_result = self._search_works(actor.name, page=1, max_pages=3)
                works = search_result.get("works", [])
            except Exception as e:
                error_logger.error(f"搜索演员 {actor.name} 作品失败: {e}")
            
            if not works:
                return ServiceResult.ok({"actor": actor.to_dict(), "new_works": []})
            
            new_works = []
            if not actor.last_work_id:
                new_works = works[:5]
            else:
                found_last = False
                for work in works:
                    if work.get("id") == actor.last_work_id:
                        found_last = True
                        break
                    new_works.append(work)
                
                if not found_last:
                    new_works = works[:5]
            
            return ServiceResult.ok({
                "actor": actor.to_dict(),
                "new_works": new_works
            })
        except Exception as e:
            error_logger.error(f"获取演员新作品失败: {e}")
            return ServiceResult.error("获取演员新作品失败")
    
    def clear_actor_new_count(self, actor_id: str) -> ServiceResult:
        try:
            actor = self._actor_repo.get_by_id(actor_id)
            if not actor:
                return ServiceResult.error("订阅不存在")
            
            actor.clear_new_count()
            self._actor_repo.save(actor)
            
            return ServiceResult.ok({"id": actor_id}, "已清除")
        except Exception as e:
            error_logger.error(f"清除新作品计数失败: {e}")
            return ServiceResult.error("清除新作品计数失败")
    
    def get_actor_works_paginated(self, actor_id: str, offset: int = 0, limit: int = 5) -> ServiceResult:
        """分页获取演员作品"""
        try:
            actor = self._actor_repo.get_by_id(actor_id)
            if not actor:
                return ServiceResult.error("订阅不存在")
            
            result = self.get_works_paginated_impl(actor, offset, limit)
            
            if result.success:
                data = result.data
                data["actor"] = data.pop("creator")
            
            return result
        except Exception as e:
            error_logger.error(f"获取演员作品失败: {e}")
            return ServiceResult.error("获取演员作品失败")
    
    def search_actor_works_by_name(self, actor_name: str, offset: int = 0, limit: int = 5) -> ServiceResult:
        """根据演员名搜索作品（不需要订阅）"""
        return self.search_works_by_name_impl(actor_name, offset, limit)
    
    def clear_actor_cover_cache(self) -> ServiceResult:
        """清理演员作品封面缓存"""
        import shutil

        cleared_count = 0
        freed_size = 0

        try:
            if os.path.exists(CACHE_ROOT_DIR):
                for dirpath, _, filenames in os.walk(CACHE_ROOT_DIR):
                    for filename in filenames:
                        filepath = os.path.join(dirpath, filename)
                        try:
                            if os.path.isfile(filepath):
                                freed_size += os.path.getsize(filepath)
                                cleared_count += 1
                        except Exception:
                            continue
                shutil.rmtree(CACHE_ROOT_DIR, ignore_errors=True)
            os.makedirs(CACHE_ROOT_DIR, exist_ok=True)

            app_logger.info(f"清理演员封面缓存完成: 清理 {cleared_count} 个文件, 释放 {freed_size} 字节")
            return ServiceResult.ok({
                "cleared_count": cleared_count,
                "freed_size_bytes": freed_size,
                "freed_size_mb": round(freed_size / (1024 * 1024), 2)
            })
        except Exception as e:
            error_logger.error(f"清理演员封面缓存失败: {e}")
            return ServiceResult.error("清理演员封面缓存失败")
    
    def clear_actor_works_cache(self, actor_name: str = None) -> ServiceResult:
        """清理演员作品缓存"""
        return self.clear_works_cache_impl(actor_name)
    
    def get_actor_videos(self, actor_name: str) -> ServiceResult:
        """获取演员作品（简化版）"""
        try:
            search_result = self._search_works(actor_name, page=1, max_pages=3)
            works = search_result.get("works", [])
            return ServiceResult.ok(works)
        except Exception as e:
            error_logger.error(f"获取演员视频失败: {e}")
            return ServiceResult.error("获取演员视频失败")
    
    def update_check_time(self, actor_subscription_id: str) -> ServiceResult:
        """更新检查时间"""
        try:
            actor = self._actor_repo.get_by_id(actor_subscription_id)
            if not actor:
                return ServiceResult.error("订阅不存在")
            
            actor.update_check_time(get_current_time())
            self._actor_repo.save(actor)
            
            return ServiceResult.ok(actor.to_dict())
        except Exception as e:
            error_logger.error(f"更新检查时间失败: {e}")
            return ServiceResult.error("更新检查时间失败")
    
    def update_last_work(self, actor_subscription_id: str, work_id: str, work_title: str, new_count: int = 0) -> ServiceResult:
        """更新最新作品信息"""
        try:
            actor = self._actor_repo.get_by_id(actor_subscription_id)
            if not actor:
                return ServiceResult.error("订阅不存在")
            
            actor.update_check_info(work_id, work_title, new_count)
            self._actor_repo.save(actor)
            
            return ServiceResult.ok(actor.to_dict())
        except Exception as e:
            error_logger.error(f"更新最新作品失败: {e}")
            return ServiceResult.error("更新最新作品失败")
