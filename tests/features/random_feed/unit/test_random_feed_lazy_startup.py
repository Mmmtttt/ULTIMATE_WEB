from __future__ import annotations

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
