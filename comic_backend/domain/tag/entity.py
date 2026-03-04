from dataclasses import dataclass
from typing import List
from datetime import datetime
from core.enums import ContentType


@dataclass
class Tag:
    id: str
    name: str
    content_type: ContentType = ContentType.COMIC
    create_time: str = ""
    
    @classmethod
    def from_dict(cls, data: dict) -> "Tag":
        content_type = data.get("content_type", ContentType.COMIC)
        if isinstance(content_type, str):
            content_type = ContentType(content_type)
        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            content_type=content_type,
            create_time=data.get("create_time", "")
        )
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "content_type": self.content_type.value,
            "create_time": self.create_time
        }
    
    def update_name(self, name: str):
        self.name = name
