from abc import ABC, abstractmethod
from typing import List, Optional
from .entity import Recommendation


class RecommendationRepository(ABC):
    """推荐漫画仓库接口"""
    
    @abstractmethod
    def get_by_id(self, recommendation_id: str) -> Optional[Recommendation]:
        """根据ID获取推荐漫画"""
        pass
    
    @abstractmethod
    def get_all(self) -> List[Recommendation]:
        """获取所有推荐漫画"""
        pass
    
    @abstractmethod
    def save(self, recommendation: Recommendation) -> bool:
        """保存推荐漫画"""
        pass
    
    @abstractmethod
    def delete(self, recommendation_id: str) -> bool:
        """删除推荐漫画"""
        pass
    
    @abstractmethod
    def search(self, keyword: str) -> List[Recommendation]:
        """搜索推荐漫画"""
        pass
    
    @abstractmethod
    def filter_by_tags(self, include_tags: List[str], exclude_tags: List[str]) -> List[Recommendation]:
        """根据标签筛选"""
        pass
