import importlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest
from PIL import Image

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

utils_root = BACKEND_ROOT / "utils"
existing_utils = sys.modules.get("utils")
existing_utils_file = str(getattr(existing_utils, "__file__", "") or "")
if not existing_utils_file.startswith(str(utils_root)):
    spec = importlib.util.spec_from_file_location(
        "utils",
        utils_root / "__init__.py",
        submodule_search_locations=[str(utils_root)],
    )
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules["utils"] = module
    spec.loader.exec_module(module)

import application.local_comic_import_service as local_import_module
from application.local_comic_import_service import LocalComicImportService
from infrastructure.persistence.json_storage import JsonStorage
from infrastructure.persistence.repositories import JsonDocumentRepository

file_parser_module = importlib.import_module("utils.file_parser")
image_handler_module = importlib.import_module("utils.image_handler")
json_storage_module = importlib.import_module("infrastructure.persistence.json_storage")
persisted_metadata_module = importlib.import_module("application.persisted_content_metadata")


@pytest.fixture(autouse=True)
def _reset_json_storage_singletons():
    JsonStorage._instances.clear()
    JsonStorage._locks.clear()
    yield
    JsonStorage._instances.clear()
    JsonStorage._locks.clear()


def _create_image(path: Path, color: tuple[int, int, int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (80, 120), color).save(path, format="PNG")


def test_local_import_commit_places_files_in_local_and_sets_cover_and_tag(tmp_path, monkeypatch):
    workspace_dir = tmp_path / "workspace"
    local_pictures_dir = tmp_path / "comic" / "local"
    jm_pictures_dir = tmp_path / "comic" / "JM"
    jm_cover_dir = tmp_path / "static" / "cover" / "JM"
    meta_dir = tmp_path / "meta"
    meta_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(json_storage_module, "get_meta_dir", lambda: str(meta_dir))
    monkeypatch.setattr(local_import_module, "_local_import_workspace_dir", lambda: workspace_dir)
    monkeypatch.setattr(local_import_module, "LOCAL_PICTURES_DIR", str(local_pictures_dir))
    monkeypatch.setattr(file_parser_module, "LOCAL_PICTURES_DIR", str(local_pictures_dir))
    monkeypatch.setattr(file_parser_module, "COMIC_DIR", str(tmp_path / "comic"))
    monkeypatch.setattr(file_parser_module, "JSON_FILE", str(comics_json := meta_dir / "comics_database.json"))
    monkeypatch.setattr(file_parser_module, "RECOMMENDATION_JSON_FILE", str(meta_dir / "recommendations_database.json"))
    monkeypatch.setattr(image_handler_module, "COVER_DIR", str(tmp_path / "static" / "cover"))
    monkeypatch.setattr(persisted_metadata_module, "DATA_DIR", str(tmp_path))
    tags_json = meta_dir / "tags_database.json"

    service = LocalComicImportService()
    service._db_storage = JsonDocumentRepository(str(comics_json), "comics", "total_comics")
    service._tag_storage = JsonDocumentRepository(str(tags_json), "tags", "total_tags")

    source_root = tmp_path / "source"
    work_dir = source_root / "作品A"
    _create_image(work_dir / "001.png", (255, 0, 0))
    _create_image(work_dir / "002.png", (0, 0, 255))

    session_payload = service.create_session_from_path(str(work_dir))
    session_id = str(session_payload["session_id"])

    result = service.commit_session_import(session_id, {".": "work"})
    assert result["imported_count"] == 1
    assert result["failed_count"] == 0

    comics_data = service._db_storage.read_document()
    assert len(comics_data.get("comics", [])) == 1
    comic = comics_data["comics"][0]

    comic_id = str(comic["id"])
    assert comic_id.startswith("LOCAL")
    original_id = comic_id

    assert comic.get("local_asset_dir_name") == "作品A"
    assert comic.get("storage_path_relative") == "comic/local/作品A"
    assert comic.get("storage_path_kind") == "local_dir"
    imported_dir = local_pictures_dir / "作品A"
    assert imported_dir.exists()
    assert not (jm_pictures_dir / original_id).exists()

    parsed_images = file_parser_module.file_parser.parse_comic_images(comic_id)
    assert len(parsed_images) == 2
    assert Path(parsed_images[0]).name == "001.png"

    cover_path = str(comic.get("cover_path", ""))
    assert cover_path.startswith("/static/cover/JM/")
    cover_file = jm_cover_dir / f"{original_id}.jpg"
    assert cover_file.exists()

    with Image.open(cover_file) as cover_image:
        r, g, b = cover_image.convert("RGB").getpixel((0, 0))
        assert r > b
        assert r > g

    tag_ids = comic.get("tag_ids", [])
    assert len(tag_ids) == 2
    assert comic.get("score") == 8.0

    tags_data = service._tag_storage.read_document()
    local_tag = next((t for t in tags_data.get("tags", []) if t.get("name") == "本地"), None)
    assert local_tag is not None
    recent_tag = next((t for t in tags_data.get("tags", []) if t.get("name") == "最近导入"), None)
    assert recent_tag is not None
    assert local_tag.get("id") in tag_ids
    assert recent_tag.get("id") in tag_ids


def test_local_import_reuses_existing_local_tag_without_rewriting_tags(tmp_path, monkeypatch):
    meta_dir = tmp_path / "meta"
    meta_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(json_storage_module, "get_meta_dir", lambda: str(meta_dir))
    tags_json = meta_dir / "tags_database.json"
    tags_json.write_text(
        json.dumps(
            {
                "tags": [
                    {
                        "id": "tag_001",
                        "name": "本地",
                        "content_type": "comic",
                    }
                ],
                "total_tags": 1,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    service = LocalComicImportService()
    service._tag_storage = JsonDocumentRepository(str(tags_json), "tags", "total_tags")
    calls = {"count": 0}
    original_atomic_update = service._tag_storage.atomic_update_document

    def counted_atomic_update(*args, **kwargs):
        calls["count"] += 1
        return original_atomic_update(*args, **kwargs)

    service._tag_storage.atomic_update_document = counted_atomic_update

    assert service._ensure_local_tag_id() == "tag_001"
    assert calls["count"] == 0


def test_local_import_reuses_existing_named_tags_without_rewriting_tags(tmp_path, monkeypatch):
    meta_dir = tmp_path / "meta"
    meta_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(json_storage_module, "get_meta_dir", lambda: str(meta_dir))
    tags_json = meta_dir / "tags_database.json"
    tags_json.write_text(
        json.dumps(
            {
                "tags": [
                    {"id": "tag_001", "name": "本地", "content_type": "comic"},
                    {"id": "tag_002", "name": "长篇", "content_type": "comic"},
                    {"id": "tag_003", "name": "彩色", "content_type": "comic"},
                ],
                "total_tags": 3,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    service = LocalComicImportService()
    service._tag_storage = JsonDocumentRepository(str(tags_json), "tags", "total_tags")
    calls = {"count": 0}
    original_atomic_update = service._tag_storage.atomic_update_document

    def counted_atomic_update(*args, **kwargs):
        calls["count"] += 1
        return original_atomic_update(*args, **kwargs)

    service._tag_storage.atomic_update_document = counted_atomic_update

    assert service._ensure_comic_tag_ids(["长篇", "彩色"]) == {
        "长篇": "tag_002",
        "彩色": "tag_003",
    }
    assert calls["count"] == 0


def test_local_import_appends_comic_records_in_one_batch_write(tmp_path, monkeypatch):
    meta_dir = tmp_path / "meta"
    meta_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(json_storage_module, "get_meta_dir", lambda: str(meta_dir))
    comics_json = meta_dir / "comics_database.json"
    comics_json.write_text(
        json.dumps({"comics": [], "total_comics": 0}, ensure_ascii=False),
        encoding="utf-8",
    )

    service = LocalComicImportService()
    service._db_storage = JsonDocumentRepository(str(comics_json), "comics", "total_comics")
    calls = {"count": 0}
    original_atomic_update = service._db_storage.atomic_update_document

    def counted_atomic_update(*args, **kwargs):
        calls["count"] += 1
        return original_atomic_update(*args, **kwargs)

    service._db_storage.atomic_update_document = counted_atomic_update

    ok, inserted_count = service._append_comic_records_batch(
        [
            {"id": "LOCAL001", "title": "A"},
            {"id": "LOCAL002", "title": "B"},
            {"id": "LOCAL003", "title": "C"},
        ]
    )

    assert ok is True
    assert inserted_count == 3
    assert calls["count"] == 1
    payload = service._db_storage.read_document()
    assert payload["total_comics"] == 3
    assert [item["id"] for item in payload["comics"]] == ["LOCAL001", "LOCAL002", "LOCAL003"]


def test_file_parser_local_comic_still_supports_legacy_id_named_directory(tmp_path, monkeypatch):
    local_pictures_dir = tmp_path / "comic" / "local"
    jm_pictures_dir = tmp_path / "comic" / "JM"
    meta_dir = tmp_path / "meta"
    meta_dir.mkdir(parents=True, exist_ok=True)

    comics_json = meta_dir / "comics_database.json"
    recommendations_json = meta_dir / "recommendations_database.json"
    recommendations_json.write_text(json.dumps({"recommendations": []}, ensure_ascii=False), encoding="utf-8")

    monkeypatch.setattr(file_parser_module, "LOCAL_PICTURES_DIR", str(local_pictures_dir))
    monkeypatch.setattr(file_parser_module, "COMIC_DIR", str(tmp_path / "comic"))
    monkeypatch.setattr(file_parser_module, "JSON_FILE", str(comics_json))
    monkeypatch.setattr(file_parser_module, "RECOMMENDATION_JSON_FILE", str(recommendations_json))
    monkeypatch.setattr(persisted_metadata_module, "DATA_DIR", str(tmp_path))

    legacy_comic_id = "LOCALLEGACY001"
    legacy_dir = local_pictures_dir / legacy_comic_id
    _create_image(legacy_dir / "001.png", (0, 255, 0))
    _create_image(legacy_dir / "002.png", (0, 128, 255))

    comics_json.write_text(
        json.dumps(
            {
                "comics": [
                    {
                        "id": legacy_comic_id,
                        "title": "旧数据作品",
                        "author": "",
                        "cover_path": "",
                        "total_page": 2,
                        "current_page": 1,
                        "tag_ids": [],
                        "list_ids": [],
                    }
                ]
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    parsed_images = file_parser_module.file_parser.parse_comic_images(legacy_comic_id)
    assert len(parsed_images) == 2
    assert Path(parsed_images[0]).name == "001.png"


def test_file_parser_prefers_persisted_relative_path_for_remote_comic(tmp_path, monkeypatch):
    local_pictures_dir = tmp_path / "comic" / "local"
    comic_root = tmp_path / "comic"
    meta_dir = tmp_path / "meta"
    meta_dir.mkdir(parents=True, exist_ok=True)

    comics_json = meta_dir / "comics_database.json"
    recommendations_json = meta_dir / "recommendations_database.json"
    recommendations_json.write_text(json.dumps({"recommendations": []}, ensure_ascii=False), encoding="utf-8")

    monkeypatch.setattr(file_parser_module, "LOCAL_PICTURES_DIR", str(local_pictures_dir))
    monkeypatch.setattr(file_parser_module, "COMIC_DIR", str(comic_root))
    monkeypatch.setattr(file_parser_module, "JSON_FILE", str(comics_json))
    monkeypatch.setattr(file_parser_module, "RECOMMENDATION_JSON_FILE", str(recommendations_json))
    monkeypatch.setattr(persisted_metadata_module, "DATA_DIR", str(tmp_path))

    comic_id = "JM1436655"
    remote_dir = comic_root / "JM" / "1436655"
    _create_image(remote_dir / "001.png", (128, 0, 255))
    _create_image(remote_dir / "002.png", (64, 255, 64))

    comics_json.write_text(
        json.dumps(
            {
                "comics": [
                    {
                        "id": comic_id,
                        "title": "协议路径作品",
                        "author": "作者A",
                        "cover_path": "",
                        "total_page": 2,
                        "current_page": 1,
                        "tag_ids": [],
                        "list_ids": [],
                        "storage_path_relative": "comic/JM/1436655",
                        "storage_path_kind": "local_dir",
                    }
                ]
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    parsed_images = file_parser_module.file_parser.parse_comic_images(comic_id)
    assert len(parsed_images) == 2
    assert Path(parsed_images[0]).name == "001.png"
