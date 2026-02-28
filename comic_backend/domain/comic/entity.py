from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime


@dataclass
class Comic:
    id: str
    title: str
    cover_path: str
    total_page: int
    current_page: int = 1
    title_jp: str = ""
    author: str = ""
    desc: str = ""
    score: Optional[float] = 8.0
    tag_ids: List[str] = field(default_factory=list)
    list_ids: List[str] = field(default_factory=list)
    create_time: str = ""
    last_read_time: str = ""
    
    @classmethod
    def from_dict(cls, data: dict) -> "Comic":
        return cls(
            id=data.get("id", ""),
            title=data.get("title", ""),
            title_jp=data.get("title_jp", ""),
            author=data.get("author", ""),
            desc=data.get("desc", ""),
            cover_path=data.get("cover_path", ""),
            total_page=data.get("total_page", 0),
            current_page=data.get("current_page", 1),
            score=data.get("score") if data.get("score") is not None else 8.0,
            tag_ids=data.get("tag_ids") or [],
            list_ids=data.get("list_ids") or [],
            create_time=data.get("create_time", ""),
            last_read_time=data.get("last_read_time", "")
        )
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "title_jp": self.title_jp,
            "author": self.author,
            "desc": self.desc,
            "cover_path": self.cover_path,
            "total_page": self.total_page,
            "current_page": self.current_page,
            "score": self.score,
            "tag_ids": self.tag_ids,
            "list_ids": self.list_ids,
            "create_time": self.create_time,
            "last_read_time": self.last_read_time
        }
    
    def update_progress(self, page: int) -> bool:
        if 1 <= page <= self.total_page:
            self.current_page = page
            self.last_read_time = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
            return True
        return False
    
    def update_score(self, score: float) -> bool:
        from core.utils import validate_score
        valid, _ = validate_score(score)
        if valid:
            self.score = score
            return True
        return False
    
    def bind_tags(self, tag_ids: List[str]):
        self.tag_ids = tag_ids
    
    def add_tags(self, tag_ids: List[str]):
        current = set(self.tag_ids)
        current.update(tag_ids)
        self.tag_ids = list(current)
    
    def remove_tags(self, tag_ids: List[str]):
        current = set(self.tag_ids)
        current.difference_update(tag_ids)
        self.tag_ids = list(current)
    
    def update_meta(self, meta: dict):
        if 'title' in meta and meta['title']:
            self.title = meta['title']
        if 'author' in meta:
            self.author = meta['author']
        if 'desc' in meta:
            self.desc = meta['desc']
        if 'cover_path' in meta and meta['cover_path']:
            self.cover_path = meta['cover_path']
    
    def add_to_list(self, list_id: str):
        if list_id not in self.list_ids:
            self.list_ids.append(list_id)
    
    def remove_from_list(self, list_id: str):
        if list_id in self.list_ids:
            self.list_ids = [lid for lid in self.list_ids if lid != list_id]
