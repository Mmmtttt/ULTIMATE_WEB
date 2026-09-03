from __future__ import annotations

from pathlib import Path
import sys

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from domain.comic import Comic
from domain.recommendation import Recommendation
from application.comic_app_service import ComicAppService
from infrastructure.persistence.json_storage import JsonStorage
import infrastructure.persistence.catalog_index.writer as catalog_index_writer
import infrastructure.persistence.json_storage as json_storage_module
from infrastructure.persistence.repositories.comic_repository_impl import ComicJsonRepository
from infrastructure.persistence.repositories.list_repository_impl import ListJsonRepository
from infrastructure.persistence.repositories.recommendation_repository_impl import RecommendationJsonRepository


def _reset_json_storage(tmp_path, monkeypatch):
    JsonStorage._instances.clear()
    JsonStorage._locks.clear()
    monkeypatch.setattr(json_storage_module, "get_meta_dir", lambda: str(tmp_path))


def test_batch_update_many_by_ids_syncs_index_once(tmp_path, monkeypatch):
    _reset_json_storage(tmp_path, monkeypatch)
    calls = []
    monkeypatch.setattr(
        catalog_index_writer,
        "sync_after_json_write",
        lambda file_name, old_data, new_data, **kwargs: calls.append(file_name),
    )
    storage = JsonStorage("comics_database.json")
    assert storage.write(
        {
            "comics": [
                Comic(id="COMIC001", title="Comic 1").to_dict(),
                Comic(id="COMIC002", title="Comic 2").to_dict(),
                Comic(id="COMIC003", title="Comic 3").to_dict(),
            ],
            "total_comics": 3,
        }
    )
    calls.clear()

    repo = ComicJsonRepository(storage=storage)
    updated_count = repo.update_many_by_ids(
        ["COMIC001", "COMIC002"],
        lambda comic: comic.move_to_trash(),
    )

    data = storage.read()
    deleted_flags = {item["id"]: bool(item.get("is_deleted")) for item in data["comics"]}
    assert updated_count == 2
    assert deleted_flags == {"COMIC001": True, "COMIC002": True, "COMIC003": False}
    assert calls == ["comics_database.json"]


def test_batch_delete_many_by_ids_syncs_index_once(tmp_path, monkeypatch):
    _reset_json_storage(tmp_path, monkeypatch)
    calls = []
    monkeypatch.setattr(
        catalog_index_writer,
        "sync_after_json_write",
        lambda file_name, old_data, new_data, **kwargs: calls.append(file_name),
    )
    storage = JsonStorage("comics_database.json")
    assert storage.write(
        {
            "comics": [
                Comic(id="COMIC001", title="Comic 1").to_dict(),
                Comic(id="COMIC002", title="Comic 2").to_dict(),
                Comic(id="COMIC003", title="Comic 3").to_dict(),
            ],
            "total_comics": 3,
        }
    )
    calls.clear()

    repo = ComicJsonRepository(storage=storage)
    deleted_count = repo.delete_many_by_ids(["COMIC001", "COMIC003", "MISSING"])

    data = storage.read()
    assert deleted_count == 2
    assert [item["id"] for item in data["comics"]] == ["COMIC002"]
    assert data["total_comics"] == 1
    assert calls == ["comics_database.json"]


def test_batch_update_many_by_ids_skips_write_when_no_entity_matches(tmp_path, monkeypatch):
    _reset_json_storage(tmp_path, monkeypatch)
    calls = []
    monkeypatch.setattr(
        catalog_index_writer,
        "sync_after_json_write",
        lambda file_name, old_data, new_data, **kwargs: calls.append(file_name),
    )
    storage = JsonStorage("comics_database.json")
    assert storage.write(
        {
            "comics": [Comic(id="COMIC001", title="Comic 1").to_dict()],
            "total_comics": 1,
        }
    )
    calls.clear()

    repo = ComicJsonRepository(storage=storage)
    updated_count = repo.update_many_by_ids(
        ["MISSING"],
        lambda comic: comic.move_to_trash(),
    )

    assert updated_count == 0
    assert calls == []


def test_batch_save_many_syncs_index_once(tmp_path, monkeypatch):
    _reset_json_storage(tmp_path, monkeypatch)
    calls = []
    monkeypatch.setattr(
        catalog_index_writer,
        "sync_after_json_write",
        lambda file_name, old_data, new_data, **kwargs: calls.append(file_name),
    )
    storage = JsonStorage("comics_database.json")
    assert storage.write(
        {
            "comics": [
                Comic(id="COMIC001", title="Comic 1").to_dict(),
                Comic(id="COMIC002", title="Comic 2").to_dict(),
            ],
            "total_comics": 2,
        }
    )
    calls.clear()

    repo = ComicJsonRepository(storage=storage)
    saved_count = repo.save_many(
        [
            Comic(id="COMIC001", title="Comic 1 Updated"),
            Comic(id="COMIC003", title="Comic 3"),
        ]
    )

    data = storage.read()
    titles = {item["id"]: item["title"] for item in data["comics"]}
    assert saved_count == 2
    assert titles == {
        "COMIC001": "Comic 1 Updated",
        "COMIC002": "Comic 2",
        "COMIC003": "Comic 3",
    }
    assert data["total_comics"] == 3
    assert calls == ["comics_database.json"]


