from abc import ABC, abstractmethod
from typing import List, Optional
from domain.author.entity import AuthorSubscription


class AuthorRepository(ABC):
    @abstractmethod
    def get_all(self) -> List[AuthorSubscription]:
        pass
    
    @abstractmethod
    def get_by_id(self, author_id: str) -> Optional[AuthorSubscription]:
        pass
    
    @abstractmethod
    def get_by_name(self, name: str) -> Optional[AuthorSubscription]:
        pass
    
    @abstractmethod
    def save(self, author: AuthorSubscription) -> bool:
        pass
    
    @abstractmethod
    def delete(self, author_id: str) -> bool:
        pass
    
    @abstractmethod
    def exists_by_name(self, name: str) -> bool:
        pass
