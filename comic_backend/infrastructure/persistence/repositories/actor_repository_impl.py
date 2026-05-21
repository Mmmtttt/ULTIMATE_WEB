"""
演员仓储实现
"""

from typing import Optional
from infrastructure.persistence.repositories.base_repository_impl import BaseCreatorJsonRepository
from infrastructure.persistence.json_storage import JsonStorage
from domain.actor.entity import ActorSubscription


class ActorJsonRepository(BaseCreatorJsonRepository[ActorSubscription]):
    
    def __init__(self):
        from core.constants import ACTOR_JSON_FILE as ACTIVE_ACTOR_JSON_FILE

        self._storage = JsonStorage(ACTIVE_ACTOR_JSON_FILE)
        self._data_key = "actors"
    
    def _get_entity_class(self):
        return ActorSubscription
    
    def get_by_actor_id(self, actor_id: str) -> Optional[ActorSubscription]:
        normalized_actor_id = str(actor_id or "").strip()
        if not normalized_actor_id:
            return None
        data = self._storage.read()
        entities = data.get(self._data_key, [])
        entity_data = None
        for entity in entities:
            if str(entity.get("actor_id") or "").strip() == normalized_actor_id:
                entity_data = entity
                break
            for ref in entity.get("actor_refs") or []:
                if not isinstance(ref, dict):
                    continue
                if str(ref.get("actor_id") or ref.get("id") or "").strip() == normalized_actor_id:
                    entity_data = entity
                    break
            if entity_data:
                break
        return ActorSubscription.from_dict(entity_data) if entity_data else None
