from typing import List, Optional
from domain.tag import Tag, TagRepository
from infrastructure.persistence.json_storage import JsonStorage
from core.constants import RECOMMENDATION_JSON_FILE
from infrastructure.logger import error_logger
from core.utils import get_current_time, generate_id
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
            
            tags = [t for t in tags if t["id"] != tag_id]
            
            for comic in comics:
                if tag_id in comic.get("tag_ids", []):
                    comic["tag_ids"] = [t for t in comic.get("tag_ids", []) if t != tag_id]
            
            for video in videos:
                if tag_id in video.get("tag_ids", []):
                    video["tag_ids"] = [t for t in video.get("tag_ids", []) if t != tag_id]
            
            data["tags"] = tags
            data["comics"] = comics
            data["videos"] = videos
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


class RecommendationTagJsonRepository(TagJsonRepository):
    """推荐页标签仓库 - 使用推荐页数据库"""
    
    def __init__(self):
        super().__init__(storage=JsonStorage(RECOMMENDATION_JSON_FILE))
    
    def delete(self, tag_id: str) -> bool:
        try:
            data = self._storage.read()
            tags = data.get("tags", [])
            recommendations = data.get("recommendations", [])
            
            tags = [t for t in tags if t["id"] != tag_id]
            
            for rec in recommendations:
                if tag_id in rec.get("tag_ids", []):
                    rec["tag_ids"] = [t for t in rec.get("tag_ids", []) if t != tag_id]
            
            data["tags"] = tags
            data["recommendations"] = recommendations
            data["last_updated"] = get_current_time()
            
            return self._storage.write(data)
        except Exception as e:
            error_logger.error(f"删除推荐标签失败: {e}")
            return False
