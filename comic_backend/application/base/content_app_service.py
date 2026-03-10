from abc import ABC, abstractmethod
from typing import List, Optional, TypeVar, Generic, Dict, Any, Set
import os
import threading
import requests
from PIL import Image
from io import BytesIO

from domain.base.entity import BaseEntity, BaseContent, BaseCreator
from domain.base.repository import BaseRepository, BaseContentRepository, BaseCreatorRepository
from infrastructure.common.result import ServiceResult
from infrastructure.logger import app_logger, error_logger
from infrastructure.persistence.cache import CacheManager
from infrastructure.persistence.json_storage import JsonStorage
from core.enums import ContentType

T = TypeVar('T', bound=BaseEntity)


class BaseAppService(ABC, Generic[T]):
    _entity_name: str = "实体"
    
    def _get_by_id_impl(
        self, 
        repo: BaseRepository[T], 
        entity_id: str
    ) -> ServiceResult:
        try:
            entity = repo.get_by_id(entity_id)
            if not entity:
                return ServiceResult.error(f"{self._entity_name}不存在")
            return ServiceResult.ok(entity.to_dict())
        except Exception as e:
            error_logger.error(f"获取{self._entity_name}失败: {e}")
            return ServiceResult.error(f"获取{self._entity_name}失败")
    
    def _get_all_impl(self, repo: BaseRepository[T]) -> ServiceResult:
        try:
            entities = repo.get_all()
            return ServiceResult.ok([e.to_dict() for e in entities])
        except Exception as e:
            error_logger.error(f"获取{self._entity_name}列表失败: {e}")
            return ServiceResult.error(f"获取{self._entity_name}列表失败")
    
    def _delete_impl(
        self, 
        repo: BaseRepository[T], 
        entity_id: str
    ) -> ServiceResult:
        try:
            success = repo.delete(entity_id)
            if success:
                return ServiceResult.ok({"message": f"{self._entity_name}删除成功"})
            return ServiceResult.error(f"{self._entity_name}删除失败")
        except Exception as e:
            error_logger.error(f"删除{self._entity_name}失败: {e}")
            return ServiceResult.error(f"删除{self._entity_name}失败")


