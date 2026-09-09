from __future__ import annotations

from pathlib import Path
import sys


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from application.comic_app_service import ComicAppService
from domain.comic import Comic
from domain.recommendation import Recommendation
import protocol.platform_service as platform_service_module


class FakeEntityRepository:
    def __init__(self, entity):
        self.entity = entity
        self.saved = []

    def get_by_id(self, entity_id):
        if self.entity and self.entity.id == entity_id:
            return self.entity
        return None

    def save(self, entity):
        self.entity = entity
        self.saved.append(entity.to_dict())
        return True


class FakeTagRepository:
    pass


def test_repair_single_cover_updates_one_local_comic(monkeypatch):
    comic = Comic(
        id="JM100001",
        title="Local Comic",
        cover_path="/static/default/default_cover.jpg",
        total_units=3,
        current_unit=1,
    )
    service = ComicAppService(
        comic_repo=FakeEntityRepository(comic),
        tag_repo=FakeTagRepository(),
    )

    def fake_sync_cover(record, platform_service):
        record["cover_path"] = "/static/cover/JM/100001.jpg"
        return True, True

    monkeypatch.setattr(platform_service_module, "get_platform_service", lambda: object())
    monkeypatch.setattr(service, "_sync_cover_for_record", fake_sync_cover)

    result = service.repair_single_cover("JM100001", source="local")

    assert result.success is True
    assert result.data["source"] == "local"
    assert result.data["changed"] is True
    assert result.data["downloaded_cover"] is True
    assert result.data["cover_path"] == "/static/cover/JM/100001.jpg"
    assert service._comic_repo.entity.cover_path == "/static/cover/JM/100001.jpg"
    assert len(service._comic_repo.saved) == 1


def test_repair_single_cover_updates_one_recommendation_comic(monkeypatch):
    recommendation = Recommendation(
        id="JM200001",
        title="Preview Comic",
        cover_path="/static/default/default_cover.jpg",
        total_page=3,
        current_page=1,
    )
    service = ComicAppService(
        comic_repo=FakeEntityRepository(None),
        tag_repo=FakeTagRepository(),
    )
    service._recommendation_repo = FakeEntityRepository(recommendation)

    def fake_sync_cover(record, platform_service):
        record["cover_path"] = "/static/cover/JM/200001.jpg"
        return True, True

    monkeypatch.setattr(platform_service_module, "get_platform_service", lambda: object())
    monkeypatch.setattr(service, "_sync_cover_for_record", fake_sync_cover)

    result = service.repair_single_cover("JM200001", source="preview")

    assert result.success is True
    assert result.data["source"] == "preview"
    assert result.data["changed"] is True
    assert result.data["downloaded_cover"] is True
    assert result.data["cover_path"] == "/static/cover/JM/200001.jpg"
    assert service._recommendation_repo.entity.cover_path == "/static/cover/JM/200001.jpg"
    assert len(service._recommendation_repo.saved) == 1
