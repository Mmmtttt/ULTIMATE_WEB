"""
视频推荐实体
"""

from dataclasses import dataclass, field
from typing import List, Optional
from core.enums import ContentType


@dataclass
class VideoRecommendation:
    """推荐视频实体类 - 结构与 Video 相似，但图片存储在图床"""
    id: str
    title: str
    title_jp: str = ""
    creator: str = ""
    desc: str = ""
    cover_path: str = ""           # 图床 URL，而非本地路径
    total_units: int = 0
    current_unit: int = 1
    score: Optional[float] = 8.0
    tag_ids: List[str] = field(default_factory=list)
    list_ids: List[str] = field(default_factory=list)
    create_time: str = ""
    last_access_time: str = ""
    is_deleted: bool = False
    
    content_type: ContentType = ContentType.VIDEO
    code: str = ""
    date: str = ""
    series: str = ""
    magnets: List[dict] = field(default_factory=list)
    thumbnail_images: List[str] = field(default_factory=list)
    preview_video: str = ""
    
    _actors: List[str] = field(default_factory=list, repr=False)
    
    @property
    def actors(self) -> List[str]:
        return self._actors
    
    @actors.setter
    def actors(self, value: List[str]):
        self._actors = value or []
    
    @classmethod
    def from_dict(cls, data: dict) -> "VideoRecommendation":
        return cls(
            id=data.get("id", ""),
            title=data.get("title", ""),
            title_jp=data.get("title_jp", ""),
            creator=data.get("creator", data.get("actors", [""])[0] if data.get("actors") else ""),
            desc=data.get("desc", ""),
            cover_path=data.get("cover_path", ""),
            total_units=data.get("total_units", 0),
            current_unit=data.get("current_unit", 1),
            score=data.get("score") if data.get("score") is not None else 8.0,
            tag_ids=data.get("tag_ids", []),
            list_ids=data.get("list_ids", []),
            create_time=data.get("create_time", ""),
            last_access_time=data.get("last_access_time", ""),
            is_deleted=data.get("is_deleted", False),
            content_type=ContentType.VIDEO,
            code=data.get("code", ""),
            date=data.get("date", ""),
            series=data.get("series", ""),
            magnets=data.get("magnets", []),
            thumbnail_images=data.get("thumbnail_images", []),
            preview_video=data.get("preview_video", ""),
            _actors=data.get("actors", [])
        )
    
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
            "content_type": self.content_type.value if hasattr(self.content_type, 'value') else self.content_type,
            "code": self.code,
            "date": self.date,
            "series": self.series,
            "magnets": self.magnets,
            "thumbnail_images": self.thumbnail_images,
            "preview_video": self.preview_video,
            "actors": self._actors
        }
    
    def update_progress(self, unit: int):
        """更新观看进度"""
        if 1 <= unit <= self.total_units:
            self.current_unit = unit
    
    def update_score(self, score: float):
        """更新评分"""
        self.score = score
    
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
