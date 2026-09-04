from __future__ import annotations

from pathlib import Path
import sys

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from application.comic_app_service import ComicAppService
from application.recommendation_app_service import RecommendationAppService
from application.video_app_service import VideoAppService
from core.enums import ContentType
from domain.comic import Comic
from domain.recommendation import Recommendation
from domain.tag import Tag
from domain.video import Video


class FakeTagRepository:
    def get_all(self, content_type=None):
        return [
            Tag(id="tag_fast", name="Fast", content_type=content_type or ContentType.COMIC),
            Tag(id="tag_slow", name="Slow", content_type=content_type or ContentType.COMIC),
        ]


class RaisingLegacyRepository:
    def search(self, keyword):
        raise AssertionError("legacy repository search should not run when catalog index is available")

    def filter_by_tags(self, include_tags, exclude_tags):
        raise AssertionError("legacy repository tag filter should not run when catalog index is available")

    def filter_multi(self, include_tags=None, exclude_tags=None, authors=None, list_ids=None):
        raise AssertionError("legacy repository multi filter should not run when catalog index is available")


class FakeCatalogQueryService:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def query_local_all(self, **kwargs):
        serializer = kwargs["serializer"]
        self.calls.append({key: value for key, value in kwargs.items() if key != "serializer"})
        return {
            "items": [serializer(dict(self.payload))],
            "total": 1,
            "performance": {"index": "sqlite"},
        }


def test_comic_legacy_search_uses_catalog_index_before_repository_scan():
    service = ComicAppService(comic_repo=RaisingLegacyRepository(), tag_repo=FakeTagRepository())
    index = FakeCatalogQueryService(
        {
            **Comic(id="COMIC001", title="Fast Comic", creator="Alice", tag_ids=["tag_fast"]).to_dict(),
            "cover_path": "/static/cover/fast.jpg",
        }
    )
    service._catalog_query_service = index

    result = service.search("fast")

    assert result.success is True
    assert result.data[0]["id"] == "COMIC001"
    assert result.data[0]["tags"] == [{"id": "tag_fast", "name": "Fast"}]
    assert index.calls[0]["media_type"] == "comic"
    assert index.calls[0]["keyword"] == "fast"


def test_recommendation_legacy_filter_uses_preview_catalog_index():
    service = RecommendationAppService(
        recommendation_repo=RaisingLegacyRepository(),
        tag_repo=FakeTagRepository(),
        comic_repo=RaisingLegacyRepository(),
    )
    index = FakeCatalogQueryService(
        {
            **Recommendation(id="REC001", title="Preview Comic", author="Bob", tag_ids=["tag_fast"]).to_dict(),
            "cover_path": "/static/cover/preview.jpg",
        }
    )
    service._catalog_query_service = index

    result = service.filter_multi(include_tags=["tag_fast"], exclude_tags=["tag_slow"], authors=["Bob"], list_ids=["list1"])

    assert result.success is True
    assert result.data[0]["id"] == "REC001"
    assert index.calls[0]["media_type"] == "comic"
    assert index.calls[0]["source"] == "preview"
    assert index.calls[0]["include_tags"] == ["tag_fast"]
    assert index.calls[0]["exclude_tags"] == ["tag_slow"]
    assert index.calls[0]["authors"] == ["Bob"]
    assert index.calls[0]["list_ids"] == ["list1"]


def test_video_legacy_filter_uses_catalog_index_before_repository_scan():
    service = VideoAppService(video_repo=RaisingLegacyRepository(), tag_repo=FakeTagRepository())
    index = FakeCatalogQueryService(
        {
            **Video(id="VID001", title="Fast Video", creator="Carol", tag_ids=["tag_fast"]).to_dict(),
            "cover_path": "/static/cover/video.jpg",
        }
    )
    service._catalog_query_service = index

    result = service.filter_by_tags(["tag_fast"], [])

    assert result.success is True
    assert result.data[0]["id"] == "VID001"
    assert result.data[0]["tags"] == [{"id": "tag_fast", "name": "Fast"}]
    assert index.calls[0]["media_type"] == "video"
    assert index.calls[0]["include_tags"] == ["tag_fast"]