class BaseContentAppService(BaseAppService[BaseContent]):
    _entity_name: str = "内容"
    _content_type: ContentType = ContentType.COMIC
    
    def _get_list_impl(
        self,
        repo: BaseContentRepository,
        tag_repo: BaseRepository = None,
        sort_type: str = None,
        min_score: float = None,
        max_score: float = None,
        include_deleted: bool = False
    ) -> ServiceResult:
        try:
            entities = repo.get_all()
            
            if not include_deleted:
                entities = [e for e in entities if not e.is_deleted]
            
            if min_score is not None:
                entities = [e for e in entities if e.score is not None and e.score >= min_score]
            if max_score is not None:
                entities = [e for e in entities if e.score is not None and e.score <= max_score]
            
            if sort_type == "create_time":
                entities = sorted(entities, key=lambda e: e.create_time or "", reverse=True)
            elif sort_type == "score":
                entities = sorted(entities, key=lambda e: e.score or 0, reverse=True)
            elif sort_type == "access_time" or sort_type == "read_time":
                entities = sorted(entities, key=lambda e: e.last_access_time or "", reverse=True)
            
            tag_map = {}
            if tag_repo:
                tags = tag_repo.get_all()
                tag_map = {t.id: t.name for t in tags}
            
            result_list = []
            for e in entities:
                entity_info = e.to_dict()
                entity_info["tags"] = [
                    {"id": tid, "name": tag_map.get(tid, tid)} 
                    for tid in e.tag_ids
                ]
                result_list.append(entity_info)
            
            return ServiceResult.ok(result_list)
        except Exception as e:
            error_logger.error(f"获取{self._entity_name}列表失败: {e}")
            return ServiceResult.error(f"获取{self._entity_name}列表失败")
    
    def _search_impl(
        self,
        repo: BaseContentRepository,
        keyword: str
    ) -> ServiceResult:
        try:
            entities = repo.search(keyword)
            entities = [e for e in entities if not e.is_deleted]
            return ServiceResult.ok([e.to_dict() for e in entities])
        except Exception as e:
            error_logger.error(f"搜索{self._entity_name}失败: {e}")
            return ServiceResult.error(f"搜索{self._entity_name}失败")
    
    def _update_score_impl(
        self,
        repo: BaseContentRepository,
        entity_id: str,
        score: float
    ) -> ServiceResult:
        try:
            entity = repo.get_by_id(entity_id)
            if not entity:
                return ServiceResult.error(f"{self._entity_name}不存在")
            
            if entity.update_score(score):
                repo.save(entity)
                return ServiceResult.ok({"message": "评分更新成功", "score": score})
            return ServiceResult.error("评分无效")
        except Exception as e:
            error_logger.error(f"更新评分失败: {e}")
            return ServiceResult.error("更新评分失败")
    
    def _update_progress_impl(
        self,
        repo: BaseContentRepository,
        entity_id: str,
        unit: int
    ) -> ServiceResult:
        try:
            entity = repo.get_by_id(entity_id)
            if not entity:
                return ServiceResult.error(f"{self._entity_name}不存在")
            
            if entity.update_progress(unit):
                repo.save(entity)
                return ServiceResult.ok({"message": "进度更新成功", "current_unit": unit})
            return ServiceResult.error("进度无效")
        except Exception as e:
            error_logger.error(f"更新进度失败: {e}")
            return ServiceResult.error("更新进度失败")
    
    def _move_to_trash_impl(
        self,
        repo: BaseContentRepository,
        entity_id: str
    ) -> ServiceResult:
        try:
            entity = repo.get_by_id(entity_id)
            if not entity:
                return ServiceResult.error(f"{self._entity_name}不存在")
            
            entity.move_to_trash()
            repo.save(entity)
            return ServiceResult.ok({"message": "已移至回收站"})
        except Exception as e:
            error_logger.error(f"移至回收站失败: {e}")
            return ServiceResult.error("移至回收站失败")
    
    def _restore_from_trash_impl(
        self,
        repo: BaseContentRepository,
        entity_id: str
    ) -> ServiceResult:
        try:
            entity = repo.get_by_id(entity_id)
            if not entity:
                return ServiceResult.error(f"{self._entity_name}不存在")
            
            entity.restore_from_trash()
            repo.save(entity)
            return ServiceResult.ok({"message": "已从回收站恢复"})
        except Exception as e:
            error_logger.error(f"从回收站恢复失败: {e}")
            return ServiceResult.error("从回收站恢复失败")


