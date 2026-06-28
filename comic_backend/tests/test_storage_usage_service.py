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
