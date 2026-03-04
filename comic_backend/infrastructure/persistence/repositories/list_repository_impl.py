from typing import List as ListType, Optional
from domain.list import List, ListRepository
from infrastructure.persistence.json_storage import JsonStorage
from infrastructure.logger import error_logger
from core.utils import get_current_time, generate_id


class ListJsonRepository(ListRepository):
    def __init__(self, storage: JsonStorage = None):
        self._storage = storage or JsonStorage()
    
    def get_by_id(self, list_id: str) -> Optional[List]:
        data = self._storage.read()
        lists = data.get("lists", [])
        list_data = next((l for l in lists if l["id"] == list_id), None)
        return List.from_dict(list_data) if list_data else None
    
    def get_all(self) -> ListType[List]:
        data = self._storage.read()
        lists = data.get("lists", [])
        return [List.from_dict(l) for l in lists]
    
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
            data = self._storage.read()
            lists = data.get("lists", [])
            comics = data.get("comics", [])
            videos = data.get("videos", [])
            
            lists = [l for l in lists if l["id"] != list_id]
            
            for comic in comics:
                if list_id in comic.get("list_ids", []):
                    comic["list_ids"] = [lid for lid in comic.get("list_ids", []) if lid != list_id]
            
            for video in videos:
                if list_id in video.get("list_ids", []):
                    video["list_ids"] = [lid for lid in video.get("list_ids", []) if lid != list_id]
            
            data["lists"] = lists
            data["comics"] = comics
            data["videos"] = videos
            data["last_updated"] = get_current_time()
            
            return self._storage.write(data)
        except Exception as e:
            error_logger.error(f"删除清单失败: {e}")
            return False
    
    def exists_by_name(self, name: str) -> bool:
        data = self._storage.read()
        lists = data.get("lists", [])
        return any(l.get("name") == name for l in lists)
    
    def create(self, name: str, desc: str = "") -> Optional[List]:
        if self.exists_by_name(name):
            return None
        
        list_obj = List(
            id=generate_id("list"),
            name=name,
            desc=desc,
            is_default=False,
            create_time=get_current_time()
        )
        
        if self.save(list_obj):
            return list_obj
        return None
    
    def get_comic_count(self, list_id: str) -> int:
        data = self._storage.read()
        comics = data.get("comics", [])
        return sum(1 for c in comics if list_id in c.get("list_ids", []))
    
    def get_video_count(self, list_id: str) -> int:
        data = self._storage.read()
        videos = data.get("videos", [])
        return sum(1 for v in videos if list_id in v.get("list_ids", []))
    
    def ensure_default_list(self) -> bool:
        data = self._storage.read()
        lists = data.get("lists", [])
        
        if not any(l.get("id") == "list_favorites" for l in lists):
            from domain.list.entity import DEFAULT_FAVORITES_LIST
            default_list = DEFAULT_FAVORITES_LIST
            default_list.create_time = get_current_time()
            lists.append(default_list.to_dict())
            data["lists"] = lists
            return self._storage.write(data)
        return True