class BaseCreatorAppService(BaseAppService[BaseCreator]):
    _entity_name: str = "创作者"
    _content_type: ContentType = ContentType.COMIC
    _cache_manager = CacheManager()
    
    @abstractmethod
    def _search_works(self, creator_name: str, page: int = 1, max_pages: int = 1) -> Dict:
        """搜索创作者作品，子类必须实现
        
        Args:
            creator_name: 创作者名称
            page: 起始页码
            max_pages: 最大搜索页数
            
        Returns:
            Dict: {
                "works": List[Dict],  # 作品列表
                "has_more": bool,     # 是否还有更多
                "page": int           # 当前页码
            }
        """
        pass
    
    @abstractmethod
    def _get_existing_content_ids(self) -> Set[str]:
        """获取已存在的内容ID集合，子类必须实现"""
        pass
    
    @abstractmethod
    def _download_cover(self, content_id: str, cover_url: str, platform: str) -> str:
        """下载作品封面，子类必须实现"""
        pass
    
    @abstractmethod
    def _get_cache_key_prefix(self) -> str:
        """获取缓存键前缀，子类必须实现"""
        pass
    
    def _get_subscribed_impl(
        self,
        repo: BaseCreatorRepository
    ) -> ServiceResult:
        try:
            creators = repo.get_subscribed()
            return ServiceResult.ok([c.to_dict() for c in creators])
        except Exception as e:
            error_logger.error(f"获取订阅{self._entity_name}列表失败: {e}")
            return ServiceResult.error(f"获取订阅{self._entity_name}列表失败")
    
    def _subscribe_impl(
        self,
        repo: BaseCreatorRepository,
        creator_id: str
    ) -> ServiceResult:
        try:
            creator = repo.get_by_id(creator_id)
            if not creator:
                return ServiceResult.error(f"{self._entity_name}不存在")
            
            creator.subscribe()
            repo.save(creator)
            return ServiceResult.ok({"message": "订阅成功"})
        except Exception as e:
            error_logger.error(f"订阅失败: {e}")
            return ServiceResult.error("订阅失败")
    
    def _unsubscribe_impl(
        self,
        repo: BaseCreatorRepository,
        creator_id: str
    ) -> ServiceResult:
        try:
            creator = repo.get_by_id(creator_id)
            if not creator:
                return ServiceResult.error(f"{self._entity_name}不存在")
            
            creator.unsubscribe()
            repo.save(creator)
            return ServiceResult.ok({"message": "取消订阅成功"})
        except Exception as e:
            error_logger.error(f"取消订阅失败: {e}")
            return ServiceResult.error("取消订阅失败")
    
    def get_works_paginated_impl(
        self,
        creator: BaseCreator,
        offset: int = 0,
        limit: int = 5
    ) -> ServiceResult:
        """通用的分页获取作品实现 - 支持分页查询和缓存追加"""
        try:
            cache_key = f"{self._get_cache_key_prefix()}_{creator.name}"
            cache_meta_key = f"{cache_key}_meta"
            
            cached_all_works = self._cache_manager.get_persistent(cache_key, self._get_cache_key_prefix())
            cached_meta = self._cache_manager.get_persistent(cache_meta_key, self._get_cache_key_prefix())
            
            if cached_all_works is None:
                cached_all_works = []
            if cached_meta is None:
                cached_meta = {"has_more": True, "next_page": 1, "all_fetched": False}
            
            required_count = offset + limit
            
            while len(cached_all_works) < required_count and cached_meta.get("has_more", True) and not cached_meta.get("all_fetched", False):
                app_logger.info(f"[Paginated] 缓存不足，继续获取第 {cached_meta['next_page']} 页")
                
                search_result = self._search_works(
                    creator.name,
                    page=cached_meta["next_page"],
                    max_pages=1
                )
                
                new_works = search_result.get("works", [])
                has_more = search_result.get("has_more", False)
                
                if new_works:
                    existing_ids = {w.get("id") for w in cached_all_works}
                    unique_new_works = [w for w in new_works if w.get("id") not in existing_ids]
                    
                    cached_all_works.extend(unique_new_works)
                    self._cache_manager.set_persistent(cache_key, cached_all_works, self._get_cache_key_prefix())
                    
                    app_logger.info(f"[Paginated] 新增 {len(unique_new_works)} 个作品到缓存，当前总数: {len(cached_all_works)}")
                
                cached_meta["has_more"] = has_more
                if has_more:
                    cached_meta["next_page"] = cached_meta["next_page"] + 1
                else:
                    cached_meta["all_fetched"] = True
                
                self._cache_manager.set_persistent(cache_meta_key, cached_meta, self._get_cache_key_prefix())
                
                if not new_works:
                    break
            
            existing_ids = self._get_existing_content_ids()
            app_logger.info(f"[Paginated] 从持久化缓存读取{self._entity_name} {creator.name} 作品，共 {len(cached_all_works)} 个，已存在 {len(existing_ids)} 个")
            
            paginated_works = cached_all_works[offset:offset + limit]
            total = len(cached_all_works)
            has_more = (offset + limit < total) or cached_meta.get("has_more", False)
            
            app_logger.info(f"[Paginated] 返回作品数量: {len(paginated_works)}，总数: {total}，has_more: {has_more}")
            
            self._async_download_covers(paginated_works)
            
            return ServiceResult.ok({
                "creator": creator.to_dict(),
                "works": paginated_works,
                "total": total,
                "offset": offset,
                "limit": limit,
                "has_more": has_more,
                "from_cache": True
            })
        except Exception as e:
            error_logger.error(f"获取{self._entity_name}作品失败: {e}")
            return ServiceResult.error(f"获取{self._entity_name}作品失败")
    
    def search_works_by_name_impl(
        self,
        creator_name: str,
        offset: int = 0,
        limit: int = 5
    ) -> ServiceResult:
        """通用的按名称搜索作品实现 - 支持分页查询和缓存追加"""
        try:
            cache_key = f"{self._get_cache_key_prefix()}_{creator_name}"
            cache_meta_key = f"{cache_key}_meta"
            
            cached_all_works = self._cache_manager.get_persistent(cache_key, self._get_cache_key_prefix())
            cached_meta = self._cache_manager.get_persistent(cache_meta_key, self._get_cache_key_prefix())
            
            if cached_all_works is None:
                cached_all_works = []
            if cached_meta is None:
                cached_meta = {"has_more": True, "next_page": 1, "all_fetched": False}
            
            required_count = offset + limit
            
            while len(cached_all_works) < required_count and cached_meta.get("has_more", True) and not cached_meta.get("all_fetched", False):
                app_logger.info(f"[Paginated] 缓存不足，继续获取第 {cached_meta['next_page']} 页")
                
                search_result = self._search_works(
                    creator_name,
                    page=cached_meta["next_page"],
                    max_pages=1
                )
                
                new_works = search_result.get("works", [])
                has_more = search_result.get("has_more", False)
                
                if new_works:
                    existing_ids = {w.get("id") for w in cached_all_works}
                    unique_new_works = [w for w in new_works if w.get("id") not in existing_ids]
                    
                    cached_all_works.extend(unique_new_works)
                    self._cache_manager.set_persistent(cache_key, cached_all_works, self._get_cache_key_prefix())
                    
                    app_logger.info(f"[Paginated] 新增 {len(unique_new_works)} 个作品到缓存，当前总数: {len(cached_all_works)}")
                
                cached_meta["has_more"] = has_more
                if has_more:
                    cached_meta["next_page"] = cached_meta["next_page"] + 1
                else:
                    cached_meta["all_fetched"] = True
                
                self._cache_manager.set_persistent(cache_meta_key, cached_meta, self._get_cache_key_prefix())
                
                if not new_works:
                    break
            
            existing_ids = self._get_existing_content_ids()
            app_logger.info(f"[Paginated] 从持久化缓存搜索{self._entity_name} {creator_name} 作品，共 {len(cached_all_works)} 个，已存在 {len(existing_ids)} 个")
            
            paginated_works = cached_all_works[offset:offset + limit]
            total = len(cached_all_works)
            has_more = (offset + limit < total) or cached_meta.get("has_more", False)
            
            app_logger.info(f"[Paginated] 返回作品数量: {len(paginated_works)}，总数: {total}，has_more: {has_more}")
            
            self._async_download_covers(paginated_works)
            
            return ServiceResult.ok({
                "creator_name": creator_name,
                "works": paginated_works,
                "total": total,
                "offset": offset,
                "limit": limit,
                "has_more": has_more,
                "from_cache": True
            })
        except Exception as e:
            error_logger.error(f"搜索{self._entity_name}作品失败: {e}")
            return ServiceResult.error(f"搜索{self._entity_name}作品失败")
    
    def clear_works_cache_impl(self, creator_name: str = None) -> ServiceResult:
        """通用的清除作品缓存实现 - 同时清除缓存元数据"""
        try:
            if creator_name:
                cache_key = f"{self._get_cache_key_prefix()}_{creator_name}"
                cache_meta_key = f"{cache_key}_meta"
                
                deleted1 = self._cache_manager.delete_persistent(cache_key, self._get_cache_key_prefix())
                deleted2 = self._cache_manager.delete_persistent(cache_meta_key, self._get_cache_key_prefix())
                
                return ServiceResult.ok({
                    "cleared_count": 1 if (deleted1 or deleted2) else 0,
                    "creator_name": creator_name
                })
            else:
                count = self._cache_manager.clear_persistent_category(self._get_cache_key_prefix())
                return ServiceResult.ok({
                    "cleared_count": count
                })
        except Exception as e:
            error_logger.error(f"清理{self._entity_name}作品缓存失败: {e}")
            return ServiceResult.error(f"清理{self._entity_name}作品缓存失败")
    
    def _async_download_covers(self, works: List[Dict]):
        """异步下载作品封面"""
        def download_covers():
            for work in works:
                if work.get("cover_url"):
                    try:
                        platform = work.get("platform", "")
                        self._download_cover(work["id"], work["cover_url"], platform)
                    except Exception as e:
                        error_logger.error(f"异步下载封面失败 {work['id']}: {e}")
        threading.Thread(target=download_covers, daemon=True).start()
