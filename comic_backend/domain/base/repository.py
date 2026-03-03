from abc import ABC, abstractmethod
from typing import List, Optional, TypeVar, Generic

from domain.base.entity import BaseEntity, BaseContent, BaseCreator

T = TypeVar('T', bound=BaseEntity)


class BaseRepository(ABC, Generic[T]):
    
    @abstractmethod
    def get_by_id(self, entity_id: str) -> Optional[T]:
        pass
    
    @abstractmethod
    def get_all(self) -> List[T]:
        pass
    
    @abstractmethod
    def save(self, entity: T) -> bool:
        pass
    
    @abstractmethod
    def delete(self, entity_id: str) -> bool:
        pass


class BaseContentRepository(BaseRepository[BaseContent]):
    
    @abstractmethod
    def search(self, keyword: str) -> List[BaseContent]:
        pass
    
    @abstractmethod
    def filter_by_tags(self, include_tags: List[str], exclude_tags: List[str]) -> List[BaseContent]:
        pass
    
    @abstractmethod
    def get_by_tag(self, tag_id: str) -> List[BaseContent]:
        pass
    
    @abstractmethod
    def get_by_list(self, list_id: str) -> List[BaseContent]:
        pass


class BaseCreatorRepository(BaseRepository[BaseCreator]):
    
    @abstractmethod
    def get_by_name(self, name: str) -> Optional[BaseCreator]:
        pass
    
    @abstractmethod
    def exists_by_name(self, name: str) -> bool:
        pass
    
    @abstractmethod
    def get_subscribed(self) -> List[BaseCreator]:
        pass
