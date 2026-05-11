import json
import os
import sys
import importlib
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

os.environ.setdefault("ULTIMATE_CONFIG_DIR", str(BACKEND_ROOT / ".pytest_runtime_config"))

import application.comic_app_service as comic_app_service_module
import application.persisted_content_metadata as persisted_metadata_module
import application.video_app_service as video_app_service_module
import infrastructure.recommendation_cache_manager as recommendation_cache_manager_module
from core.host_platform_fallback import (
    build_host_recommendation_cache_dir,
    infer_existing_host_comic_dir,
    infer_existing_host_recommendation_cache_dir,
    merge_host_video_display,
)
from domain.comic import Comic

file_parser_module = importlib.import_module("utils.file_parser")


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def test_infer_existing_host_comic_dir_for_jm_uses_split_directory(tmp_path):
    comic_root = tmp_path / "comic"
    local_root = comic_root / "local"
    target_dir = comic_root / "JM" / "1406651"
    target_dir.mkdir(parents=True, exist_ok=True)

    resolved = infer_existing_host_comic_dir(
        "JM1406651",
        {"platform": "JM", "title": "作品", "author": "作者"},
        comic_root=str(comic_root),
        local_root=str(local_root),
    )

    assert resolved == str(target_dir)


def test_infer_existing_host_comic_dir_for_pk_supports_new_and_legacy_layout(tmp_path):
    comic_root = tmp_path / "comic"
    local_root = comic_root / "local"

    new_dir = comic_root / "PK" / "作者A" / "作品A"
    new_dir.mkdir(parents=True, exist_ok=True)
    legacy_dir = comic_root / "PK" / "comics" / "作者B" / "作品B"
    legacy_dir.mkdir(parents=True, exist_ok=True)

    resolved_new = infer_existing_host_comic_dir(
        "PKabc123",
        {"platform": "PK", "author": "作者A", "title": "作品A"},
        comic_root=str(comic_root),
        local_root=str(local_root),
    )
    resolved_legacy = infer_existing_host_comic_dir(
        "PKdef456",
        {"platform": "PK", "author": "作者B", "title": "作品B"},
        comic_root=str(comic_root),
        local_root=str(local_root),
    )
    resolved_missing = infer_existing_host_comic_dir(
        "PKmissing",
        {"platform": "PK", "author": "作者C", "title": "作品C"},
        comic_root=str(comic_root),
        local_root=str(local_root),
    )

    assert resolved_new == str(new_dir)
    assert resolved_legacy == str(legacy_dir)
    assert resolved_missing == ""


def test_recommendation_cache_dir_for_pk_uses_same_author_title_layout_as_local_library(tmp_path):
    cache_root = tmp_path / "recommendation_cache" / "comic"
    existing_dir = cache_root / "PK" / "作者A" / "作品A"
    existing_dir.mkdir(parents=True, exist_ok=True)

    canonical = build_host_recommendation_cache_dir(
        "PKabc123",
        {"platform": "PK", "author": "作者A", "title": "作品A"},
        cache_root=str(cache_root),
    )
    resolved = infer_existing_host_recommendation_cache_dir(
        "PKabc123",
        {"platform": "PK", "author": "作者A", "title": "作品A"},
        cache_root=str(cache_root),
    )

    assert canonical == str(existing_dir)
    assert resolved == str(existing_dir)


def test_recommendation_cache_manager_rebuilds_pk_cache_dir_from_author_title_when_stored_relative_is_invalid(
    tmp_path,
    monkeypatch,
):
    data_dir = tmp_path / "data"
    meta_dir = data_dir / "meta_data"
    cache_root = data_dir / "recommendation_cache" / "comic"
    actual_dir = cache_root / "PK" / "同步作者" / "同步作品"
    actual_dir.mkdir(parents=True, exist_ok=True)

    recommendations_json = meta_dir / "recommendations_database.json"
    _write_json(
        recommendations_json,
        {
            "recommendations": [
                {
                    "id": "PK698e14e13951674692432507",
                    "platform": "PK",
                    "author": "同步作者",
                    "title": "同步作品",
                    "storage_path_relative": "recommendation_cache/comic/PK/698e14e13951674692432507",
                    "storage_path_kind": "preview_cache_dir",
                }
            ]
        },
    )

    monkeypatch.setattr(persisted_metadata_module, "DATA_DIR", str(data_dir))
    monkeypatch.setattr(
        recommendation_cache_manager_module,
        "RECOMMENDATION_JSON_FILE",
        str(recommendations_json),
    )
    monkeypatch.setattr(
        recommendation_cache_manager_module.RecommendationCacheManager,
        "_instance",
        None,
    )
    manager = recommendation_cache_manager_module.RecommendationCacheManager(
        cache_dir=str(cache_root),
        cache_index_file=str(meta_dir / "recommendation_cache_index.json"),
    )

    resolved = manager._get_comic_cache_dir("PK698e14e13951674692432507")

    assert resolved == str(actual_dir)


