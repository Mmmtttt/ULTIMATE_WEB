from typing import List as ListType, Optional
from domain.list import List, ListRepository
from domain.list.entity import DEFAULT_COMIC_FAVORITES_LIST, DEFAULT_VIDEO_FAVORITES_LIST
from infrastructure.persistence.json_storage import JsonStorage
from infrastructure.logger import error_logger
from core.utils import get_current_time, generate_id
from core.enums import ContentType


class ListJsonRepository(ListRepository):
    def __init__(self, storage: JsonStorage = None):
        if storage is not None:
            self._storage = storage
        else:
            from core.constants import LISTS_JSON_FILE as ACTIVE_LISTS_JSON_FILE

            self._storage = JsonStorage(ACTIVE_LISTS_JSON_FILE)

    @staticmethod
    def _get_content_databases():
        from core.constants import (
            JSON_FILE as ACTIVE_JSON_FILE,
            RECOMMENDATION_JSON_FILE as ACTIVE_RECOMMENDATION_JSON_FILE,
            VIDEO_JSON_FILE as ACTIVE_VIDEO_JSON_FILE,
            VIDEO_RECOMMENDATION_JSON_FILE as ACTIVE_VIDEO_RECOMMENDATION_JSON_FILE,
        )

        return [
            (ACTIVE_JSON_FILE, "comics"),
            (ACTIVE_RECOMMENDATION_JSON_FILE, "recommendations"),
            (ACTIVE_VIDEO_JSON_FILE, "videos"),
            (ACTIVE_VIDEO_RECOMMENDATION_JSON_FILE, "video_recommendations"),
        ]
    
    def get_by_id(self, list_id: str) -> Optional[List]:
        data = self._storage.read()
        lists = data.get("lists", [])
        list_data = next((l for l in lists if l["id"] == list_id), None)
        return List.from_dict(list_data) if list_data else None
    
    def get_all(self, content_type: ContentType = None) -> ListType[List]:
        data = self._storage.read()
        lists = data.get("lists", [])
        result = [List.from_dict(l) for l in lists]
        if content_type:
            result = [l for l in result if l.content_type == content_type]
        return result
    
    def save(self, list_obj: List) -> bool:
        try:
            data = self._storage.read()
            lists = data.get("lists", [])
            
            index = next((i for i, l in enumerate(lists) if l["id"] == list_obj.id), -1)
            
            if index >= 0:
                lists[index] = list_obj.to_dict()
            else:
                lists.append(list_obj.to_dict())
            
            data["lists"] = lists
            data["last_updated"] = get_current_time()
            
            return self._storage.write(data)
        except Exception as e:
            error_logger.error(f"保存清单失败: {e}")
            return False
    
    def delete(self, list_id: str) -> bool:
        try:
            # 从清单数据库删除清单
            data = self._storage.read()
            lists = data.get("lists", [])
            lists = [l for l in lists if l["id"] != list_id]
            data["lists"] = lists
            data["last_updated"] = get_current_time()
            
            # 保存清单数据库
            if not self._storage.write(data):
                return False
            
            # 从所有内容数据库中移除对该清单的引用
            for db_file, content_key in self._get_content_databases():
                content_storage = JsonStorage(db_file)
                content_data = content_storage.read()
                contents = content_data.get(content_key, [])
                
                for content in contents:
                    if list_id in content.get("list_ids", []):
                        content["list_ids"] = [lid for lid in content.get("list_ids", []) if lid != list_id]
                
                content_data[content_key] = contents
                content_storage.write(content_data)
            
            return True
        except Exception as e:
            error_logger.error(f"删除清单失败: {e}")
            return False
    
    def exists_by_name(self, name: str, content_type: ContentType = None) -> bool:
        data = self._storage.read()
        lists = data.get("lists", [])
        for l in lists:
            if l.get("name") == name:
                if content_type is None or l.get("content_type") == content_type.value:
                    return True
        return False
    
    def create(self, name: str, desc: str = "", content_type: ContentType = ContentType.COMIC) -> Optional[List]:
        if self.exists_by_name(name, content_type):
            return None
        
        list_obj = List(
            id=generate_id("list"),
            name=name,
            desc=desc,
            content_type=content_type,
            is_default=False,
            create_time=get_current_time()
        )
        
        if self.save(list_obj):
            return list_obj
        return None
    
    def get_comic_count(self, list_id: str) -> int:
        count = 0

        from core.constants import (
            JSON_FILE as ACTIVE_JSON_FILE,
            RECOMMENDATION_JSON_FILE as ACTIVE_RECOMMENDATION_JSON_FILE,
        )

        comic_storage = JsonStorage(ACTIVE_JSON_FILE)
        comic_data = comic_storage.read()
        comics = comic_data.get("comics", [])
        count += sum(1 for c in comics if list_id in c.get("list_ids", []) and not c.get("is_deleted"))

        rec_storage = JsonStorage(ACTIVE_RECOMMENDATION_JSON_FILE)
        rec_data = rec_storage.read()
        recommendations = rec_data.get("recommendations", [])
        count += sum(1 for r in recommendations if list_id in r.get("list_ids", []) and not r.get("is_deleted"))
        
        return count
    
    def get_video_count(self, list_id: str) -> int:
        count = 0

        from core.constants import (
            VIDEO_JSON_FILE as ACTIVE_VIDEO_JSON_FILE,
            VIDEO_RECOMMENDATION_JSON_FILE as ACTIVE_VIDEO_RECOMMENDATION_JSON_FILE,
        )

        video_storage = JsonStorage(ACTIVE_VIDEO_JSON_FILE)
        video_data = video_storage.read()
        videos = video_data.get("videos", [])
        count += sum(1 for v in videos if list_id in v.get("list_ids", []) and not v.get("is_deleted"))

        video_rec_storage = JsonStorage(ACTIVE_VIDEO_RECOMMENDATION_JSON_FILE)
        video_rec_data = video_rec_storage.read()
        video_recommendations = video_rec_data.get("video_recommendations", [])
        count += sum(1 for vr in video_recommendations if list_id in vr.get("list_ids", []) and not vr.get("is_deleted"))
        
        return count
    
    def ensure_default_list(self) -> bool:
        data = self._storage.read()
        lists = data.get("lists", [])
        modified = False
        
        if not any(l.get("id") == "list_favorites_comic" for l in lists):
            default_list = DEFAULT_COMIC_FAVORITES_LIST
            default_list.create_time = get_current_time()
            lists.append(default_list.to_dict())
            modified = True
        
        if not any(l.get("id") == "list_favorites_video" for l in lists):
            default_list = DEFAULT_VIDEO_FAVORITES_LIST
            default_list.create_time = get_current_time()
            lists.append(default_list.to_dict())
            modified = True
        
        if modified:
            data["lists"] = lists
            return self._storage.write(data)
        return True
