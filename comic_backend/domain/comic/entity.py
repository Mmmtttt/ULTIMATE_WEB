from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime

from domain.base.entity import BaseContent
from core.enums import ContentType


@dataclass
class Comic(BaseContent):
    content_type: ContentType = ContentType.COMIC
    import_source: str = ""
    storage_mode: str = ""
    soft_ref_locator: str = ""
    local_metadata_enriched: bool = False
    
    @property
    def author(self) -> str:
        return self.creator
    
    @author.setter
    def author(self, value: str):
        self.creator = value
    
    @property
    def total_page(self) -> int:
        return self.total_units
    
    @total_page.setter
    def total_page(self, value: int):
        self.total_units = value
    
    @property
    def current_page(self) -> int:
        return self.current_unit
    
    @current_page.setter
    def current_page(self, value: int):
        self.current_unit = value
    
    @property
    def last_read_time(self) -> str:
        return self.last_access_time
    
    @last_read_time.setter
    def last_read_time(self, value: str):
        self.last_access_time = value
    
    @classmethod
    def from_dict(cls, data: dict) -> "Comic":
        return cls(
            id=data.get("id", ""),
            title=data.get("title", ""),
            title_jp=data.get("title_jp", ""),
            creator=data.get("author", data.get("creator", "")),
            desc=data.get("desc", ""),
            cover_path=data.get("cover_path", ""),
            total_units=data.get("total_page", data.get("total_units", 0)),
            current_unit=data.get("current_page", data.get("current_unit", 1)),
            score=data.get("score") if data.get("score") is not None else 8.0,
            tag_ids=data.get("tag_ids") or [],
            list_ids=data.get("list_ids") or [],
            create_time=data.get("create_time", ""),
            last_access_time=data.get("last_read_time", data.get("last_access_time", "")),
            is_deleted=data.get("is_deleted", False),
            import_source=data.get("import_source", ""),
            storage_mode=data.get("storage_mode", ""),
            soft_ref_locator=data.get("soft_ref_locator", ""),
            local_metadata_enriched=bool(data.get("local_metadata_enriched", False)),
            content_type=ContentType.COMIC
        )
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "title_jp": self.title_jp,
            "author": self.creator,
            "desc": self.desc,
            "cover_path": self.cover_path,
            "total_page": self.total_units,
            "current_page": self.current_unit,
            "score": self.score,
            "tag_ids": self.tag_ids,
            "list_ids": self.list_ids,
            "create_time": self.create_time,
            "last_read_time": self.last_access_time,
            "is_deleted": self.is_deleted,
            "import_source": self.import_source,
            "storage_mode": self.storage_mode,
            "soft_ref_locator": self.soft_ref_locator,
            "local_metadata_enriched": bool(self.local_metadata_enriched),
        }
    
    def update_progress(self, page: int) -> bool:
        if 1 <= page <= self.total_units:
            self.current_unit = page
            self.last_access_time = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
            return True
        return False
