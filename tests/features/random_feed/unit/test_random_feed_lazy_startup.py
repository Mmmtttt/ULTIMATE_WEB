from __future__ import annotations

import random
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[4] / "comic_backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def test_random_feed_service_does_not_build_candidates_on_startup(monkeypatch):
    from application.random_feed_service import RandomFeedService

    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("random feed candidates should be built lazily")

    monkeypatch.setattr(RandomFeedService, "_build_candidates", fail_if_called)

    service = RandomFeedService()

    assert service.list_strategies()
    assert service.get_startup_session_id("comic") is None
    assert service.get_startup_session_id("video") is None


def test_local_comic_random_feed_samples_page_without_prebuilt_page_list():
    from application.random_feed_service import FeedWorkCandidate, RandomFeedService

    service = RandomFeedService()
    candidate = FeedWorkCandidate(
        mode="comic",
        source="local",
        content_id="COMIC_LAZY_PAGE",
        title="Lazy Page Comic",
        author="Tester",
        score=8.0,
        total_units=12,
        current_unit=1,
        page_numbers=[],
    )

    pages = {
        service._materialize_item(candidate, random.Random(seed))["page_num"]
        for seed in range(30)
    }

    assert pages
    assert all(1 <= page <= 12 for page in pages)


def test_random_feed_local_comics_prefer_catalog_index(monkeypatch):
    from application.random_feed_service import RandomFeedService
    from infrastructure.persistence.catalog_index import CatalogIndex

    monkeypatch.setattr(
        CatalogIndex,
        "load_feed_candidates",
        lambda _self, *, media_type, source="local": [
            {
                "id": "COMIC_FROM_INDEX",
                "title": "Indexed Comic",
                "creator": "Index Author",
                "score": 9.5,
                "tag_ids": ["tag_index"],
                "total_units": 20,
                "current_unit": 3,
            }
        ],
    )

    service = RandomFeedService()
    service._comic_repo.get_all = lambda: (_ for _ in ()).throw(AssertionError("JSON fallback should not run"))
    service._recommendation_repo.get_all = lambda: []

    candidates = service._build_comic_candidates()

    assert len(candidates) == 1
    assert candidates[0].content_id == "COMIC_FROM_INDEX"
    assert candidates[0].author == "Index Author"
    assert candidates[0].tag_ids == ["tag_index"]
