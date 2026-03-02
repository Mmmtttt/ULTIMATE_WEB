from dataclasses import dataclass
from typing import List, Optional


@dataclass
class AuthorSubscription:
    id: str
    name: str
    create_time: str = ""
    last_check_time: str = ""
    last_work_id: str = ""
    last_work_title: str = ""
    new_work_count: int = 0
    
    @classmethod
    def from_dict(cls, data: dict) -> "AuthorSubscription":
        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            create_time=data.get("create_time", ""),
            last_check_time=data.get("last_check_time", ""),
            last_work_id=data.get("last_work_id", ""),
            last_work_title=data.get("last_work_title", ""),
            new_work_count=data.get("new_work_count", 0)
        )
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "create_time": self.create_time,
            "last_check_time": self.last_check_time,
            "last_work_id": self.last_work_id,
            "last_work_title": self.last_work_title,
            "new_work_count": self.new_work_count
        }
    
    def update_check_info(self, last_work_id: str, last_work_title: str, new_count: int = 0):
        from core.utils import get_current_time
        self.last_check_time = get_current_time()
        self.last_work_id = last_work_id
        self.last_work_title = last_work_title
        self.new_work_count = new_count
    
    def clear_new_count(self):
        self.new_work_count = 0
