from typing import List, Optional, TypeVar, Generic, Dict, Any
from abc import abstractmethod

from domain.base.entity import BaseEntity, BaseContent, BaseCreator
from domain.base.repository import BaseRepository, BaseContentRepository, BaseCreatorRepository
from infrastructure.persistence.json_storage import JsonStorage
from infrastructure.logger import app_logger, error_logger
from core.utils import get_current_time, get_current_date

T = TypeVar('T', bound=BaseEntity)
C = TypeVar('C', bound=BaseContent)
R = TypeVar('R', bound=BaseCreator)


class BaseJsonRepository(BaseRepository[T], Generic[T]):
    _storage: JsonStorage
    _data_key: str
    
    def _get_entity_class(self):
        raise NotImplementedError
    
    def get_by_id(self, entity_id: str) -> Optional[T]:
        data = self._storage.read()
        entities = data.get(self._data_key, [])
        entity_data = next((e for e in entities if e["id"] == entity_id), None)
        return self._get_entity_class().from_dict(entity_data) if entity_data else None
    
    def get_all(self) -> List[T]:
        data = self._storage.read()
        entities = data.get(self._data_key, [])
        return [self._get_entity_class().from_dict(e) for e in entities]
    
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
                data["last_updated"] = get_current_time()
                return data
            
            return self._storage.atomic_update(update_data)
        except Exception as e:
            error_logger.error(f"保存实体失败: {e}")
            return False
    
    def delete(self, entity_id: str) -> bool:
        try:
            def update_data(data):
                entities = data.get(self._data_key, [])
                entities = [e for e in entities if e["id"] != entity_id]
                data[self._data_key] = entities
                data["last_updated"] = get_current_time()
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
            if tag_id in e.get("tag_ids", []):
                results.append(self._get_entity_class().from_dict(e))
        
        return results
    
    def get_by_list(self, list_id: str) -> List[C]:
        data = self._storage.read()
        entities = data.get(self._data_key, [])
        
        results = []
        for e in entities:
            if list_id in e.get("list_ids", []):
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
