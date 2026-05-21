"""
演员实体
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from domain.base.entity import BaseCreator
from core.enums import ContentType


@dataclass
class ActorSubscription(BaseCreator):
    content_type: ContentType = ContentType.VIDEO
    
    actor_id: str = ""
    actor_refs: List[Dict[str, Any]] = field(default_factory=list)
    
    @classmethod
    def from_dict(cls, data: dict) -> "ActorSubscription":
        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            avatar_url=data.get("avatar_url", ""),
            works_count=data.get("works_count", 0),
            is_subscribed=data.get("is_subscribed", True),
            subscribe_time=data.get("subscribe_time", data.get("create_time")),
            last_check_time=data.get("last_check_time", ""),
            last_work_id=data.get("last_work_id", ""),
            last_work_title=data.get("last_work_title", ""),
            new_work_count=data.get("new_work_count", 0),
            content_type=ContentType.VIDEO,
            actor_id=data.get("actor_id", ""),
            actor_refs=[
                dict(item or {})
                for item in (data.get("actor_refs") or [])
                if isinstance(item, dict)
            ]
        )
    
    def to_dict(self) -> dict:
        base_dict = super().to_dict()
        base_dict["actor_id"] = self.actor_id
        base_dict["actor_refs"] = [
            dict(item or {})
            for item in (self.actor_refs or [])
            if isinstance(item, dict)
        ]
        return base_dict
