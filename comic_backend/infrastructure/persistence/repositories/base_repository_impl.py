from typing import Callable, List, Optional, TypeVar, Generic, Dict, Any
from abc import abstractmethod

from domain.base.entity import BaseEntity, BaseContent, BaseCreator
from domain.base.repository import BaseRepository, BaseContentRepository, BaseCreatorRepository
from infrastructure.persistence.json_storage import JsonStorage
from infrastructure.logger import app_logger, error_logger
from core.utils import get_current_time, get_current_date

T = TypeVar('T', bound=BaseEntity)
C = TypeVar('C', bound=BaseContent)
R = TypeVar('R', bound=BaseCreator)


class JsonRepositoryBatchMixin(Generic[T]):
    _storage: JsonStorage
    _data_key: str
    _total_key: Optional[str] = None
    
    def _get_entity_class(self):
        raise NotImplementedError

    def _touch_data(self, data: Dict[str, Any], entities: List[Dict[str, Any]]) -> None:
        if self._total_key:
            data[self._total_key] = len(entities)
        data["last_updated"] = get_current_time()
    
    def get_by_id(self, entity_id: str) -> Optional[T]:
        data = self._storage.read()
        entities = data.get(self._data_key, [])
        entity_data = next((e for e in entities if e["id"] == entity_id), None)
        return self._get_entity_class().from_dict(entity_data) if entity_data else None
    
    def get_all(self) -> List[T]:
        data = self._storage.read()
        entities = data.get(self._data_key, [])
        return [self._get_entity_class().from_dict(e) for e in entities]

    def get_many_by_ids(self, entity_ids: List[str]) -> List[T]:
        wanted_ids = self._normalize_entity_ids(entity_ids)
        if not wanted_ids:
            return []
        data = self._storage.read()
        entities = data.get(self._data_key, [])
        return [
            self._get_entity_class().from_dict(item)
            for item in entities
            if str(item.get("id") or "").strip() in wanted_ids
        ]

    def update_many_by_ids(self, entity_ids: List[str], mutator: Callable[[T], Optional[bool]]) -> int:
        wanted_ids = self._normalize_entity_ids(entity_ids)
        if not wanted_ids:
            return 0

        updated_count = 0

        try:
            def update_data(data):
                nonlocal updated_count
                entities = list(data.get(self._data_key, []))
                next_entities: List[Dict[str, Any]] = []
                updated_count = 0

                for raw in entities:
                    if str(raw.get("id") or "").strip() not in wanted_ids:
                        next_entities.append(raw)
                        continue

                    entity = self._get_entity_class().from_dict(raw)
                    should_save = mutator(entity)
                    if should_save is False:
                        next_entities.append(raw)
                        continue

                    next_entities.append(entity.to_dict())
                    updated_count += 1

                if updated_count == 0:
                    return None

                data[self._data_key] = next_entities
                self._touch_data(data, next_entities)
                return data

            return updated_count if self._storage.atomic_update(update_data, catalog_index_changed_ids=wanted_ids) else 0
        except Exception as e:
            error_logger.error(f"批量更新实体失败: {e}")
            return 0

    def save_many(self, entities: List[T]) -> int:
        """批量保存实体：一次读、一次改、一次写、一次索引同步。"""
        valid_entities = [
            entity
            for entity in (entities or [])
            if entity is not None and str(getattr(entity, "id", "") or "").strip()
        ]
        if not valid_entities:
            return 0

        valid_entity_ids = [
            str(entity.id).strip()
            for entity in valid_entities
        ]
        saved_count = 0

        try:
            def update_data(data):
                nonlocal saved_count
                pending_by_id = {
                    str(entity.id).strip(): entity
                    for entity in valid_entities
                }
                existing = list(data.get(self._data_key, []))
                next_entities: List[Dict[str, Any]] = []
                saved_count = 0

                for raw in existing:
                    raw_id = str(raw.get("id") or "").strip()
                    entity = pending_by_id.pop(raw_id, None)
                    if entity is None:
                        next_entities.append(raw)
                    else:
                        next_entities.append(entity.to_dict())
                        saved_count += 1

                # 剩余的是新增实体
                for entity in pending_by_id.values():
                    next_entities.append(entity.to_dict())
                    saved_count += 1

                if saved_count == 0:
                    return None

                data[self._data_key] = next_entities
                self._touch_data(data, next_entities)
                return data

            return saved_count if self._storage.atomic_update(
                update_data,
                catalog_index_changed_ids=valid_entity_ids,
            ) else 0
        except Exception as e:
            error_logger.error(f"批量保存实体失败: {e}")
            return 0

    def delete_many_by_ids(self, entity_ids: List[str]) -> int:
        wanted_ids = self._normalize_entity_ids(entity_ids)
        if not wanted_ids:
            return 0

        deleted_count = 0

        try:
            def update_data(data):
                nonlocal deleted_count
                entities = list(data.get(self._data_key, []))
                next_entities = [
                    item
                    for item in entities
                    if str(item.get("id") or "").strip() not in wanted_ids
                ]
                deleted_count = len(entities) - len(next_entities)
                if deleted_count == 0:
                    return None
                data[self._data_key] = next_entities
                self._touch_data(data, next_entities)
                return data

            return deleted_count if self._storage.atomic_update(update_data, catalog_index_changed_ids=wanted_ids) else 0
        except Exception as e:
            error_logger.error(f"批量删除实体失败: {e}")
            return 0

    @staticmethod
    def _normalize_entity_ids(entity_ids: List[str]) -> set[str]:
        return {
            str(entity_id or "").strip()
            for entity_id in (entity_ids or [])
            if str(entity_id or "").strip()
        }


