"""
演员仓储接口
"""

from abc import abstractmethod
from typing import List, Optional
from domain.base.repository import BaseCreatorRepository
from .entity import ActorSubscription


class ActorRepository(BaseCreatorRepository):
    
    @abstractmethod
    def get_by_id(self, entity_id: str) -> Optional[ActorSubscription]:
        pass
    
    @abstractmethod
    def get_all(self) -> List[ActorSubscription]:
        pass
    
    @abstractmethod
    def save(self, entity: ActorSubscription) -> bool:
        pass
    
    @abstractmethod
    def get_by_name(self, name: str) -> Optional[ActorSubscription]:
        pass
    
    @abstractmethod
    def exists_by_name(self, name: str) -> bool:
        pass
    
    @abstractmethod
    def get_subscribed(self) -> List[ActorSubscription]:
        pass
    
    @abstractmethod
    def get_by_actor_id(self, actor_id: str) -> Optional[ActorSubscription]:
        pass
