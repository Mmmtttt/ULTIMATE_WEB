from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from application.tag_app_service import TagAppService
from core.enums import ContentType
from domain.tag import Tag
from infrastructure.persistence.catalog_index import CatalogIndex


class FakeTagRepository:
    def get_all(self, content_type=None):
        return [
            Tag(id="tag_action", name="Action", content_type=content_type or ContentType.COMIC),
            Tag(id="tag_empty", name="Empty", content_type=content_type or ContentType.COMIC),
        ]


class RaisingContentRepository:
    def get_all(self):
        raise AssertionError("content repository should not be scanned when tag counts use index")


@dataclass
class FakeContent:
    id: str
    tag_ids: list[str]
    is_deleted: bool = False


class FakeFallbackRepository:
    def __init__(self, items):
        self._items = list(items)

    def get_all(self):
        return list(self._items)


def test_tag_list_uses_catalog_index_counts_without_scanning_content_repositories(monkeypatch):
    monkeypatch.setattr(
        CatalogIndex,
        "count_tags",
        lambda self, content_type: {"tag_action": 2},
    )

    service = TagAppService(
        tag_repo=FakeTagRepository(),
        comic_repo=RaisingContentRepository(),
        recommendation_repo=RaisingContentRepository(),
    )

    result = service.get_tag_list(ContentType.COMIC)

    assert result.success is True
    counts = {item["id"]: item["comic_count"] for item in result.data}
    assert counts == {"tag_action": 2, "tag_empty": 0}


def test_tag_list_falls_back_to_json_counts_when_catalog_index_unavailable(monkeypatch):
    monkeypatch.setattr(CatalogIndex, "count_tags", lambda self, content_type: None)

    service = TagAppService(
        tag_repo=FakeTagRepository(),
        comic_repo=FakeFallbackRepository(
            [
                FakeContent(id="COMIC001", tag_ids=["tag_action"]),
                FakeContent(id="COMIC002", tag_ids=["tag_action"], is_deleted=True),
            ]
        ),
        recommendation_repo=FakeFallbackRepository(
            [
                FakeContent(id="REC001", tag_ids=["tag_action"]),
            ]
        ),
    )

    result = service.get_tag_list(ContentType.COMIC)

    assert result.success is True
    counts = {item["id"]: item["comic_count"] for item in result.data}
    assert counts == {"tag_action": 2, "tag_empty": 0}
