from __future__ import annotations

from pathlib import Path
import sys


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import application.recommendation_app_service as recommendation_app_service
from application.recommendation_app_service import RecommendationAppService
from domain.recommendation import Recommendation


class FakeRecommendationRepository:
    def __init__(self, recommendation: Recommendation):
        self.recommendation = recommendation
        self.saved = []

    def get_by_id(self, recommendation_id):
        if self.recommendation.id == recommendation_id:
            return self.recommendation
        return None

    def save(self, recommendation):
        self.saved.append(recommendation.to_dict())
        self.recommendation = recommendation
        return True


class FakeTagRepository:
    def get_all(self, *args, **kwargs):
        return []


class FakeComicRepository:
    pass


class FakePlatformService:
    def __init__(self):
        self.downloads = []

    def get_album_by_id(self, platform, album_id):
        return {
            "albums": [
                {
                    "album_id": album_id,
                    "title": "Remote Title",
                    "title_jp": "Remote JP",
                    "author": "Remote Author",
                    "desc": "Remote Description",
                    "cover_url": "https://example.test/cover.jpg",
                    "pages": 12,
                }
            ]
        }

    def download_album(self, platform, album_id, download_dir, show_progress=False, **kwargs):
        self.downloads.append({
            "platform": platform,
            "album_id": album_id,
            "download_dir": download_dir,
            "show_progress": show_progress,
            "kwargs": kwargs,
        })
        return {"local_pages": 12, "pages_count": 12}, True


def _service(recommendation: Recommendation, platform_service: FakePlatformService):
    service = RecommendationAppService(
        recommendation_repo=FakeRecommendationRepository(recommendation),
        tag_repo=FakeTagRepository(),
        comic_repo=FakeComicRepository(),
    )
    service._platform_service = platform_service
    return service


def test_check_recommendation_update_compares_remote_pages_with_known_pages(monkeypatch):
    recommendation = Recommendation(id="JM123", title="Local", total_page=10)
    service = _service(recommendation, FakePlatformService())

    monkeypatch.setattr(
        recommendation_app_service,
        "split_prefixed_id",
        lambda content_id, media_type=None: ("JM", "123", None),
    )
    monkeypatch.setattr(
        recommendation_app_service.recommendation_cache_manager,
        "get_cached_pages",
        lambda _rid: list(range(1, 11)),
    )

    result = service.check_recommendation_update("JM123")

    assert result.success is True
    assert result.data["can_update"] is True
    assert result.data["has_update"] is True
    assert result.data["db_total_page"] == 10
    assert result.data["cached_page_count"] == 10
    assert result.data["remote_total_page"] == 12


def test_check_recommendation_update_treats_partial_cache_as_update(monkeypatch):
    recommendation = Recommendation(id="JM123", title="Local", total_page=12)
    service = _service(recommendation, FakePlatformService())

    monkeypatch.setattr(
        recommendation_app_service,
        "split_prefixed_id",
        lambda content_id, media_type=None: ("JM", "123", None),
    )
    monkeypatch.setattr(
        recommendation_app_service.recommendation_cache_manager,
        "get_cached_pages",
        lambda _rid: list(range(1, 7)),
    )

    result = service.check_recommendation_update("JM123")

    assert result.success is True
    assert result.data["can_update"] is True
    assert result.data["has_update"] is True
    assert result.data["update_reason"] == "missing_cached_pages"
    assert result.data["db_total_page"] == 12
    assert result.data["cached_page_count"] == 6
    assert result.data["remote_total_page"] == 12
    assert result.data["expected_cached_page_count"] == 12
    assert result.data["missing_cached_page_count"] == 6


def test_download_recommendation_update_refreshes_cache_and_metadata(monkeypatch):
    recommendation = Recommendation(id="JM123", title="Local", total_page=10, current_page=9)
    platform_service = FakePlatformService()
    service = _service(recommendation, platform_service)
    cached_pages = {"pages": list(range(1, 11))}
    added_to_cache = []

    monkeypatch.setattr(
        recommendation_app_service,
        "split_prefixed_id",
        lambda content_id, media_type=None: ("JM", "123", None),
    )

    def fake_get_cached_pages(_rid):
        return list(cached_pages["pages"])

    def fake_add_to_cache(rid, page_count):
        added_to_cache.append((rid, page_count))
        cached_pages["pages"] = list(range(1, page_count + 1))
        return True

    monkeypatch.setattr(
        recommendation_app_service.recommendation_cache_manager,
        "get_cached_pages",
        fake_get_cached_pages,
    )
    monkeypatch.setattr(
        recommendation_app_service.recommendation_cache_manager,
        "add_to_cache",
        fake_add_to_cache,
    )
    monkeypatch.setattr(service, "_refresh_recommendation_persisted_metadata", lambda _rec: False)

    result = service.download_recommendation_update("JM123")

    assert result.success is True
    assert result.data["had_update"] is True
    assert result.data["old_total_page"] == 10
    assert result.data["cached_page_count"] == 12
    assert added_to_cache == [("JM123", 12)]
    assert platform_service.downloads[0]["platform"] == "JM"
    assert platform_service.downloads[0]["album_id"] == "123"
    assert platform_service.downloads[0]["show_progress"] is False
    assert service._recommendation_repo.recommendation.title == "Remote Title"
    assert service._recommendation_repo.recommendation.author == "Remote Author"
    assert service._recommendation_repo.recommendation.total_page == 12
    assert service._recommendation_repo.saved


def test_download_recommendation_update_does_not_shrink_total_page_on_partial_cache(monkeypatch):
    recommendation = Recommendation(id="JM123", title="Local", total_page=12, current_page=9)
    platform_service = FakePlatformService()
    service = _service(recommendation, platform_service)
    cached_pages = {"pages": list(range(1, 7))}
    added_to_cache = []

    monkeypatch.setattr(
        recommendation_app_service,
        "split_prefixed_id",
        lambda content_id, media_type=None: ("JM", "123", None),
    )
    monkeypatch.setattr(
        recommendation_app_service.recommendation_cache_manager,
        "get_cached_pages",
        lambda _rid: list(cached_pages["pages"]),
    )
    monkeypatch.setattr(
        recommendation_app_service.recommendation_cache_manager,
        "add_to_cache",
        lambda rid, page_count: added_to_cache.append((rid, page_count)) or True,
    )

    result = service.download_recommendation_update("JM123")

    assert result.success is False
    assert "缓存仍不完整" in result.message
    assert service._recommendation_repo.recommendation.total_page == 12
    assert service._recommendation_repo.recommendation.current_page == 9
    assert service._recommendation_repo.saved == []
    assert added_to_cache == [("JM123", 12)]
