from dataclasses import dataclass
from typing import List as ListType
from datetime import datetime


@dataclass
class List:
    id: str
    name: str
    desc: str = ""
    is_default: bool = False
    create_time: str = ""
    
    @classmethod
    def from_dict(cls, data: dict) -> "List":
        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            desc=data.get("desc", ""),
            is_default=data.get("is_default", False),
            create_time=data.get("create_time", "")
        )
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "desc": self.desc,
            "is_default": self.is_default,
            "create_time": self.create_time
        }
    
    def update(self, name: str = None, desc: str = None):
        if name:
            self.name = name
        if desc is not None:
            self.desc = desc


DEFAULT_FAVORITES_LIST = List(
    id="list_favorites",
    name="我的收藏",
    desc="默认收藏清单",
    is_default=True,
    create_time=""
)
