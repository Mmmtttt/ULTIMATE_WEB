from dataclasses import dataclass
from typing import Optional

from domain.base.entity import BaseCreator
from core.enums import ContentType


@dataclass
class AuthorSubscription(BaseCreator):
    content_type: ContentType = ContentType.COMIC
    
    @classmethod
    def from_dict(cls, data: dict) -> "AuthorSubscription":
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
            content_type=ContentType.COMIC
        )
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "create_time": self.subscribe_time or "",
            "last_check_time": self.last_check_time,
            "last_work_id": self.last_work_id,
            "last_work_title": self.last_work_title,
            "new_work_count": self.new_work_count
        }
    
    @property
    def create_time(self) -> str:
        return self.subscribe_time or ""
    
    @create_time.setter
    def create_time(self, value: str):
        self.subscribe_time = value
