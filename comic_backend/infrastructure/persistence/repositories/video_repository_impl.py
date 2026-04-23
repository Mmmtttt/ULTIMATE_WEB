"""
视频仓储实现
"""

from typing import List, Optional
from infrastructure.persistence.repositories.base_repository_impl import BaseContentJsonRepository
from infrastructure.persistence.json_storage import JsonStorage
from domain.video.entity import Video


class VideoJsonRepository(BaseContentJsonRepository[Video]):
    
    def __init__(self):
        from core.constants import VIDEO_JSON_FILE as ACTIVE_VIDEO_JSON_FILE

        self._storage = JsonStorage(ACTIVE_VIDEO_JSON_FILE)
        self._data_key = "videos"
    
    def _get_entity_class(self):
        return Video
    
    def get_by_code(self, code: str) -> Optional[Video]:
        data = self._storage.read()
        entities = data.get(self._data_key, [])
        entity_data = next((e for e in entities if e.get("code", "").upper() == code.upper()), None)
        return Video.from_dict(entity_data) if entity_data else None
    
    def search_by_keyword(self, keyword: str) -> List[Video]:
        data = self._storage.read()
        entities = data.get(self._data_key, [])
        keyword_lower = keyword.lower()
        
        results = []
        for e in entities:
            if (keyword_lower in e.get("title", "").lower() or
                keyword_lower in e.get("code", "").lower() or
                keyword_lower in e.get("creator", "").lower() or
                keyword_lower in str(e.get("actors", [])).lower()):
                results.append(Video.from_dict(e))
        
        return results
