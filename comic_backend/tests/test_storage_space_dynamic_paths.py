import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from application import local_comic_import_service
from core import storage_layout
from core.constants import (
    CACHE_ROOT_DIR,
    COVER_DIR,
    JSON_FILE,
    LOCAL_PICTURES_DIR,
    LOCAL_VIDEO_COVER_DIR,
    LOCAL_VIDEO_PICTURES_DIR,
    SPACE_MODE_NORMAL,
    SPACE_MODE_PRIVATE,
    set_current_space_mode,
)


def test_imported_path_constants_follow_active_data_space(tmp_path, monkeypatch):
    normal_dir = tmp_path / "UltimateData"
    private_dir = tmp_path / "UltimateData_private"
    monkeypatch.setattr(storage_layout, "_NORMAL_DATA_DIR", str(normal_dir))
    monkeypatch.setattr(storage_layout, "_PRIVATE_DATA_DIR", str(private_dir))

    try:
        set_current_space_mode(SPACE_MODE_NORMAL)
        assert Path(JSON_FILE) == normal_dir / "meta_data" / "comics_database.json"
        assert Path(COVER_DIR) == normal_dir / "static" / "cover"
        assert Path(LOCAL_PICTURES_DIR) == normal_dir / "comic" / "local"
        assert Path(LOCAL_VIDEO_PICTURES_DIR) == normal_dir / "video" / "LOCAL"
        assert Path(LOCAL_VIDEO_COVER_DIR) == normal_dir / "static" / "cover" / "LOCAL"

        set_current_space_mode(SPACE_MODE_PRIVATE)
        assert Path(JSON_FILE) == private_dir / "meta_data" / "comics_database.json"
        assert Path(COVER_DIR) == private_dir / "static" / "cover"
        assert Path(LOCAL_PICTURES_DIR) == private_dir / "comic" / "local"
        assert Path(LOCAL_VIDEO_PICTURES_DIR) == private_dir / "video" / "LOCAL"
        assert Path(LOCAL_VIDEO_COVER_DIR) == private_dir / "static" / "cover" / "LOCAL"
        assert Path(CACHE_ROOT_DIR) == private_dir / "cache"
    finally:
        set_current_space_mode(SPACE_MODE_NORMAL)


def test_local_comic_import_temp_and_softref_state_are_space_local(tmp_path, monkeypatch):
    normal_dir = tmp_path / "normal"
    private_dir = tmp_path / "private"
    monkeypatch.setattr(storage_layout, "_NORMAL_DATA_DIR", str(normal_dir))
    monkeypatch.setattr(storage_layout, "_PRIVATE_DATA_DIR", str(private_dir))

    try:
        set_current_space_mode(SPACE_MODE_PRIVATE)
        assert local_comic_import_service._softref_passwords_file() == private_dir / "cache" / "comic_softref_passwords.json"
        assert local_comic_import_service._local_import_workspace_dir() == private_dir / "cache" / "comic_local_import_workspace"

        set_current_space_mode(SPACE_MODE_NORMAL)
        assert local_comic_import_service._softref_passwords_file() == normal_dir / "cache" / "comic_softref_passwords.json"
        assert local_comic_import_service._local_import_workspace_dir() == normal_dir / "cache" / "comic_local_import_workspace"
    finally:
        set_current_space_mode(SPACE_MODE_NORMAL)


def test_private_data_dir_default_and_legacy_relative_value_resolve_next_to_normal_dir(tmp_path, monkeypatch):
    normal_dir = tmp_path / "data_parent" / "UltimateData"
    monkeypatch.setattr(storage_layout, "_NORMAL_DATA_DIR", str(normal_dir))

    monkeypatch.setattr(
        storage_layout,
        "_load_server_config",
        lambda: {"auth": {"private_data_dir": "UltimateData_private"}},
    )
    assert Path(storage_layout._resolve_private_data_dir()) == normal_dir.parent / "UltimateData_private"

    monkeypatch.setattr(
        storage_layout,
        "_load_server_config",
        lambda: {"auth": {"private_data_dir": "./../UltimateData_private"}},
    )
    assert Path(storage_layout._resolve_private_data_dir()) == normal_dir.parent / "UltimateData_private"