class BaseJsonRepository(JsonRepositoryBatchMixin[T], BaseRepository[T], Generic[T]):
    
    def save(self, entity: T) -> bool:
        try:
            def update_data(data):
                entities = data.get(self._data_key, [])
                index = next((i for i, e in enumerate(entities) if e["id"] == entity.id), -1)
                
                if index >= 0:
                    entities[index] = entity.to_dict()
                else:
                    entities.append(entity.to_dict())
                
                data[self._data_key] = entities
                self._touch_data(data, entities)
                return data
            
            return self._storage.atomic_update(update_data, catalog_index_changed_ids=[entity.id])
        except Exception as e:
            error_logger.error(f"保存实体失败: {e}")
            return False
    
    def delete(self, entity_id: str) -> bool:
        try:
            def update_data(data):
                entities = data.get(self._data_key, [])
                entities = [e for e in entities if e["id"] != entity_id]
                data[self._data_key] = entities
                self._touch_data(data, entities)
                return data
            
            return self._storage.atomic_update(update_data)
        except Exception as e:
            error_logger.error(f"删除实体失败: {e}")
            return False


class BaseContentJsonRepository(BaseJsonRepository[C], Generic[C]):
    
    def search(self, keyword: str) -> List[C]:
        data = self._storage.read()
        entities = data.get(self._data_key, [])
        keyword_lower = keyword.lower()
        
        results = []
        for e in entities:
            if (keyword_lower in e.get("title", "").lower() or
                keyword_lower in e.get("creator", "").lower() or
                keyword_lower in e.get("author", "").lower() or
                keyword_lower in e.get("desc", "").lower()):
                results.append(self._get_entity_class().from_dict(e))
        
        return results
    
    def filter_by_tags(self, include_tags: List[str], exclude_tags: List[str]) -> List[C]:
        data = self._storage.read()
        entities = data.get(self._data_key, [])
        
        results = []
        for e in entities:
            if e.get("is_deleted", False):
                continue
            
            entity_tags = set(e.get("tag_ids", []))
            
            if include_tags and not all(t in entity_tags for t in include_tags):
                continue
            
            if exclude_tags and any(t in entity_tags for t in exclude_tags):
                continue
            
            results.append(self._get_entity_class().from_dict(e))
        
        return results
    
    def get_by_tag(self, tag_id: str) -> List[C]:
        data = self._storage.read()
        entities = data.get(self._data_key, [])
        
        results = []
        for e in entities:
            if e.get("is_deleted", False):
                continue
            
            if tag_id in e.get("tag_ids", []):
                results.append(self._get_entity_class().from_dict(e))
        
        return results
    
    def get_by_list(self, list_id: str) -> List[C]:
        data = self._storage.read()
        entities = data.get(self._data_key, [])
        
        results = []
        for e in entities:
            if e.get("is_deleted", False):
                continue
            
            if list_id in e.get("list_ids", []):
                results.append(self._get_entity_class().from_dict(e))
        
        return results
    
    def filter_multi(self, include_tags: List[str] = None, exclude_tags: List[str] = None,
                     authors: List[str] = None, list_ids: List[str] = None) -> List[C]:
        data = self._storage.read()
        entities = data.get(self._data_key, [])
        
        results = []
        for e in entities:
            if e.get("is_deleted", False):
                continue
            
            entity_tags = set(e.get("tag_ids", []))
            entity_author = e.get("author", "") or e.get("creator", "")
            entity_list_ids = set(e.get("list_ids", []))
            
            if include_tags and not all(t in entity_tags for t in include_tags):
                continue
            
            if exclude_tags and any(t in entity_tags for t in exclude_tags):
                continue
            
            if authors and entity_author not in authors:
                continue
            
            if list_ids and not any(lid in entity_list_ids for lid in list_ids):
                continue
            
            results.append(self._get_entity_class().from_dict(e))
        
        return results


class BaseCreatorJsonRepository(BaseJsonRepository[R], Generic[R]):
    
    def get_by_name(self, name: str) -> Optional[R]:
        data = self._storage.read()
        entities = data.get(self._data_key, [])
        entity_data = next((e for e in entities if e.get("name") == name), None)
        return self._get_entity_class().from_dict(entity_data) if entity_data else None
    
    def exists_by_name(self, name: str) -> bool:
        data = self._storage.read()
        entities = data.get(self._data_key, [])
        return any(e.get("name") == name for e in entities)
    
    def get_subscribed(self) -> List[R]:
        data = self._storage.read()
        entities = data.get(self._data_key, [])
        
        results = []
        for e in entities:
            if e.get("is_subscribed", False):
                results.append(self._get_entity_class().from_dict(e))
        
        return results
