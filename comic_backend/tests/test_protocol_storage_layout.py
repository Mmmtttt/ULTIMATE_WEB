import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from core import constants


def test_protocol_storage_layout_includes_manifest_declared_platform_dirs():
    dirs = {str(Path(item)).replace("\\", "/") for item in constants.list_protocol_platform_storage_dirs()}

    assert any("/video/" in item for item in dirs)
    assert any("/static/cover/" in item for item in dirs)


def test_platform_cover_dirs_include_manifest_declared_comic_platforms():
    cover_dirs = {str(Path(item)).replace("\\", "/") for item in constants.list_platform_cover_dirs(media_type="comic")}

    assert cover_dirs
    assert all("/static/cover/" in item for item in cover_dirs)


def test_platform_cover_dirs_include_manifest_declared_video_platforms_and_local_cover_root():
    cover_dirs = {str(Path(item)).replace("\\", "/") for item in constants.list_platform_cover_dirs(media_type="video")}

    assert any(item.endswith("/static/cover/LOCAL") for item in cover_dirs)
    assert any(not item.endswith("/static/cover/LOCAL") for item in cover_dirs)
    assert any(item.endswith("/static/cover/LOCAL") for item in cover_dirs)
