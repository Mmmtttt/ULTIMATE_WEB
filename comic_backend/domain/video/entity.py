"""
视频实体
"""

from dataclasses import dataclass, field
from typing import List, Optional
from domain.base.entity import BaseContent
from core.enums import ContentType


@dataclass
class Video(BaseContent):
    content_type: ContentType = ContentType.VIDEO
    
    code: str = ""
    date: str = ""
    series: str = ""
    magnets: List[dict] = field(default_factory=list)
    thumbnail_images: List[str] = field(default_factory=list)
    preview_video: str = ""
    cover_path_local: str = ""
    thumbnail_images_local: List[str] = field(default_factory=list)
    preview_video_local: str = ""
    local_video_path: str = ""
    local_source_path: str = ""
    local_metadata_enriched: bool = False
    
    @property
    def actors(self) -> List[str]:
        return self._actors
    
    @actors.setter
    def actors(self, value: List[str]):
        self._actors = value or []
    
    _actors: List[str] = field(default_factory=list, repr=False)
    
    @classmethod
    def from_dict(cls, data: dict) -> "Video":
        return cls(
            id=data.get("id", ""),
            title=data.get("title", ""),
            title_jp=data.get("title_jp", ""),
            creator=data.get("creator", data.get("actors", [""])[0] if data.get("actors") else ""),
            desc=data.get("desc", ""),
            cover_path=data.get("cover_path", ""),
            total_units=data.get("total_units", 0),
            current_unit=data.get("current_unit", 1),
            score=data.get("score"),
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
            cover_path_local=data.get("cover_path_local", ""),
            thumbnail_images_local=data.get("thumbnail_images_local", []),
            preview_video_local=data.get("preview_video_local", ""),
            local_video_path=data.get("local_video_path", ""),
            local_source_path=data.get("local_source_path", ""),
            local_metadata_enriched=bool(data.get("local_metadata_enriched", False)),
            _actors=data.get("actors", [])
        )
    
    def to_dict(self) -> dict:
        base_dict = super().to_dict()
        base_dict.update({
            "code": self.code,
            "date": self.date,
            "series": self.series,
            "magnets": self.magnets,
            "thumbnail_images": self.thumbnail_images,
            "preview_video": self.preview_video,
            "cover_path_local": self.cover_path_local,
            "thumbnail_images_local": self.thumbnail_images_local,
            "preview_video_local": self.preview_video_local,
            "local_video_path": self.local_video_path,
            "local_source_path": self.local_source_path,
            "local_metadata_enriched": bool(self.local_metadata_enriched),
            "actors": self._actors
        })
        return base_dict
    
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
