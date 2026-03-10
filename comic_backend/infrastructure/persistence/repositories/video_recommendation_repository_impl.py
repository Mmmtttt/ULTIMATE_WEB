"""
视频推荐仓储实现
"""

from typing import List, Optional
from infrastructure.persistence.repositories.base_repository_impl import BaseContentJsonRepository
from infrastructure.persistence.json_storage import JsonStorage
from domain.video_recommendation.entity import VideoRecommendation
from core.constants import VIDEO_RECOMMENDATION_JSON_FILE


class VideoRecommendationJsonRepository(BaseContentJsonRepository[VideoRecommendation]):
    
    def __init__(self):
        self._storage = JsonStorage(VIDEO_RECOMMENDATION_JSON_FILE)
        self._data_key = "video_recommendations"
    
    def _get_entity_class(self):
        return VideoRecommendation
    
    def search(self, keyword: str) -> List[VideoRecommendation]:
        data = self._storage.read()
        entities = data.get(self._data_key, [])
        keyword_lower = keyword.lower()
        
        results = []
        for e in entities:
            if e.get("is_deleted", False):
                continue
            
            if (keyword_lower in e.get("title", "").lower() or
                keyword_lower in e.get("code", "").lower() or
                keyword_lower in e.get("creator", "").lower() or
                keyword_lower in str(e.get("actors", [])).lower()):
                results.append(self._get_entity_class().from_dict(e))
        
        return results
