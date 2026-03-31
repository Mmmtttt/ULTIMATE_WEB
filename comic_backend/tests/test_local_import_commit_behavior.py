import importlib
from pathlib import Path

from PIL import Image

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
    monkeypatch.setattr(image_handler_module, "JM_COVER_DIR", str(jm_cover_dir))

    comics_json = meta_dir / "comics_database.json"
    tags_json = meta_dir / "tags_database.json"

    service = LocalComicImportService()
    service._db_storage = JsonStorage(str(comics_json))
    service._tag_storage = JsonStorage(str(tags_json))

    source_root = tmp_path / "source"
    work_dir = source_root / "作品A"
    _create_image(work_dir / "001.png", (255, 0, 0))
    _create_image(work_dir / "002.png", (0, 0, 255))

    session_payload = service.create_session_from_path(str(source_root))
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

    imported_dir = local_pictures_dir / original_id
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
