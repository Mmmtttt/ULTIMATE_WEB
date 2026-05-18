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
    local_cover_thumbnail_index: int = -1
    local_cover_asset_version: str = ""
    preview_video_local: str = ""
    local_video_path: str = ""
    local_source_path: str = ""
    local_asset_dir_name: str = ""
    local_source_filename: str = ""
    source_origin: str = ""
    source_updated_time: str = ""
    local_metadata_enriched: bool = False
    
    @property
    def actors(self) -> List[str]:
        return self._actors
    
    @actors.setter
    def actors(self, value: List[str]):
        self._actors = BaseContent._normalize_unique_values(value or [])
    
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
            tag_ids=BaseContent._normalize_unique_values(data.get("tag_ids") or []),
            list_ids=BaseContent._normalize_unique_values(data.get("list_ids") or []),
            create_time=data.get("create_time", ""),
            last_access_time=data.get("last_access_time", ""),
            is_deleted=data.get("is_deleted", False),
            platform=data.get("platform", ""),
            plugin_id=data.get("plugin_id", ""),
            plugin_name=data.get("plugin_name", ""),
            display=dict(data.get("display") or {}),
            storage_path_relative=data.get("storage_path_relative", ""),
            storage_path_kind=data.get("storage_path_kind", ""),
            content_type=ContentType.VIDEO,
            code=data.get("code", ""),
            date=data.get("date", ""),
            series=data.get("series", ""),
            magnets=data.get("magnets", []),
            thumbnail_images=data.get("thumbnail_images", []),
            preview_video=data.get("preview_video", ""),
            cover_path_local=data.get("cover_path_local", ""),
            thumbnail_images_local=data.get("thumbnail_images_local", []),
            local_cover_thumbnail_index=(
                int(data.get("local_cover_thumbnail_index"))
                if data.get("local_cover_thumbnail_index") is not None
                else -1
            ),
            local_cover_asset_version=data.get("local_cover_asset_version", ""),
            preview_video_local=data.get("preview_video_local", ""),
            local_video_path=data.get("local_video_path", ""),
            local_source_path=data.get("local_source_path", ""),
            local_asset_dir_name=data.get("local_asset_dir_name", ""),
            local_source_filename=data.get("local_source_filename", ""),
            source_origin=data.get("source_origin", ""),
            source_updated_time=data.get("source_updated_time", ""),
            local_metadata_enriched=bool(data.get("local_metadata_enriched", False)),
            _actors=BaseContent._normalize_unique_values(data.get("actors") or [])
        )
    
    def to_dict(self) -> dict:
        base_dict = super().to_dict()
        base_dict.update({
            "platform": self.platform,
            "plugin_id": self.plugin_id,
            "plugin_name": self.plugin_name,
            "display": dict(self.display or {}),
            "storage_path_relative": self.storage_path_relative,
            "storage_path_kind": self.storage_path_kind,
            "code": self.code,
            "date": self.date,
            "series": self.series,
            "magnets": self.magnets,
            "thumbnail_images": self.thumbnail_images,
            "preview_video": self.preview_video,
            "cover_path_local": self.cover_path_local,
            "thumbnail_images_local": self.thumbnail_images_local,
            "local_cover_thumbnail_index": (
                int(self.local_cover_thumbnail_index)
                if self.local_cover_thumbnail_index is not None
                else -1
            ),
            "local_cover_asset_version": self.local_cover_asset_version,
            "preview_video_local": self.preview_video_local,
            "local_video_path": self.local_video_path,
            "local_source_path": self.local_source_path,
            "local_asset_dir_name": self.local_asset_dir_name,
            "local_source_filename": self.local_source_filename,
            "source_origin": self.source_origin,
            "source_updated_time": self.source_updated_time,
            "local_metadata_enriched": bool(self.local_metadata_enriched),
            "actors": self._actors
        })
        return base_dict
    