def test_recommendation_cache_manager_reads_pk_cached_page_from_author_title_layout(
    tmp_path,
    monkeypatch,
):
    data_dir = tmp_path / "data"
    meta_dir = data_dir / "meta_data"
    cache_root = data_dir / "recommendation_cache" / "comic"
    actual_dir = cache_root / "PK" / "同步作者" / "同步作品"
    actual_dir.mkdir(parents=True, exist_ok=True)
    (actual_dir / "001.png").write_bytes(b"fake-image")

    recommendations_json = meta_dir / "recommendations_database.json"
    _write_json(
        recommendations_json,
        {
            "recommendations": [
                {
                    "id": "PK698e14e13951674692432507",
                    "platform": "PK",
                    "author": "同步作者",
                    "title": "同步作品",
                    "storage_path_relative": "recommendation_cache/comic/PK/698e14e13951674692432507",
                    "storage_path_kind": "preview_cache_dir",
                }
            ]
        },
    )

    monkeypatch.setattr(persisted_metadata_module, "DATA_DIR", str(data_dir))
    monkeypatch.setattr(
        recommendation_cache_manager_module,
        "RECOMMENDATION_JSON_FILE",
        str(recommendations_json),
    )
    monkeypatch.setattr(
        recommendation_cache_manager_module.RecommendationCacheManager,
        "_instance",
        None,
    )
    manager = recommendation_cache_manager_module.RecommendationCacheManager(
        cache_dir=str(cache_root),
        cache_index_file=str(meta_dir / "recommendation_cache_index.json"),
    )

    image_path = manager.get_cached_page_path("PK698e14e13951674692432507", 1)

    assert image_path == str(actual_dir / "001.png")


