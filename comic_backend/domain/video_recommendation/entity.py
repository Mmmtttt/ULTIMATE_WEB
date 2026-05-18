from dataclasses import dataclass, field
from typing import Any, Dict, List

from core.enums import ContentType
from domain.base.entity import BaseContent


@dataclass
class VideoRecommendation(BaseContent):
    code: str = ""
    date: str = ""
    series: str = ""
    magnets: List[dict] = field(default_factory=list)
    thumbnail_images: List[str] = field(default_factory=list)
    preview_video: str = ""
    cover_path_local: str = ""
    thumbnail_images_local: List[str] = field(default_factory=list)
    preview_video_local: str = ""
    content_type: ContentType = ContentType.VIDEO
    _actors: List[str] = field(default_factory=list, repr=False)

    @property
    def actors(self) -> List[str]:
        return self._actors

    @actors.setter
    def actors(self, value: List[str]):
        self._actors = BaseContent._normalize_unique_values(value or [])

    @classmethod
    def from_dict(cls, data: dict) -> "VideoRecommendation":
        return cls(
            id=data.get("id", ""),
            title=data.get("title", ""),
            title_jp=data.get("title_jp", ""),
            creator=data.get("creator", data.get("actors", [""])[0] if data.get("actors") else ""),
            desc=data.get("desc", ""),
            cover_path=data.get("cover_path", ""),
            total_units=int(data.get("total_units", 0) or 0),
            current_unit=int(data.get("current_unit", 1) or 1),
            score=data.get("score") if data.get("score") is not None else 8.0,
            tag_ids=BaseContent._normalize_unique_values(data.get("tag_ids") or []),
            list_ids=BaseContent._normalize_unique_values(data.get("list_ids") or []),
            create_time=data.get("create_time", ""),
            last_access_time=data.get("last_access_time", ""),
            is_deleted=bool(data.get("is_deleted", False)),
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
            magnets=list(data.get("magnets") or []),
            thumbnail_images=[str(item or "") for item in (data.get("thumbnail_images") or [])],
            preview_video=data.get("preview_video", ""),
            cover_path_local=data.get("cover_path_local", ""),
            thumbnail_images_local=[str(item or "") for item in (data.get("thumbnail_images_local") or [])],
            preview_video_local=data.get("preview_video_local", ""),
            _actors=BaseContent._normalize_unique_values(data.get("actors") or []),
        )

    def to_dict(self) -> dict:
        payload = super().to_dict()
        payload.update(
            {
                "code": self.code,
                "date": self.date,
                "series": self.series,
                "magnets": list(self.magnets),
                "thumbnail_images": list(self.thumbnail_images),
                "preview_video": self.preview_video,
                "cover_path_local": self.cover_path_local,
                "thumbnail_images_local": list(self.thumbnail_images_local),
                "preview_video_local": self.preview_video_local,
                "actors": list(self._actors),
            }
        )
        return payload
