from abc import ABC, abstractmethod
from typing import List, Optional
from .entity import Comic


class ComicRepository(ABC):
    @abstractmethod
    def get_by_id(self, comic_id: str) -> Optional[Comic]:
        pass
    
    @abstractmethod
    def get_all(self) -> List[Comic]:
        pass
    
    @abstractmethod
    def save(self, comic: Comic) -> bool:
        pass
    
    @abstractmethod
    def delete(self, comic_id: str) -> bool:
        pass
    
    @abstractmethod
    def search(self, keyword: str) -> List[Comic]:
        pass
    
    @abstractmethod
    def filter_by_tags(self, include_tags: List[str], exclude_tags: List[str]) -> List[Comic]:
        pass
