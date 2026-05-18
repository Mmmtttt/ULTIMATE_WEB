from abc import ABC
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict, Any

from core.enums import ContentType
from core.utils import validate_score


@dataclass
class BaseEntity(ABC):
    id: str
    
    def to_dict(self) -> dict:
        raise NotImplementedError
    
    @classmethod
    def from_dict(cls, data: dict):
        raise NotImplementedError


@dataclass
class BaseContent(BaseEntity):
    title: str = ""
    title_jp: str = ""
    creator: str = ""
    desc: str = ""
    cover_path: str = ""
    total_units: int = 0
    current_unit: int = 1
    score: Optional[float] = None
    tag_ids: List[str] = field(default_factory=list)
    list_ids: List[str] = field(default_factory=list)
    create_time: str = ""
    last_access_time: str = ""
    is_deleted: bool = False
    platform: str = ""
    plugin_id: str = ""
    plugin_name: str = ""
    display: Dict[str, Any] = field(default_factory=dict)
    storage_path_relative: str = ""
    storage_path_kind: str = ""
    content_type: ContentType = ContentType.COMIC

    @staticmethod
    def _normalize_unique_values(values: List[str]) -> List[str]:
        normalized: List[str] = []
        seen = set()
        for raw_value in values or []:
            value = str(raw_value or "").strip()
            if not value or value in seen:
                continue
            seen.add(value)
            normalized.append(value)
        return normalized
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "title_jp": self.title_jp,
            "creator": self.creator,
            "desc": self.desc,
            "cover_path": self.cover_path,
            "total_units": self.total_units,
            "current_unit": self.current_unit,
            "score": self.score,
            "tag_ids": self.tag_ids,
            "list_ids": self.list_ids,
            "create_time": self.create_time,
            "last_access_time": self.last_access_time,
            "is_deleted": self.is_deleted,
            "platform": self.platform,
            "plugin_id": self.plugin_id,
            "plugin_name": self.plugin_name,
            "display": dict(self.display or {}),
            "storage_path_relative": self.storage_path_relative,
            "storage_path_kind": self.storage_path_kind,
            "content_type": self.content_type.value
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "BaseContent":
        content_type_str = data.get("content_type", "comic")
        content_type = ContentType.COMIC if content_type_str == "comic" else ContentType.VIDEO
        
        return cls(
            id=data.get("id", ""),
            title=data.get("title", ""),
            title_jp=data.get("title_jp", ""),
            creator=data.get("creator", data.get("author", "")),
            desc=data.get("desc", ""),
            cover_path=data.get("cover_path", ""),
            total_units=data.get("total_units", data.get("total_page", 0)),
            current_unit=data.get("current_unit", data.get("current_page", 1)),
            score=data.get("score"),
            tag_ids=cls._normalize_unique_values(data.get("tag_ids") or []),
            list_ids=cls._normalize_unique_values(data.get("list_ids") or []),
            create_time=data.get("create_time", ""),
            last_access_time=data.get("last_access_time", data.get("last_read_time", "")),
            is_deleted=data.get("is_deleted", False),
            platform=data.get("platform", ""),
            plugin_id=data.get("plugin_id", ""),
            plugin_name=data.get("plugin_name", ""),
            display=dict(data.get("display") or {}),
            storage_path_relative=data.get("storage_path_relative", ""),
            storage_path_kind=data.get("storage_path_kind", ""),
            content_type=content_type
        )
    
    def update_progress(self, unit: int) -> bool:
        if 1 <= unit <= self.total_units:
            self.current_unit = unit
            self.last_access_time = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
            return True
        return False
    
    def update_score(self, score: float) -> bool:
        valid, _ = validate_score(score)
        if valid:
            self.score = score
            return True
        return False
    
    def bind_tags(self, tag_ids: List[str]):
        self.tag_ids = self._normalize_unique_values(tag_ids)

    def add_tags(self, tag_ids: List[str]):
        self.tag_ids = self._normalize_unique_values(list(self.tag_ids) + list(tag_ids or []))

    def remove_tags(self, tag_ids: List[str]):
        removing = {str(item or "").strip() for item in (tag_ids or []) if str(item or "").strip()}
        self.tag_ids = [tag_id for tag_id in self.tag_ids if tag_id not in removing]

    def update_meta(self, meta: dict):
        if not isinstance(meta, dict):
            return
        title = str(meta.get("title") or "").strip()
        creator = str(meta.get("creator") or meta.get("author") or "").strip()
        if title:
            self.title = title
        if creator:
            self.creator = creator
        if "desc" in meta:
            self.desc = str(meta.get("desc") or "")
        cover_path = str(meta.get("cover_path") or "").strip()
        if cover_path:
            self.cover_path = cover_path
    
    def add_to_list(self, list_id: str):
        if list_id not in self.list_ids:
            self.list_ids.append(list_id)
    
    def remove_from_list(self, list_id: str):
        if list_id in self.list_ids:
            self.list_ids = [lid for lid in self.list_ids if lid != list_id]
    
    def move_to_trash(self):
        self.is_deleted = True
    
    def restore_from_trash(self):
        self.is_deleted = False


@dataclass
class BaseCreator(BaseEntity):
    name: str = ""
    avatar_url: str = ""
    works_count: int = 0
    is_subscribed: bool = False
    subscribe_time: Optional[str] = None
    last_check_time: str = ""
    last_work_id: str = ""
    last_work_title: str = ""
    new_work_count: int = 0
    content_type: ContentType = ContentType.COMIC
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "avatar_url": self.avatar_url,
            "works_count": self.works_count,
            "is_subscribed": self.is_subscribed,
            "subscribe_time": self.subscribe_time,
            "last_check_time": self.last_check_time,
            "last_work_id": self.last_work_id,
            "last_work_title": self.last_work_title,
            "new_work_count": self.new_work_count,
            "content_type": self.content_type.value
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "BaseCreator":
        content_type_str = data.get("content_type", "comic")
        content_type = ContentType.COMIC if content_type_str == "comic" else ContentType.VIDEO
        
        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            avatar_url=data.get("avatar_url", ""),
            works_count=data.get("works_count", 0),
            is_subscribed=data.get("is_subscribed", False),
            subscribe_time=data.get("subscribe_time"),
            last_check_time=data.get("last_check_time", ""),
            last_work_id=data.get("last_work_id", ""),
            last_work_title=data.get("last_work_title", ""),
            new_work_count=data.get("new_work_count", 0),
            content_type=content_type
        )
    
    def update_check_info(self, last_work_id: str, last_work_title: str, new_count: int = 0):
        from core.utils import get_current_time
        self.last_check_time = get_current_time()
        self.last_work_id = last_work_id
        self.last_work_title = last_work_title
        self.new_work_count = new_count
    
    def clear_new_count(self):
        self.new_work_count = 0
    
    def subscribe(self):
        from core.utils import get_current_time
        self.is_subscribed = True
        self.subscribe_time = get_current_time()
    
    def unsubscribe(self):
        self.is_subscribed = False
