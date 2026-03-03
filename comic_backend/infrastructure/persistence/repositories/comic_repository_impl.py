from typing import List, Optional
from domain.comic import Comic, ComicRepository
from domain.comic.entity import Comic as ComicEntity
from infrastructure.persistence.json_storage import JsonStorage
from infrastructure.persistence.repositories.base_repository_impl import BaseContentJsonRepository
from infrastructure.logger import app_logger, error_logger
from core.utils import get_current_date


class ComicJsonRepository(ComicRepository):
    def __init__(self, storage: JsonStorage = None):
        self._storage = storage or JsonStorage()
    
    def get_by_id(self, comic_id: str) -> Optional[Comic]:
        data = self._storage.read()
        comics = data.get("comics", [])
        comic_data = next((c for c in comics if c["id"] == comic_id), None)
        return Comic.from_dict(comic_data) if comic_data else None
    
    def get_all(self) -> List[Comic]:
        data = self._storage.read()
        comics = data.get("comics", [])
        return [Comic.from_dict(c) for c in comics]
    
    def save(self, comic: Comic) -> bool:
        try:
            app_logger.info(f"[ComicRepo.save] 保存漫画: id={comic.id}, list_ids={comic.list_ids}")
            
            def update_data(data):
                comics = data.get("comics", [])
                
                index = next((i for i, c in enumerate(comics) if c["id"] == comic.id), -1)
                
                if index >= 0:
                    comics[index] = comic.to_dict()
                else:
                    comics.append(comic.to_dict())
                
                data["comics"] = comics
                data["total_comics"] = len(comics)
                data["last_updated"] = get_current_date()
                return data
            
            result = self._storage.atomic_update(update_data)
            app_logger.info(f"[ComicRepo.save] 写入结果: {result}")
            return result
        except Exception as e:
            error_logger.error(f"保存漫画失败: {e}")
            return False
    
    def delete(self, comic_id: str) -> bool:
        try:
            def update_data(data):
                comics = data.get("comics", [])
                comics = [c for c in comics if c["id"] != comic_id]
                data["comics"] = comics
                data["total_comics"] = len(comics)
                data["last_updated"] = get_current_date()
                return data
            
            return self._storage.atomic_update(update_data)
        except Exception as e:
            error_logger.error(f"删除漫画失败: {e}")
            return False
    
    def search(self, keyword: str) -> List[Comic]:
        data = self._storage.read()
        comics = data.get("comics", [])
        keyword_lower = keyword.lower()
        
        results = []
        for c in comics:
            if (keyword_lower in c.get("title", "").lower() or
                keyword_lower in c.get("author", "").lower() or
                keyword_lower in c.get("desc", "").lower()):
                results.append(Comic.from_dict(c))
        
        return results
    
    def filter_by_tags(self, include_tags: List[str], exclude_tags: List[str]) -> List[Comic]:
        data = self._storage.read()
        comics = data.get("comics", [])
        
        results = []
        for c in comics:
            comic_tags = set(c.get("tag_ids", []))
            
            if include_tags and not all(t in comic_tags for t in include_tags):
                continue
            
            if exclude_tags and any(t in comic_tags for t in exclude_tags):
                continue
            
            results.append(Comic.from_dict(c))
        
        return results


class ComicJsonRepositoryV2(BaseContentJsonRepository):
    _data_key = "comics"
    
    def __init__(self, storage: JsonStorage = None):
        self._storage = storage or JsonStorage()
    
    def _get_entity_class(self):
        return Comic
    
    def save(self, entity: Comic) -> bool:
        try:
            app_logger.info(f"[ComicRepo.save] 保存漫画: id={entity.id}, list_ids={entity.list_ids}")
            
            def update_data(data):
                entities = data.get(self._data_key, [])
                index = next((i for i, e in enumerate(entities) if e["id"] == entity.id), -1)
                
                if index >= 0:
                    entities[index] = entity.to_dict()
                else:
                    entities.append(entity.to_dict())
                
                data[self._data_key] = entities
                data["total_comics"] = len(entities)
                data["last_updated"] = get_current_date()
                return data
            
            result = self._storage.atomic_update(update_data)
            app_logger.info(f"[ComicRepo.save] 写入结果: {result}")
            return result
        except Exception as e:
            error_logger.error(f"保存漫画失败: {e}")
            return False
    
    def search(self, keyword: str) -> List[Comic]:
        data = self._storage.read()
        entities = data.get(self._data_key, [])
        keyword_lower = keyword.lower()
        
        results = []
        for e in entities:
            if (keyword_lower in e.get("title", "").lower() or
                keyword_lower in e.get("author", "").lower() or
                keyword_lower in e.get("creator", "").lower() or
                keyword_lower in e.get("desc", "").lower()):
                results.append(Comic.from_dict(e))
        
        return results
