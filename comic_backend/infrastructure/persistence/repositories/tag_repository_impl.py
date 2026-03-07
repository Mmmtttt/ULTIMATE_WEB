from typing import List, Optional
from domain.tag import Tag, TagRepository
from infrastructure.persistence.json_storage import JsonStorage
from infrastructure.logger import error_logger
from core.utils import get_current_time
from core.enums import ContentType


class TagJsonRepository(TagRepository):
    def __init__(self, storage: JsonStorage = None):
        self._storage = storage or JsonStorage()
    
    def get_by_id(self, tag_id: str) -> Optional[Tag]:
        data = self._storage.read()
        tags = data.get("tags", [])
        tag_data = next((t for t in tags if t["id"] == tag_id), None)
        return Tag.from_dict(tag_data) if tag_data else None
    
    def get_all(self, content_type: ContentType = None) -> List[Tag]:
        data = self._storage.read()
        tags = data.get("tags", [])
        
        if content_type:
            tags = [t for t in tags if t.get("content_type", ContentType.COMIC.value) == content_type.value]
        
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
            videos = data.get("videos", [])
            recommendations = data.get("recommendations", [])
            
            tags = [t for t in tags if t["id"] != tag_id]
            
            for comic in comics:
                if tag_id in comic.get("tag_ids", []):
                    comic["tag_ids"] = [t for t in comic.get("tag_ids", []) if t != tag_id]
            
            for video in videos:
                if tag_id in video.get("tag_ids", []):
                    video["tag_ids"] = [t for t in video.get("tag_ids", []) if t != tag_id]
            
            for rec in recommendations:
                if tag_id in rec.get("tag_ids", []):
                    rec["tag_ids"] = [t for t in rec.get("tag_ids", []) if t != tag_id]
            
            data["tags"] = tags
            data["comics"] = comics
            data["videos"] = videos
            data["recommendations"] = recommendations
            data["last_updated"] = get_current_time()
            
            return self._storage.write(data)
        except Exception as e:
            error_logger.error(f"删除标签失败: {e}")
            return False
    
    def exists_by_name(self, name: str, content_type: ContentType = None) -> bool:
        data = self._storage.read()
        tags = data.get("tags", [])
        
        if content_type:
            tags = [t for t in tags if t.get("content_type", ContentType.COMIC.value) == content_type.value]
        
        return any(t.get("name") == name for t in tags)
    
    def _get_next_tag_id(self, tags: List[dict]) -> str:
        max_tag_num = 0
        for tag in tags:
            if tag["id"].startswith("tag_"):
                try:
                    num = int(tag["id"][4:])
                    max_tag_num = max(max_tag_num, num)
                except ValueError:
                    pass
        max_tag_num += 1
        return f"tag_{max_tag_num:03d}"
    
    def create(self, name: str) -> Optional[Tag]:
        if self.exists_by_name(name):
            return None
        
        data = self._storage.read()
        tags = data.get("tags", [])
        tag_id = self._get_next_tag_id(tags)
        
        tag = Tag(
            id=tag_id,
            name=name,
            create_time=get_current_time()
        )
        
        if self.save(tag):
            return tag
        return None