def test_file_parser_ignores_invalid_jm_relative_path_and_falls_back_to_host_layout(tmp_path, monkeypatch):
    comic_root = tmp_path / "comic"
    local_root = comic_root / "local"
    actual_dir = comic_root / "JM" / "1406651"
    actual_dir.mkdir(parents=True, exist_ok=True)
    meta_dir = tmp_path / "meta"

    comics_json = meta_dir / "comics_database.json"
    recommendations_json = meta_dir / "recommendations_database.json"
    _write_json(
        comics_json,
        {
            "comics": [
                {
                    "id": "JM1406651",
                    "title": "旧记录作品",
                    "author": "作者A",
                    "storage_path_relative": "comic/JM1406651",
                    "storage_path_kind": "local_dir",
                }
            ]
        },
    )
    _write_json(recommendations_json, {"recommendations": []})

    monkeypatch.setattr(persisted_metadata_module, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(file_parser_module, "COMIC_DIR", str(comic_root))
    monkeypatch.setattr(file_parser_module, "LOCAL_PICTURES_DIR", str(local_root))
    monkeypatch.setattr(file_parser_module, "JSON_FILE", str(comics_json))
    monkeypatch.setattr(file_parser_module, "RECOMMENDATION_JSON_FILE", str(recommendations_json))

    resolved = file_parser_module.file_parser._get_comic_dir("JM1406651")

    assert resolved == str(actual_dir)


def test_comic_app_service_rebuilds_storage_path_from_existing_host_layout(tmp_path, monkeypatch):
    comic_root = tmp_path / "comic"
    local_root = comic_root / "local"
    actual_dir = comic_root / "JM" / "1406651"
    actual_dir.mkdir(parents=True, exist_ok=True)
    meta_dir = tmp_path / "meta"

    comics_json = meta_dir / "comics_database.json"
    recommendations_json = meta_dir / "recommendations_database.json"
    _write_json(
        comics_json,
        {
            "comics": [
                {
                    "id": "JM1406651",
                    "title": "旧记录作品",
                    "author": "作者A",
                    "storage_path_relative": "comic/JM1406651",
                    "storage_path_kind": "local_dir",
                }
            ]
        },
    )
    _write_json(recommendations_json, {"recommendations": []})

    monkeypatch.setattr(persisted_metadata_module, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(file_parser_module, "COMIC_DIR", str(comic_root))
    monkeypatch.setattr(file_parser_module, "LOCAL_PICTURES_DIR", str(local_root))
    monkeypatch.setattr(file_parser_module, "JSON_FILE", str(comics_json))
    monkeypatch.setattr(file_parser_module, "RECOMMENDATION_JSON_FILE", str(recommendations_json))
    monkeypatch.setattr(comic_app_service_module, "COMIC_DIR", str(comic_root))
    monkeypatch.setattr(comic_app_service_module, "LOCAL_PICTURES_DIR", str(local_root))

    service = comic_app_service_module.ComicAppService()
    comic = Comic.from_dict(
        {
            "id": "JM1406651",
            "title": "旧记录作品",
            "author": "作者A",
            "storage_path_relative": "comic/JM1406651",
            "storage_path_kind": "local_dir",
        }
    )

    storage_path, storage_kind = service._resolve_comic_storage_path(comic)

    assert storage_path == str(actual_dir)
    assert storage_kind == "local_dir"


def test_merge_host_video_display_uses_builtin_platform_rules_without_manifest():
    javdb_display = merge_host_video_display({"id": "JAVDBabc123"})
    javbus_display = merge_host_video_display({"cover_path": "/static/cover/JAVBUS/xyz.jpg"})
    local_display = merge_host_video_display({"id": "LOCALV001"})
    unknown_display = merge_host_video_display({"id": "UNKNOWN001"})

    assert (((javdb_display.get("display") or {}).get("cover") or {}).get("aspect_ratio")) == "16 / 9"
    assert (((javdb_display.get("display") or {}).get("cover") or {}).get("mobile_aspect_ratio")) == "3 / 2"
    assert (((javbus_display.get("display") or {}).get("cover") or {}).get("aspect_ratio")) == "2 / 3"
    assert (((javbus_display.get("display") or {}).get("cover") or {}).get("mobile_aspect_ratio")) == "2 / 3"
    assert (((local_display.get("display") or {}).get("cover") or {}).get("aspect_ratio")) == "16 / 9"
    assert (((local_display.get("display") or {}).get("cover") or {}).get("mobile_aspect_ratio")) == "16 / 9"
    assert (((unknown_display.get("display") or {}).get("cover") or {}).get("aspect_ratio")) == "16 / 9"
    assert (((unknown_display.get("display") or {}).get("cover") or {}).get("mobile_aspect_ratio")) == "16 / 9"


def test_video_app_service_annotates_local_video_with_builtin_display_when_manifest_missing(monkeypatch):
    monkeypatch.setattr(video_app_service_module, "annotate_item", lambda item, **kwargs: dict(item))

    annotated = video_app_service_module.VideoAppService._annotate_video_record(
        {
            "id": "JAVDBakKE7q",
            "platform": "",
            "display": {},
            "cover_path": "/static/cover/JAVDB/akKE7q.jpg",
        }
    )

    assert ((((annotated.get("display") or {}).get("cover") or {}).get("aspect_ratio")) == "16 / 9")
    assert ((((annotated.get("display") or {}).get("cover") or {}).get("mobile_aspect_ratio")) == "3 / 2")


def test_video_app_service_annotates_local_video_with_landscape_default_when_display_empty(monkeypatch):
    monkeypatch.setattr(video_app_service_module, "annotate_item", lambda item, **kwargs: dict(item))

    annotated = video_app_service_module.VideoAppService._annotate_video_record(
        {
            "id": "LOCALV_DEMO_001",
            "platform": "",
            "display": {},
            "cover_path": "",
            "local_video_path": "/media/video/LOCAL/demo/source.mp4",
            "content_type": "video",
        }
    )

    assert ((((annotated.get("display") or {}).get("cover") or {}).get("aspect_ratio")) == "16 / 9")
    assert ((((annotated.get("display") or {}).get("cover") or {}).get("mobile_aspect_ratio")) == "16 / 9")
