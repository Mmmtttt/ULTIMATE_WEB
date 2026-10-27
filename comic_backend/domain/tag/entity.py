from dataclasses import dataclass, field
from typing import List
from datetime import datetime
from core.enums import ContentType


@dataclass
class Tag:
    id: str
    name: str
    content_type: ContentType = ContentType.COMIC
    create_time: str = ""
    # 受控词表属性：kind 分类 + 同义词，供语义检索的标签路使用
    kind: str = "题材"
    aliases: List[str] = field(default_factory=list)

    @staticmethod
    def _normalize_aliases(values) -> List[str]:
        normalized: List[str] = []
        seen = set()
        for raw in values or []:
            value = str(raw or "").strip()
            if not value or value in seen:
                continue
            seen.add(value)
            normalized.append(value)
        return normalized

    @classmethod
    def from_dict(cls, data: dict) -> "Tag":
        content_type = data.get("content_type", ContentType.COMIC.value)
        if isinstance(content_type, ContentType):
            normalized_content_type = content_type
        elif isinstance(content_type, str):
            try:
                normalized_content_type = ContentType(content_type)
            except ValueError:
                normalized_content_type = ContentType.COMIC
        else:
            normalized_content_type = ContentType.COMIC
        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            content_type=normalized_content_type,
            create_time=data.get("create_time", ""),
            kind=str(data.get("kind") or "题材"),
            aliases=cls._normalize_aliases(data.get("aliases") or []),
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "content_type": self.content_type.value,
            "create_time": self.create_time,
            "kind": self.kind,
            "aliases": list(self.aliases or []),
        }

    def update_name(self, name: str):
        self.name = name
