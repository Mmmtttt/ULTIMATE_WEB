"""
演员仓储实现
"""

from typing import Optional
from infrastructure.persistence.repositories.base_repository_impl import BaseCreatorJsonRepository
from infrastructure.persistence.json_storage import JsonStorage
from domain.actor.entity import ActorSubscription
from core.constants import ACTOR_JSON_FILE


class ActorJsonRepository(BaseCreatorJsonRepository[ActorSubscription]):
    
    def __init__(self):
        self._storage = JsonStorage(ACTOR_JSON_FILE)
        self._data_key = "actors"
    
    def _get_entity_class(self):
        return ActorSubscription
    
    def get_by_actor_id(self, actor_id: str) -> Optional[ActorSubscription]:
        data = self._storage.read()
        entities = data.get(self._data_key, [])
        entity_data = next((e for e in entities if e.get("actor_id") == actor_id), None)
        return ActorSubscription.from_dict(entity_data) if entity_data else None
