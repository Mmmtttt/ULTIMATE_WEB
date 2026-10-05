from __future__ import annotations

from pathlib import Path
import sys

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from application.list_app_service import ListAppService
from core.enums import ContentType
from domain.list import List
from infrastructure.persistence.catalog_index import CatalogIndex


class _FakeListRepository:
    def __init__(self) -> None:
        self.comic_count_calls = 0
        self.video_count_calls = 0
        self.lists = [
            List(id="list_a", name="A", content_type=ContentType.COMIC),
            List(id="list_b", name="B", content_type=ContentType.VIDEO),
        ]

    def ensure_default_list(self) -> bool:
        return True

    def get_all(self, content_type=None):
        if content_type is None:
            return list(self.lists)
        return [item for item in self.lists if item.content_type == content_type]

    def get_by_id(self, list_id: str):
        return next((item for item in self.lists if item.id == list_id), None)

    def save(self, list_obj):
        return True

    def get_comic_count(self, list_id: str) -> int:
        self.comic_count_calls += 1
        return 99

    def get_video_count(self, list_id: str) -> int:
        self.video_count_calls += 1
        return 88


def test_list_all_uses_catalog_index_counts(monkeypatch):
    repo = _FakeListRepository()
    monkeypatch.setattr(
        CatalogIndex,
        "count_list_members",
        lambda self, list_ids: {
            "list_a": {"comic_count": 2, "video_count": 0},
            "list_b": {"comic_count": 0, "video_count": 3},
        },
    )

    result = ListAppService(list_repo=repo).get_list_all()

    assert result.success is True
    counts = {item["id"]: (item["comic_count"], item["video_count"]) for item in result.data}
    assert counts == {"list_a": (2, 0), "list_b": (0, 3)}
    assert repo.comic_count_calls == 0
    assert repo.video_count_calls == 0


def test_list_all_falls_back_to_json_counts_when_index_unavailable(monkeypatch):
    repo = _FakeListRepository()
    monkeypatch.setattr(CatalogIndex, "count_list_members", lambda self, list_ids: None)

    result = ListAppService(list_repo=repo).get_list_all()

    assert result.success is True
    counts = {item["id"]: (item["comic_count"], item["video_count"]) for item in result.data}
    assert counts == {"list_a": (99, 88), "list_b": (99, 88)}
    assert repo.comic_count_calls == 2
    assert repo.video_count_calls == 2


class _ExplodingContentRepository:
    def get_all(self):
        raise AssertionError("content repository should not be scanned when catalog index is available")


def test_list_detail_uses_catalog_index_members(monkeypatch):
    repo = _FakeListRepository()
    monkeypatch.setattr(
        CatalogIndex,
        "load_list_members",
        lambda self, list_id: [
            {
                "media_type": "comic",
                "source": "local",
                "payload": {
                    "id": "COMIC001",
                    "title": "Comic 1",
                    "cover_path": "/static/cover/comic.jpg",
                    "total_page": 10,
                    "current_page": 2,
                    "score": 8,
                    "tag_ids": ["tag_001"],
                    "last_read_time": "2026-09-04T10:00:00",
                    "create_time": "2026-09-04T09:00:00",
                },
            },
            {
                "media_type": "video",
                "source": "preview",
                "payload": {
                    "id": "VIDEO001",
                    "title": "Video 1",
                    "cover_path": "/static/cover/video.jpg",
                    "score": 9,
                    "tag_ids": ["tag_002"],
                    "last_access_time": "2026-09-04T11:00:00",
                    "create_time": "2026-09-04T08:00:00",
                    "code": "ABC-123",
                    "actors": ["Actor A"],
                },
            },
        ],
    )

    result = ListAppService(
        list_repo=repo,
        comic_repo=_ExplodingContentRepository(),
        rec_repo=_ExplodingContentRepository(),
        video_repo=_ExplodingContentRepository(),
        video_rec_repo=_ExplodingContentRepository(),
    ).get_list_detail("list_a")

    assert result.success is True
    assert result.data["comic_count"] == 1
    assert result.data["video_count"] == 1
    assert result.data["comics"][0]["id"] == "COMIC001"
    assert result.data["comics"][0]["source"] == "local"
    assert result.data["videos"][0]["id"] == "VIDEO001"
    assert result.data["videos"][0]["source"] == "preview"
