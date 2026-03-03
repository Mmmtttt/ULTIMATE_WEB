"""
视频仓储接口
"""

from abc import abstractmethod
from typing import List, Optional
from domain.base.repository import BaseContentRepository
from .entity import Video


class VideoRepository(BaseContentRepository):
    
    @abstractmethod
    def get_by_id(self, entity_id: str) -> Optional[Video]:
        pass
    
    @abstractmethod
    def get_all(self) -> List[Video]:
        pass
    
    @abstractmethod
    def save(self, entity: Video) -> bool:
        pass
    
    @abstractmethod
    def search(self, keyword: str) -> List[Video]:
        pass
    
    @abstractmethod
    def filter_by_tags(self, include_tags: List[str], exclude_tags: List[str]) -> List[Video]:
        pass
    
    @abstractmethod
    def get_by_tag(self, tag_id: str) -> List[Video]:
        pass
    
    @abstractmethod
    def get_by_list(self, list_id: str) -> List[Video]:
        pass
    
    @abstractmethod
    def get_by_code(self, code: str) -> Optional[Video]:
        pass
    
    @abstractmethod
    def search_by_keyword(self, keyword: str) -> List[Video]:
        pass
