import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from infrastructure.persistence.json_storage import JsonStorage
import infrastructure.persistence.json_storage as json_storage_module
import infrastructure.persistence.catalog_index.connection as catalog_index_connection
import infrastructure.persistence.catalog_index.writer as catalog_index_writer


def test_json_storage_singleton_uses_normalized_absolute_path(tmp_path, monkeypatch):
    JsonStorage._instances.clear()
    JsonStorage._locks.clear()
    monkeypatch.setattr(json_storage_module, "get_meta_dir", lambda: str(tmp_path))
    json_path = tmp_path / "sample.json"
    relative_like = json_path.parent / "." / json_path.name

    first = JsonStorage(str(json_path))
    second = JsonStorage(str(relative_like))

    assert first is second
    assert first.json_file == str(json_path.resolve())


def test_json_storage_creates_precise_default_video_recommendation_schema(tmp_path, monkeypatch):
    JsonStorage._instances.clear()
    JsonStorage._locks.clear()
    monkeypatch.setattr(json_storage_module, "get_meta_dir", lambda: str(tmp_path))
    json_path = tmp_path / "video_recommendations_database.json"
    storage = JsonStorage(str(json_path))

    payload = storage.read()

    assert payload["total_video_recommendations"] == 0
    assert payload["video_recommendations"] == []


def test_deferred_catalog_index_sync_coalesces_repeated_writes(tmp_path, monkeypatch):
    JsonStorage._instances.clear()
    JsonStorage._locks.clear()
    monkeypatch.setattr(json_storage_module, "get_meta_dir", lambda: str(tmp_path))
    calls = []

    def fake_sync(file_name, old_data, new_data, **kwargs):
        calls.append(
            {
                "file_name": file_name,
                "old_data": old_data,
                "new_data": new_data,
                "changed_ids": kwargs.get("changed_ids"),
            }
        )

    monkeypatch.setattr(catalog_index_writer, "sync_after_json_write", fake_sync)
    index_path = tmp_path / "catalog_index.db"
    index_path.touch()
    monkeypatch.setattr(catalog_index_connection, "get_catalog_index_path", lambda: str(index_path))
    storage = JsonStorage("comics_database.json")

    with JsonStorage.defer_catalog_index_sync():
        assert storage.write({"comics": [{"id": "LOCAL001"}], "total_comics": 1})
        assert storage.atomic_update(
            lambda data: {
                **data,
                "comics": [
                    {"id": "LOCAL001"},
                    {"id": "LOCAL002"},
                ],
                "total_comics": 2,
            }
        )

    assert len(calls) == 1
    assert calls[0]["file_name"] == "comics_database.json"
    assert calls[0]["old_data"] is None
    assert [item["id"] for item in calls[0]["new_data"]["comics"]] == ["LOCAL001", "LOCAL002"]


def test_atomic_update_catalog_index_snapshot_can_be_limited_to_changed_ids(tmp_path, monkeypatch):
    JsonStorage._instances.clear()
    JsonStorage._locks.clear()
    monkeypatch.setattr(json_storage_module, "get_meta_dir", lambda: str(tmp_path))
    calls = []

    def fake_sync(file_name, old_data, new_data, **kwargs):
        calls.append(
            {
                "file_name": file_name,
                "old_data": old_data,
                "new_data": new_data,
                "changed_ids": kwargs.get("changed_ids"),
            }
        )

    monkeypatch.setattr(catalog_index_writer, "sync_after_json_write", fake_sync)
    index_path = tmp_path / "catalog_index.db"
    index_path.touch()
    monkeypatch.setattr(catalog_index_connection, "get_catalog_index_path", lambda: str(index_path))
    storage = JsonStorage("comics_database.json")
    assert storage.write(
        {
            "comics": [
                {"id": "LOCAL001", "title": "Comic 1"},
                {"id": "LOCAL002", "title": "Comic 2"},
                {"id": "LOCAL003", "title": "Comic 3"},
            ],
            "total_comics": 3,
        }
    )
    calls.clear()

    assert storage.atomic_update(
        lambda data: {
            **data,
            "comics": [
                item if item["id"] != "LOCAL002" else {**item, "title": "Comic 2 Updated"}
                for item in data["comics"]
            ],
        },
        catalog_index_changed_ids=["LOCAL002"],
    )

    assert len(calls) == 1
    assert calls[0]["file_name"] == "comics_database.json"
    assert calls[0]["changed_ids"] == {"LOCAL002"}
    assert [item["id"] for item in calls[0]["old_data"]["comics"]] == ["LOCAL002"]
    assert len(calls[0]["new_data"]["comics"]) == 3


def test_deferred_catalog_index_sync_uses_single_tag_rebuild_when_tags_changed(tmp_path, monkeypatch):
    JsonStorage._instances.clear()
    JsonStorage._locks.clear()
    monkeypatch.setattr(json_storage_module, "get_meta_dir", lambda: str(tmp_path))
    calls = []

    def fake_sync(file_name, old_data, new_data, **kwargs):
        calls.append(file_name)

    monkeypatch.setattr(catalog_index_writer, "sync_after_json_write", fake_sync)
    comic_storage = JsonStorage("comics_database.json")
    tag_storage = JsonStorage("tags_database.json")

    with JsonStorage.defer_catalog_index_sync():
        assert comic_storage.write({"comics": [{"id": "LOCAL001"}], "total_comics": 1})
        assert tag_storage.write({"tags": [{"id": "tag_local", "name": "本地"}]})

    assert calls == ["tags_database.json"]