def test_batch_save_many_skips_write_when_entities_missing(tmp_path, monkeypatch):
    _reset_json_storage(tmp_path, monkeypatch)
    calls = []
    monkeypatch.setattr(
        catalog_index_writer,
        "sync_after_json_write",
        lambda file_name, old_data, new_data, **kwargs: calls.append(file_name),
    )
    storage = JsonStorage("comics_database.json")
    assert storage.write({"comics": [], "total_comics": 0})
    calls.clear()

    repo = ComicJsonRepository(storage=storage)
    assert repo.save_many([]) == 0
    assert repo.save_many([None]) == 0
    assert calls == []


def test_content_repository_save_and_delete_pass_changed_ids_to_index(tmp_path, monkeypatch):
    _reset_json_storage(tmp_path, monkeypatch)
    calls = []
    monkeypatch.setattr(
        catalog_index_writer,
        "sync_after_json_write",
        lambda file_name, old_data, new_data, **kwargs: calls.append(
            {"file_name": file_name, "changed_ids": kwargs.get("changed_ids")}
        ),
    )
    comic_storage = JsonStorage("comics_database.json")
    rec_storage = JsonStorage("recommendations_database.json")
    assert comic_storage.write({"comics": [], "total_comics": 0})
    assert rec_storage.write({"recommendations": [], "total_recommendations": 0})
    calls.clear()

    comic_repo = ComicJsonRepository(storage=comic_storage)
    rec_repo = RecommendationJsonRepository(storage=rec_storage)

    assert comic_repo.save(Comic(id="COMIC001", title="Comic 1"))
    assert comic_repo.delete("COMIC001")
    assert rec_repo.save(Recommendation(id="REC001", title="Rec 1"))
    assert rec_repo.delete("REC001")

    assert calls == [
        {"file_name": "comics_database.json", "changed_ids": {"COMIC001"}},
        {"file_name": "comics_database.json", "changed_ids": {"COMIC001"}},
        {"file_name": "recommendations_database.json", "changed_ids": {"REC001"}},
        {"file_name": "recommendations_database.json", "changed_ids": {"REC001"}},
    ]


def test_list_delete_only_syncs_content_files_with_affected_ids(tmp_path, monkeypatch):
    _reset_json_storage(tmp_path, monkeypatch)
    calls = []
    monkeypatch.setattr(
        catalog_index_writer,
        "sync_after_json_write",
        lambda file_name, old_data, new_data, **kwargs: calls.append(
            {"file_name": file_name, "changed_ids": kwargs.get("changed_ids")}
        ),
    )
    list_storage = JsonStorage("lists_database.json")
    comic_storage = JsonStorage("comics_database.json")
    rec_storage = JsonStorage("recommendations_database.json")
    video_storage = JsonStorage("videos_database.json")
    vrec_storage = JsonStorage("video_recommendations_database.json")
    assert list_storage.write(
        {"lists": [{"id": "list_target", "name": "Target"}], "last_updated": "2026-01-01"}
    )
    assert comic_storage.write(
        {
            "comics": [
                {**Comic(id="COMIC001", title="Comic 1").to_dict(), "list_ids": ["list_target"]},
                {**Comic(id="COMIC002", title="Comic 2").to_dict(), "list_ids": []},
            ],
            "total_comics": 2,
        }
    )
    assert rec_storage.write(
        {
            "recommendations": [
                {**Recommendation(id="REC001", title="Rec 1").to_dict(), "list_ids": ["list_target"]},
            ],
            "total_recommendations": 1,
        }
    )
    assert video_storage.write({"videos": [], "total_videos": 0})
    assert vrec_storage.write({"video_recommendations": [], "total_video_recommendations": 0})
    calls.clear()

    repo = ListJsonRepository(storage=list_storage)
    assert repo.delete("list_target")

    assert calls == [
        {"file_name": "lists_database.json", "changed_ids": None},
        {"file_name": "comics_database.json", "changed_ids": {"COMIC001"}},
        {"file_name": "recommendations_database.json", "changed_ids": {"REC001"}},
    ]


def test_comic_batch_delete_permanently_uses_single_repository_write(tmp_path, monkeypatch):
    _reset_json_storage(tmp_path, monkeypatch)
    calls = []
    monkeypatch.setattr(
        catalog_index_writer,
        "sync_after_json_write",
        lambda file_name, old_data, new_data, **kwargs: calls.append(file_name),
    )
    storage = JsonStorage("comics_database.json")
    assert storage.write(
        {
            "comics": [
                Comic(id="COMIC001", title="Comic 1").to_dict(),
                Comic(id="COMIC002", title="Comic 2").to_dict(),
                Comic(id="COMIC003", title="Comic 3").to_dict(),
            ],
            "total_comics": 3,
        }
    )
    calls.clear()

    repo = ComicJsonRepository(storage=storage)
    service = ComicAppService(comic_repo=repo)
    monkeypatch.setattr(service, "_cleanup_comic_files", lambda comic: None)

    result = service.batch_delete_permanently(["COMIC001", "COMIC002"])

    data = storage.read()
    assert result.success is True
    assert result.data["deleted_count"] == 2
    assert [item["id"] for item in data["comics"]] == ["COMIC003"]
    assert calls == ["comics_database.json"]
