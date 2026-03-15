from abc import ABC, abstractmethod
from typing import List, Optional
from .entity import VideoRecommendation


class VideoRecommendationRepository(ABC):
    """推荐视频仓库接口"""
    
    @abstractmethod
    def get_by_id(self, video_recommendation_id: str) -> Optional[VideoRecommendation]:
        """根据ID获取推荐视频"""
        pass
    
    @abstractmethod
    def get_all(self) -> List[VideoRecommendation]:
        """获取所有推荐视频"""
        pass
    
    @abstractmethod
    def save(self, video_recommendation: VideoRecommendation) -> bool:
        """保存推荐视频"""
        pass
    
    @abstractmethod
    def delete(self, video_recommendation_id: str) -> bool:
        """删除推荐视频"""
        pass
    
    @abstractmethod
    def search(self, keyword: str) -> List[VideoRecommendation]:
        """搜索推荐视频"""
        pass

    @abstractmethod
    def get_by_code(self, code: str) -> Optional[VideoRecommendation]:
        """根据番号获取推荐视频"""
        pass
    
    @abstractmethod
    def filter_by_tags(self, include_tags: List[str], exclude_tags: List[str]) -> List[VideoRecommendation]:
        """根据标签筛选"""
        pass
