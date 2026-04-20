import importlib
import importlib.util
import json
import sys
from pathlib import Path

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

file_parser_module = importlib.import_module("utils.file_parser")
image_handler_module = importlib.import_module("utils.image_handler")


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

    monkeypatch.setattr(local_import_module, "LOCAL_IMPORT_WORKSPACE_DIR", workspace_dir)
    monkeypatch.setattr(local_import_module, "LOCAL_PICTURES_DIR", str(local_pictures_dir))
    monkeypatch.setattr(file_parser_module, "LOCAL_PICTURES_DIR", str(local_pictures_dir))
    monkeypatch.setattr(file_parser_module, "JM_PICTURES_DIR", str(jm_pictures_dir))
    monkeypatch.setattr(file_parser_module, "JSON_FILE", str(comics_json := meta_dir / "comics_database.json"))
    monkeypatch.setattr(file_parser_module, "RECOMMENDATION_JSON_FILE", str(meta_dir / "recommendations_database.json"))
    monkeypatch.setattr(image_handler_module, "JM_COVER_DIR", str(jm_cover_dir))
    tags_json = meta_dir / "tags_database.json"

    service = LocalComicImportService()
    service._db_storage = JsonStorage(str(comics_json))
    service._tag_storage = JsonStorage(str(tags_json))

    source_root = tmp_path / "source"
    work_dir = source_root / "作品A"
    _create_image(work_dir / "001.png", (255, 0, 0))
    _create_image(work_dir / "002.png", (0, 0, 255))

    session_payload = service.create_session_from_path(str(work_dir))
    session_id = str(session_payload["session_id"])

    result = service.commit_session_import(session_id, {".": "work"})
    assert result["imported_count"] == 1
    assert result["failed_count"] == 0

    comics_data = service._db_storage.read()
    assert len(comics_data.get("comics", [])) == 1
    comic = comics_data["comics"][0]

    comic_id = str(comic["id"])
    assert comic_id.startswith("LOCAL")
    original_id = comic_id

    assert comic.get("local_asset_dir_name") == "作品A"
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
    assert len(tag_ids) == 1
    local_tag_id = tag_ids[0]
    assert comic.get("score") == 8.0

    tags_data = service._tag_storage.read()
    local_tag = next((t for t in tags_data.get("tags", []) if t.get("name") == "本地"), None)
    assert local_tag is not None
    assert local_tag.get("id") == local_tag_id


def test_file_parser_local_comic_still_supports_legacy_id_named_directory(tmp_path, monkeypatch):
    local_pictures_dir = tmp_path / "comic" / "local"
    jm_pictures_dir = tmp_path / "comic" / "JM"
    meta_dir = tmp_path / "meta"
    meta_dir.mkdir(parents=True, exist_ok=True)

    comics_json = meta_dir / "comics_database.json"
    recommendations_json = meta_dir / "recommendations_database.json"
    recommendations_json.write_text(json.dumps({"recommendations": []}, ensure_ascii=False), encoding="utf-8")

    monkeypatch.setattr(file_parser_module, "LOCAL_PICTURES_DIR", str(local_pictures_dir))
    monkeypatch.setattr(file_parser_module, "JM_PICTURES_DIR", str(jm_pictures_dir))
    monkeypatch.setattr(file_parser_module, "JSON_FILE", str(comics_json))
    monkeypatch.setattr(file_parser_module, "RECOMMENDATION_JSON_FILE", str(recommendations_json))

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
