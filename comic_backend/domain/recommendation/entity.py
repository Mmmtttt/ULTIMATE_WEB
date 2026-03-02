from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Recommendation:
    """推荐漫画实体类 - 结构与 Comic 相同，但图片存储在图床"""
    id: str
    title: str
    cover_path: str           # 图床 URL，而非本地路径
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
    is_deleted: bool = False
    
    @classmethod
    def from_dict(cls, data: dict) -> "Recommendation":
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
            last_read_time=data.get("last_read_time", ""),
            is_deleted=data.get("is_deleted", False)
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
            "last_read_time": self.last_read_time,
            "is_deleted": self.is_deleted
        }
    
    def update_progress(self, page: int):
        """更新阅读进度"""
        if 1 <= page <= self.total_page:
            self.current_page = page
    
    def update_score(self, score: float):
        """更新评分"""
        self.score = score
    
    def bind_tags(self, tag_ids: List[str]):
        """绑定标签"""
        self.tag_ids = tag_ids
    
    def add_tags(self, tag_ids: List[str]):
        """添加标签"""
        for tag_id in tag_ids:
            if tag_id not in self.tag_ids:
                self.tag_ids.append(tag_id)
    
    def remove_tags(self, tag_ids: List[str]):
        """移除标签"""
        for tag_id in tag_ids:
            if tag_id in self.tag_ids:
                self.tag_ids.remove(tag_id)
    
    def add_to_list(self, list_id: str):
        """添加到清单"""
        if list_id not in self.list_ids:
            self.list_ids.append(list_id)
    
    def remove_from_list(self, list_id: str):
        """从清单移除"""
        if list_id in self.list_ids:
            self.list_ids.remove(list_id)
    
    def move_to_trash(self):
        self.is_deleted = True
    
    def restore_from_trash(self):
        self.is_deleted = False
