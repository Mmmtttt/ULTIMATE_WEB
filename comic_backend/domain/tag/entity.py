from dataclasses import dataclass
from typing import List
from datetime import datetime


@dataclass
class Tag:
    id: str
    name: str
    create_time: str = ""
    
    @classmethod
    def from_dict(cls, data: dict) -> "Tag":
        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            create_time=data.get("create_time", "")
        )
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "create_time": self.create_time
        }
    
    def update_name(self, name: str):
        self.name = name
