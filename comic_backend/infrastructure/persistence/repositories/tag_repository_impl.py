from typing import List, Optional
from domain.tag import Tag, TagRepository
from infrastructure.persistence.json_storage import JsonStorage
from infrastructure.logger import error_logger
from core.utils import get_current_time, generate_id


class TagJsonRepository(TagRepository):
    def __init__(self, storage: JsonStorage = None):
        self._storage = storage or JsonStorage()
    
    def get_by_id(self, tag_id: str) -> Optional[Tag]:
        data = self._storage.read()
        tags = data.get("tags", [])
        tag_data = next((t for t in tags if t["id"] == tag_id), None)
        return Tag.from_dict(tag_data) if tag_data else None
    
    def get_all(self) -> List[Tag]:
        data = self._storage.read()
        tags = data.get("tags", [])
        return [Tag.from_dict(t) for t in tags]
    
    def save(self, tag: Tag) -> bool:
        try:
            data = self._storage.read()
            tags = data.get("tags", [])
            
            index = next((i for i, t in enumerate(tags) if t["id"] == tag.id), -1)
            
            if index >= 0:
                tags[index] = tag.to_dict()
            else:
                tags.append(tag.to_dict())
            
            data["tags"] = tags
            data["last_updated"] = get_current_time()
            
            return self._storage.write(data)
        except Exception as e:
            error_logger.error(f"保存标签失败: {e}")
            return False
    
    def delete(self, tag_id: str) -> bool:
        try:
            data = self._storage.read()
            tags = data.get("tags", [])
            comics = data.get("comics", [])
            
            tags = [t for t in tags if t["id"] != tag_id]
            
            for comic in comics:
                if tag_id in comic.get("tag_ids", []):
                    comic["tag_ids"] = [t for t in comic.get("tag_ids", []) if t != tag_id]
            
            data["tags"] = tags
            data["comics"] = comics
            data["last_updated"] = get_current_time()
            
            return self._storage.write(data)
        except Exception as e:
            error_logger.error(f"删除标签失败: {e}")
            return False
    
    def exists_by_name(self, name: str) -> bool:
        data = self._storage.read()
        tags = data.get("tags", [])
        return any(t.get("name") == name for t in tags)
    
    def create(self, name: str) -> Optional[Tag]:
        if self.exists_by_name(name):
            return None
        
        tag = Tag(
            id=generate_id("tag"),
            name=name,
            create_time=get_current_time()
        )
        
        if self.save(tag):
            return tag
        return None
