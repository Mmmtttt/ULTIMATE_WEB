import pytest

import sys
from pathlib import Path

from tests.shared.test_constants import REPO_ROOT

BACKEND_ROOT = Path(REPO_ROOT) / "comic_backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from application.comic_app_service import ComicAppService
from application.recommendation_app_service import RecommendationAppService
from application.video_app_service import VideoAppService
from domain.comic import Comic
from domain.recommendation import Recommendation
from domain.video import Video


def _raise_if_called(*_args, **_kwargs):
    raise AssertionError("list endpoint must not repair metadata or save records")


@pytest.mark.integration
def test_comic_list_does_not_repair_or_save_items(monkeypatch):
    service = ComicAppService()
    comic = Comic.from_dict({
        "id": "LOCAL_NO_META",
        "title": "No Metadata",
        "storage_path_relative": "",
        "storage_path_kind": "",
    })

    monkeypatch.setattr(service._comic_repo, "get_all", lambda: [comic])
    monkeypatch.setattr(service._tag_repo, "get_all", lambda: [])
    monkeypatch.setattr(service._comic_repo, "save", _raise_if_called)
    monkeypatch.setattr(service, "_refresh_comic_persisted_metadata", _raise_if_called)
    monkeypatch.setattr(service, "_ensure_cover", _raise_if_called)

    result = service.get_comic_list()

    assert result.success
    assert [item["id"] for item in result.data] == ["LOCAL_NO_META"]


@pytest.mark.integration
def test_recommendation_list_does_not_repair_or_save_items(monkeypatch):
    service = RecommendationAppService()
    recommendation = Recommendation(
        id="REC_NO_META",
        title="No Metadata",
        storage_path_relative="",
        storage_path_kind="",
    )

    monkeypatch.setattr(service._recommendation_repo, "get_all", lambda: [recommendation])
    monkeypatch.setattr(service._tag_repo, "get_all", lambda: [])
    monkeypatch.setattr(service._recommendation_repo, "save", _raise_if_called)
    monkeypatch.setattr(service, "_refresh_recommendation_persisted_metadata", _raise_if_called)

    result = service.get_recommendation_list()

    assert result.success
    assert [item["id"] for item in result.data] == ["REC_NO_META"]


@pytest.mark.integration
def test_video_list_does_not_repair_or_save_items(monkeypatch):
    service = VideoAppService()
    video = Video.from_dict({
        "id": "LOCALV_NO_META",
        "title": "No Metadata",
        "storage_path_relative": "",
        "storage_path_kind": "",
    })

    monkeypatch.setattr(service._video_repo, "get_all", lambda: [video])
    monkeypatch.setattr(service._tag_repo, "get_all", lambda: [])
    monkeypatch.setattr(service._video_repo, "save", _raise_if_called)
    monkeypatch.setattr(service, "_refresh_video_persisted_metadata", _raise_if_called)

    result = service.get_video_list()

    assert result.success
    assert [item["id"] for item in result.data] == ["LOCALV_NO_META"]
