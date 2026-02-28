from abc import ABC, abstractmethod
from typing import List as ListType, Optional
from .entity import List


class ListRepository(ABC):
    @abstractmethod
    def get_by_id(self, list_id: str) -> Optional[List]:
        pass
    
    @abstractmethod
    def get_all(self) -> ListType[List]:
        pass
    
    @abstractmethod
    def save(self, list_obj: List) -> bool:
        pass
    
    @abstractmethod
    def delete(self, list_id: str) -> bool:
        pass
    
    @abstractmethod
    def exists_by_name(self, name: str) -> bool:
        pass
