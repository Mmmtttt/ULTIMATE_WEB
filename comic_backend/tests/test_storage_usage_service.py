import sys
from pathlib import Path

import pytest


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from application import storage_usage_service
from application.content_sorting import sort_content_items


def test_get_path_usage_skips_symlink_targets(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    owned_file = data_dir / "owned.bin"
    owned_file.write_bytes(b"owned")

    external_dir = tmp_path / "external"
    external_dir.mkdir()
    (external_dir / "large.bin").write_bytes(b"x" * 1024)

    link_path = data_dir / "external_link"
    try:
        link_path.symlink_to(external_dir, target_is_directory=True)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"symlink is not available in this test environment: {exc}")

    monkeypatch.setattr(storage_usage_service, "DATA_DIR", str(data_dir))
    storage_usage_service.invalidate_storage_usage_cache()

    usage = storage_usage_service.get_path_usage(str(data_dir))

    assert usage["file_count"] == 1
    assert usage["size_bytes"] == len(b"owned")
    assert usage["excluded_reason"] == "contains_symlink"


def test_sort_content_items_supports_storage_size_and_page_count():
    items = [
        {"id": "a", "title": "A", "storage_size_bytes": 20, "total_page": 30},
        {"id": "b", "title": "B", "storage_size_bytes": 80, "total_page": 10},
        {"id": "c", "title": "C", "storage_size_bytes": 40, "total_page": 60},
    ]

    by_size = sort_content_items(items, "storage_size", "desc")
    by_pages = sort_content_items(items, "page_count", "asc")

    assert [item["id"] for item in by_size] == ["b", "c", "a"]
    assert [item["id"] for item in by_pages] == ["b", "a", "c"]


def test_other_storage_ranking_lists_real_files_only(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "misc").mkdir()
    (data_dir / "misc" / "small.txt").write_bytes(b"1")
    (data_dir / "misc" / "large.bin").write_bytes(b"2" * 32)

    managed_roots = []
    for name in (
        "comic",
        "video",
        "comic_recommendation_cache",
        "video_recommendation_cache",
        "cache",
        "meta",
        "static",
        "logs",
    ):
        root = data_dir / name
        root.mkdir()
        managed_roots.append(root)

    monkeypatch.setattr(storage_usage_service, "DATA_DIR", str(data_dir))
    for attribute, root in zip(
        (
            "COMIC_DIR",
            "VIDEO_DIR",
            "COMIC_RECOMMENDATION_CACHE_DIR",
            "VIDEO_RECOMMENDATION_CACHE_DIR",
            "CACHE_ROOT_DIR",
            "META_DIR",
            "STATIC_DIR",
            "LOGS_DIR",
        ),
        managed_roots,
    ):
        monkeypatch.setattr(storage_usage_service, attribute, str(root))

    external_dir = tmp_path / "external"
    external_dir.mkdir()
    (external_dir / "ignored.bin").write_bytes(b"x" * 128)
    symlink_created = False
    try:
        (data_dir / "external_link").symlink_to(external_dir, target_is_directory=True)
        symlink_created = True
    except (OSError, NotImplementedError):
        pass

    result = storage_usage_service.build_storage_ranking("other", limit=1)

    assert result["total"] == 2
    assert [item["title"] for item in result["items"]] == ["large.bin"]
    assert result["items"][0]["content_type"] == "file"
    assert result["items"][0]["relative_path"] == "misc/large.bin"
    if symlink_created:
        assert all("ignored.bin" not in item["id"] for item in result["items"])


def test_storage_overview_does_not_count_recommendation_cache_parent_twice(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    roots = {
        "COMIC_DIR": data_dir / "comic",
        "VIDEO_DIR": data_dir / "video",
        "RECOMMENDATION_CACHE_DIR": data_dir / "recommendation_cache",
        "COMIC_RECOMMENDATION_CACHE_DIR": data_dir / "recommendation_cache" / "comic",
        "VIDEO_RECOMMENDATION_CACHE_DIR": data_dir / "recommendation_cache" / "video",
        "CACHE_ROOT_DIR": data_dir / "cache",
        "META_DIR": data_dir / "meta_data",
        "STATIC_DIR": data_dir / "static",
        "LOGS_DIR": data_dir / "logs",
    }
    for root in roots.values():
        root.mkdir(parents=True, exist_ok=True)

    files = {
        roots["COMIC_DIR"] / "comic.bin": 10,
        roots["VIDEO_DIR"] / "video.bin": 20,
        roots["COMIC_RECOMMENDATION_CACHE_DIR"] / "comic-cache.bin": 30,
        roots["VIDEO_RECOMMENDATION_CACHE_DIR"] / "video-cache.bin": 40,
        roots["CACHE_ROOT_DIR"] / "cache.bin": 50,
        roots["META_DIR"] / "meta.bin": 60,
        roots["STATIC_DIR"] / "static.bin": 70,
        roots["LOGS_DIR"] / "log.bin": 80,
        data_dir / "unmanaged" / "other.bin": 90,
    }
    for path, size in files.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"x" * size)

    monkeypatch.setattr(storage_usage_service, "DATA_DIR", str(data_dir))
    for name, root in roots.items():
        monkeypatch.setattr(storage_usage_service, name, str(root))
    monkeypatch.setattr(storage_usage_service, "_load_storage_overview_items", lambda: ([], [], [], []))
    storage_usage_service.invalidate_storage_usage_cache()

    overview = storage_usage_service.build_storage_overview()

    assert overview["total"]["size_bytes"] == sum(files.values())
    other = next(item for item in overview["modules"] if item["key"] == "other")
    assert other["size_bytes"] == 90
