"""
演员应用服务
"""

from typing import List, Dict, Optional
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
from infrastructure.common.result import ServiceResult
from infrastructure.logger import app_logger, error_logger
from core.utils import get_current_time, generate_id
from core.constants import VIDEO_ACTOR_COVER_CACHE_DIR, VIDEO_CACHE_DIR
from application.base.content_app_service import BaseCreatorAppService


class ActorAppService(BaseCreatorAppService):
    _entity_name = "演员"
    _cache_manager = CacheManager()
    
    def __init__(
        self,
        actor_repo: ActorRepository = None,
        video_repo: VideoRepository = None
    ):
        self._actor_repo = actor_repo or ActorJsonRepository()
        self._video_repo = video_repo or VideoJsonRepository()
    
    def get_subscription_list(self) -> ServiceResult:
        return self._get_all_impl(self._actor_repo)
    
    def subscribe_actor(self, name: str, actor_id: str = "") -> ServiceResult:
        try:
            if not name or not name.strip():
                return ServiceResult.error("演员名称不能为空")
            
            name = name.strip()
            app_logger.info(f"开始订阅演员: {name}")
            
            if self._actor_repo.exists_by_name(name):
                return ServiceResult.error("已订阅该演员")
            
            actor = ActorSubscription(
                id=generate_id("actor"),
                name=name,
                actor_id=actor_id,
                subscribe_time=get_current_time()
            )
            
            app_logger.info(f"创建演员对象成功: {actor.id}")
            
            if not self._actor_repo.save(actor):
                return ServiceResult.error("订阅演员失败")
            
            app_logger.info(f"订阅演员成功: {name}")
            return ServiceResult.ok(actor.to_dict(), "订阅成功")
        except Exception as e:
            error_logger.error(f"订阅演员失败: {e}")
            import traceback
            error_logger.error(traceback.format_exc())
            return ServiceResult.error("订阅演员失败")
    
    def unsubscribe_actor(self, actor_subscription_id: str) -> ServiceResult:
        try:
            actor = self._actor_repo.get_by_id(actor_subscription_id)
            if not actor:
                return ServiceResult.error("订阅记录不存在")
            
            success = self._actor_repo.delete(actor_subscription_id)
            if success:
                app_logger.info(f"取消订阅演员成功: {actor.name}")
                return ServiceResult.ok({"message": "取消订阅成功"})
            return ServiceResult.error("取消订阅失败")
        except Exception as e:
            error_logger.error(f"取消订阅演员失败: {e}")
            return ServiceResult.error("取消订阅失败")
    
    def update_check_time(self, actor_subscription_id: str) -> ServiceResult:
        try:
            actor = self._actor_repo.get_by_id(actor_subscription_id)
            if not actor:
                return ServiceResult.error("订阅记录不存在")
            
            actor.last_check_time = get_current_time()
            self._actor_repo.save(actor)
            return ServiceResult.ok({"message": "更新成功"})
        except Exception as e:
            error_logger.error(f"更新检查时间失败: {e}")
            return ServiceResult.error("更新失败")
    
    def update_last_work(
        self,
        actor_subscription_id: str,
        work_id: str,
        work_title: str,
        new_count: int = 0
    ) -> ServiceResult:
        try:
            actor = self._actor_repo.get_by_id(actor_subscription_id)
            if not actor:
                return ServiceResult.error("订阅记录不存在")
            
            actor.last_work_id = work_id
            actor.last_work_title = work_title
            actor.new_work_count = new_count
            actor.last_check_time = get_current_time()
            
            self._actor_repo.save(actor)
            return ServiceResult.ok(actor.to_dict())
        except Exception as e:
            error_logger.error(f"更新最新作品失败: {e}")
            return ServiceResult.error("更新失败")
    
    def get_actor_videos(self, actor_name: str) -> ServiceResult:
        try:
            videos = self._video_repo.get_all()
            result = []
            for v in videos:
                if v.is_deleted:
                    continue
                if actor_name in v.actors:
                    result.append(v.to_dict())
            return ServiceResult.ok(result)
        except Exception as e:
            error_logger.error(f"获取演员视频失败: {e}")
            return ServiceResult.error("获取视频失败")
    
    def get_all_actors(self) -> ServiceResult:
        try:
            actor_set = set()
            
            videos = self._video_repo.get_all()
            for video in videos:
                for actor_name in video.actors:
                    if actor_name and actor_name.strip():
                        actor_set.add(actor_name.strip())
            
            subscribed_actors = self._actor_repo.get_all()
            subscribed_names = {a.name for a in subscribed_actors}
            
            all_actors = []
            for name in sorted(actor_set):
                is_subscribed = name in subscribed_names
                all_actors.append({
                    "name": name,
                    "is_subscribed": is_subscribed,
                    "subscription": next((a.to_dict() for a in subscribed_actors if a.name == name), None)
                })
            
            return ServiceResult.ok(all_actors)
        except Exception as e:
            error_logger.error(f"获取所有演员失败: {e}")
            return ServiceResult.error("获取演员失败")
    
    def check_actor_updates(self, actor_subscription_id: str = None) -> ServiceResult:
        """
        检查演员订阅是否有新作品：
        - 通过第三方接口获取演员作品列表
        - 取最新一部作品，与订阅记录中的 last_work_id 对比
        - 不一致则认为有更新，new_work_count 置为 1
        """
        from application.video_app_service import VideoAppService
        from api.v1.video import get_video_adapter
        
        try:
            if actor_subscription_id:
                actors = [self._actor_repo.get_by_id(actor_subscription_id)]
                actors = [a for a in actors if a]
            else:
                actors = self._actor_repo.get_all()
            
            if not actors:
                return ServiceResult.ok({"updated_actors": [], "total_new_works": 0})
            
            video_service = VideoAppService()
            updated_actors = []
            total_new_works = 0
            
            for actor in actors:
                try:
                    # 优先使用记录下来的 actor_id，如果没有则按名字搜索一次取第一个
                    actor_id = actor.actor_id
                    if not actor_id:
                        adapter = get_video_adapter("javdb")
                        search_res = adapter.search_actor(actor.name)
                        if search_res:
                            actor_id = search_res[0].get("actor_id", "")
                            if actor_id:
                                actor.actor_id = actor_id
                    
                    if not actor_id:
                        continue
                    
                    adapter = get_video_adapter("javdb")
                    result = adapter.get_actor_works(actor_id, page=1, max_pages=1)
                    works = result.get("works", []) or []
                    if not works:
                        continue
                    
                    latest_work = works[0]
                    latest_work_id = latest_work.get("id") or latest_work.get("video_id") or ""
                    latest_title = latest_work.get("title", "")
                    
                    has_update = False
                    new_count = 0
                    
                    if not actor.last_work_id:
                        has_update = True
                        new_count = 1
                    elif actor.last_work_id != latest_work_id:
                        has_update = True
                        new_count = 1
                    
                    actor.last_work_id = latest_work_id
                    actor.last_work_title = latest_title
                    actor.new_work_count = new_count
                    actor.last_check_time = get_current_time()
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
    
    def cache_actor_works(self, actor_id: str, works: List[Dict]) -> ServiceResult:
        try:
            cache_key = f"actor_works_{actor_id}"
            self._cache_manager.set(cache_key, works, VIDEO_CACHE_DIR)
            return ServiceResult.ok({"message": "缓存成功"})
        except Exception as e:
            error_logger.error(f"缓存演员作品失败: {e}")
            return ServiceResult.error("缓存失败")
    
    def get_cached_actor_works(self, actor_id: str) -> ServiceResult:
        try:
            cache_key = f"actor_works_{actor_id}"
            works = self._cache_manager.get(cache_key, VIDEO_CACHE_DIR)
            if works:
                return ServiceResult.ok(works)
            return ServiceResult.ok(None)
        except Exception as e:
            error_logger.error(f"获取缓存演员作品失败: {e}")
            return ServiceResult.ok(None)
    
    def download_actor_avatar_async(self, actor_name: str, avatar_url: str):
        def download():
            try:
                if not avatar_url:
                    return
                
                response = requests.get(avatar_url, timeout=30)
                if response.status_code != 200:
                    return
                
                image = Image.open(BytesIO(response.content))
                os.makedirs(VIDEO_ACTOR_COVER_CACHE_DIR, exist_ok=True)
                
                safe_name = "".join(c for c in actor_name if c.isalnum() or c in (' ', '-', '_'))
                avatar_path = os.path.join(VIDEO_ACTOR_COVER_CACHE_DIR, f"{safe_name}.jpg")
                image.convert("RGB").save(avatar_path, "JPEG", quality=95)
                
                app_logger.info(f"下载演员头像成功: {actor_name}")
            except Exception as e:
                error_logger.error(f"下载演员头像失败: {e}")
        
        thread = threading.Thread(target=download, daemon=True)
        thread.start()
