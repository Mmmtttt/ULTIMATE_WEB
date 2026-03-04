from abc import ABC, abstractmethod
from typing import List, Optional
from .entity import Tag
from core.enums import ContentType


class TagRepository(ABC):
    @abstractmethod
    def get_by_id(self, tag_id: str) -> Optional[Tag]:
        pass
    
    @abstractmethod
    def get_all(self, content_type: ContentType = None) -> List[Tag]:
        pass
    
    @abstractmethod
    def save(self, tag: Tag) -> bool:
        pass
    
    @abstractmethod
    def delete(self, tag_id: str) -> bool:
        pass
    
    @abstractmethod
    def exists_by_name(self, name: str, content_type: ContentType = None) -> bool:
        pass
