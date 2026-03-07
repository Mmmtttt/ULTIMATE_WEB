from dataclasses import dataclass
from typing import List as ListType, Optional
from datetime import datetime
from core.enums import ContentType


@dataclass
class List:
    id: str
    name: str
    desc: str = ""
    content_type: ContentType = ContentType.COMIC
    is_default: bool = False
    create_time: str = ""
    
    @classmethod
    def from_dict(cls, data: dict) -> "List":
        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            desc=data.get("desc", ""),
            content_type=ContentType(data.get("content_type", "comic")),
            is_default=data.get("is_default", False),
            create_time=data.get("create_time", "")
        )
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "desc": self.desc,
            "content_type": self.content_type.value,
            "is_default": self.is_default,
            "create_time": self.create_time
        }
    
    def update(self, name: str = None, desc: str = None):
        if name:
            self.name = name
        if desc is not None:
            self.desc = desc


DEFAULT_COMIC_FAVORITES_LIST = List(
    id="list_favorites_comic",
    name="我的收藏",
    desc="默认漫画收藏清单",
    content_type=ContentType.COMIC,
    is_default=True,
    create_time=""
)

DEFAULT_VIDEO_FAVORITES_LIST = List(
    id="list_favorites_video",
    name="我的收藏",
    desc="默认视频收藏清单",
    content_type=ContentType.VIDEO,
    is_default=True,
    create_time=""
)
