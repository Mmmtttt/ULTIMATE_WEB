"""
视频推荐仓储实现
"""

from typing import List, Optional
from domain.video.entity import Video
from infrastructure.persistence.json_storage import JsonStorage
from infrastructure.logger import app_logger, error_logger
from core.utils import get_current_date
from core.constants import VIDEO_RECOMMENDATION_JSON_FILE


class VideoRecommendationJsonRepository:
    """视频推荐 JSON 仓库实现 - 使用独立的 JSON 文件存储"""
    
    def __init__(self, storage: JsonStorage = None):
        self._storage = storage or JsonStorage(VIDEO_RECOMMENDATION_JSON_FILE)
    
    def get_by_id(self, video_id: str) -> Optional[Video]:
        """根据ID获取推荐视频"""
        data = self._storage.read()
        videos = data.get("video_recommendations", [])
        video_data = next((v for v in videos if v["id"] == video_id), None)
        return Video.from_dict(video_data) if video_data else None
    
    def get_all(self) -> List[Video]:
        """获取所有推荐视频"""
        data = self._storage.read()
        videos = data.get("video_recommendations", [])
        return [Video.from_dict(v) for v in videos]
    
    def save(self, video: Video) -> bool:
        """保存推荐视频"""
        try:
            def update_data(data):
                videos = data.get("video_recommendations", [])
                
                index = next((i for i, v in enumerate(videos) if v["id"] == video.id), -1)
                
                if index >= 0:
                    videos[index] = video.to_dict()
                else:
                    videos.append(video.to_dict())
                
                data["video_recommendations"] = videos
                data["last_updated"] = get_current_date()
                return data
            
            return self._storage.atomic_update(update_data)
        except Exception as e:
            error_logger.error(f"保存推荐视频失败: {e}")
            return False
    
    def delete(self, video_id: str) -> bool:
        """删除推荐视频"""
        try:
            def update_data(data):
                videos = data.get("video_recommendations", [])
                videos = [v for v in videos if v["id"] != video_id]
                data["video_recommendations"] = videos
                data["last_updated"] = get_current_date()
                return data
            
            return self._storage.atomic_update(update_data)
        except Exception as e:
            error_logger.error(f"删除推荐视频失败: {e}")
            return False
    
    def filter_by_tags(self, include_tags: List[str], exclude_tags: List[str]) -> List[Video]:
        """根据标签筛选"""
        data = self._storage.read()
        videos = data.get("video_recommendations", [])
        
        results = []
        for v in videos:
            if v.get("is_deleted"):
                continue
            tag_ids = set(v.get("tag_ids", []))
            
            if include_tags and not all(tag in tag_ids for tag in include_tags):
                continue
            
            if exclude_tags and any(tag in tag_ids for tag in exclude_tags):
                continue
            
            results.append(Video.from_dict(v))
        
        return results
    
    def get_by_tag(self, tag_id: str) -> List[Video]:
        """根据标签获取"""
        data = self._storage.read()
        videos = data.get("video_recommendations", [])
        
        results = []
        for v in videos:
            if v.get("is_deleted"):
                continue
            if tag_id in v.get("tag_ids", []):
                results.append(Video.from_dict(v))
        
        return results
