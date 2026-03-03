from abc import ABC
from typing import List, Optional, TypeVar, Generic, Dict, Any

from domain.base.entity import BaseEntity, BaseContent, BaseCreator
from domain.base.repository import BaseRepository, BaseContentRepository, BaseCreatorRepository
from infrastructure.common.result import ServiceResult
from infrastructure.logger import app_logger, error_logger
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
