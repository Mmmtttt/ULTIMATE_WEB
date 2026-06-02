from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from core.enums import ContentType
from core.utils import normalize_total_page
from domain.base.entity import BaseContent


def _normalize_int_list(values) -> List[int]:
    normalized: List[int] = []
    for item in values or []:
        try:
            normalized.append(int(item))
        except (TypeError, ValueError):
            continue
    return normalized


@dataclass(init=False)
class Recommendation(BaseContent):
    preview_image_urls: List[str] = field(default_factory=list)
    preview_pages: List[int] = field(default_factory=list)
    content_type: ContentType = ContentType.COMIC

    def __init__(
        self,
        id: str,
        title: str,
        cover_path: str = "",
        total_page: int = 0,
        current_page: int = 1,
        title_jp: str = "",
        author: str = "",
        desc: str = "",
        score: float = 8.0,
        tag_ids: List[str] = None,
        list_ids: List[str] = None,
        create_time: str = "",
        last_read_time: str = "",
        is_deleted: bool = False,
        preview_image_urls: List[str] = None,
        preview_pages: List[int] = None,
        platform: str = "",
        plugin_id: str = "",
        plugin_name: str = "",
        display: Dict[str, Any] = None,
        storage_path_relative: str = "",
        storage_path_kind: str = "",
        custom_order: Optional[int] = None,
        **kwargs,
    ):
        super().__init__(
            id=id,
            title=title,
            title_jp=title_jp,
            creator=author or str(kwargs.get("creator") or ""),
            desc=desc,
            cover_path=cover_path,
            total_units=normalize_total_page(total_page or kwargs.get("total_units", 0)),
            current_unit=max(1, int(current_page or kwargs.get("current_unit", 1) or 1)),
            score=score,
            tag_ids=BaseContent._normalize_unique_values(tag_ids or []),
            list_ids=BaseContent._normalize_unique_values(list_ids or []),
            create_time=create_time,
            last_access_time=last_read_time or str(kwargs.get("last_access_time") or ""),
            is_deleted=bool(is_deleted),
            platform=platform,
            plugin_id=plugin_id,
            plugin_name=plugin_name,
            display=dict(display or {}),
            storage_path_relative=storage_path_relative,
            storage_path_kind=storage_path_kind,
            custom_order=BaseContent._normalize_custom_order(custom_order),
            content_type=ContentType.COMIC,
        )
        self.preview_image_urls = [str(item or "") for item in (preview_image_urls or [])]
        self.preview_pages = _normalize_int_list(preview_pages or [])

    @property
    def author(self) -> str:
        return self.creator

    @author.setter
    def author(self, value: str):
        self.creator = str(value or "")

    @property
    def total_page(self) -> int:
        return self.total_units

    @total_page.setter
    def total_page(self, value: int):
        self.total_units = normalize_total_page(value)

    @property
    def current_page(self) -> int:
        return self.current_unit

    @current_page.setter
    def current_page(self, value: int):
        try:
            page = int(value)
        except (TypeError, ValueError):
            page = 1
        self.current_unit = max(1, page)

    @property
    def last_read_time(self) -> str:
        return self.last_access_time

    @last_read_time.setter
    def last_read_time(self, value: str):
        self.last_access_time = str(value or "")

    @classmethod
    def from_dict(cls, data: dict) -> "Recommendation":
        total_page = normalize_total_page(data.get("total_page", data.get("total_units", 0)))
        current_page = data.get("current_page", data.get("current_unit", 1))
        try:
            current_page = int(current_page)
        except (TypeError, ValueError):
            current_page = 1
        if total_page > 0:
            current_page = min(max(1, current_page), total_page)
        else:
            current_page = max(1, current_page)

        return cls(
            id=data.get("id", ""),
            title=data.get("title", ""),
            title_jp=data.get("title_jp", ""),
            author=data.get("author", data.get("creator", "")),
            desc=data.get("desc", ""),
            cover_path=data.get("cover_path", ""),
            total_page=total_page,
            current_page=current_page,
            score=data.get("score") if data.get("score") is not None else 8.0,
            tag_ids=data.get("tag_ids") or [],
            list_ids=data.get("list_ids") or [],
            create_time=data.get("create_time", ""),
            last_read_time=data.get("last_read_time", data.get("last_access_time", "")),
            is_deleted=bool(data.get("is_deleted", False)),
            preview_image_urls=[str(item or "") for item in (data.get("preview_image_urls") or [])],
            preview_pages=_normalize_int_list(data.get("preview_pages") or []),
            platform=data.get("platform", ""),
            plugin_id=data.get("plugin_id", ""),
            plugin_name=data.get("plugin_name", ""),
            display=dict(data.get("display") or {}),
            storage_path_relative=data.get("storage_path_relative", ""),
            storage_path_kind=data.get("storage_path_kind", ""),
            custom_order=BaseContent._normalize_custom_order(data.get("custom_order")),
            content_type=ContentType.COMIC,
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
            "score": self.score if self.score is not None else 8.0,
            "tag_ids": list(self.tag_ids),
            "list_ids": list(self.list_ids),
            "create_time": self.create_time,
            "last_read_time": self.last_access_time,
            "is_deleted": self.is_deleted,
            "preview_image_urls": list(self.preview_image_urls),
            "preview_pages": list(self.preview_pages),
            "platform": self.platform,
            "plugin_id": self.plugin_id,
            "plugin_name": self.plugin_name,
            "display": dict(self.display or {}),
            "storage_path_relative": self.storage_path_relative,
            "storage_path_kind": self.storage_path_kind,
            "custom_order": BaseContent._normalize_custom_order(self.custom_order),
        }
