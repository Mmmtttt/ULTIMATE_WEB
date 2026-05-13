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
import protocol.gateway as gateway_module
import protocol.registry as registry_module
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


def _write_plugin(plugin_dir: Path, *, plugin_id: str, config_key: str, media_type: str, host_prefix: str, overlay: dict):
    plugin_dir.mkdir(parents=True, exist_ok=True)
    (plugin_dir / "ultimate-plugin.json").write_text(
        json.dumps(
            {
                "protocol_version": "2.0",
                "plugin": {
                    "id": plugin_id,
                    "name": plugin_id,
                    "version": "1.0.0",
                    "entrypoint": "protocol.snapshot_provider:MetadataOnlyProvider",
                    "config_key": config_key,
                },
                "media_types": [media_type],
                "identity": {
                    "platform_label": host_prefix,
                    "host_id_prefix": host_prefix,
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    overlay_payload = {
        "protocol_version": "2.0",
        "plugin": {
            "id": plugin_id,
        },
    }
    overlay_payload.update(overlay or {})
    (plugin_dir / "ultimate-host.json").write_text(
        json.dumps(overlay_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _install_protocol_registry(monkeypatch, third_party_root: Path):
    _write_plugin(
        third_party_root / "JMComic-Crawler-Python",
        plugin_id="comic.jmcomic",
        config_key="jmcomic",
        media_type="comic",
        host_prefix="JM",
        overlay={
            "storage": {
                "host_resolution": {
                    "comic_local_dir": {
                        "path_templates": ["{host_prefix}/{original_id}"],
                    },
                    "comic_preview_cache_dir": {
                        "path_templates": ["{host_prefix}/{original_id}"],
                    },
                }
            },
            "presentation": {
                "media_card": {
                    "cover": {
                        "aspect_ratio": "2 / 3",
                        "mobile_aspect_ratio": "2 / 3",
                        "fit": "cover",
                    }
                }
            },
        },
    )
    _write_plugin(
        third_party_root / "Picacomic-Crawler",
        plugin_id="comic.picacomic",
        config_key="picacomic",
        media_type="comic",
        host_prefix="PK",
        overlay={
            "storage": {
                "host_resolution": {
                    "comic_local_dir": {
                        "path_templates": [
                            "{host_prefix}/{author}/{title}",
                            "{host_prefix}/comics/{author}/{title}",
                        ],
                    },
                    "comic_preview_cache_dir": {
                        "path_templates": [
                            "{host_prefix}/{author}/{title}",
                            "{host_prefix}/comics/{author}/{title}",
                        ],
                    },
                }
            },
            "presentation": {
                "media_card": {
                    "cover": {
                        "aspect_ratio": "2 / 3",
                        "mobile_aspect_ratio": "2 / 3",
                        "fit": "cover",
                    }
                }
            },
        },
    )
    _write_plugin(
        third_party_root / "javdb-api-scraper",
        plugin_id="video.javdb",
        config_key="javdb",
        media_type="video",
        host_prefix="JAVDB",
        overlay={
            "presentation": {
                "media_card": {
                    "cover": {
                        "aspect_ratio": "16 / 9",
                        "mobile_aspect_ratio": "3 / 2",
                        "fit": "cover",
                    }
                }
            }
        },
    )
    _write_plugin(
        third_party_root / "javdb-api-scraper" / "javbus_plugin",
        plugin_id="video.javbus",
        config_key="javbus",
        media_type="video",
        host_prefix="JAVBUS",
        overlay={
            "presentation": {
                "media_card": {
                    "cover": {
                        "aspect_ratio": "2 / 3",
                        "mobile_aspect_ratio": "2 / 3",
                        "fit": "contain",
                    }
                }
            }
        },
    )

    registry = registry_module.PluginRegistry(search_root=str(third_party_root))
    gateway = gateway_module.ProtocolGateway(registry=registry)
    monkeypatch.setattr(registry_module, "_registry_singleton", registry)
    monkeypatch.setattr(gateway_module, "_gateway_singleton", gateway)
    registry.refresh()
    return registry


def test_infer_existing_host_comic_dir_for_jm_uses_protocol_template(tmp_path, monkeypatch):
    _install_protocol_registry(monkeypatch, tmp_path / "third_party")
    comic_root = tmp_path / "comic"
    local_root = comic_root / "local"
    target_dir = comic_root / "JM" / "1406651"
    target_dir.mkdir(parents=True, exist_ok=True)

    resolved = infer_existing_host_comic_dir(
        "JM1406651",
        {"title": "作品", "author": "作者"},
        comic_root=str(comic_root),
        local_root=str(local_root),
    )

    assert resolved == str(target_dir)


def test_infer_existing_host_comic_dir_for_pk_supports_canonical_and_legacy_protocol_templates(tmp_path, monkeypatch):
    _install_protocol_registry(monkeypatch, tmp_path / "third_party")
    comic_root = tmp_path / "comic"
    local_root = comic_root / "local"

    new_dir = comic_root / "PK" / "作者A" / "作品A"
    new_dir.mkdir(parents=True, exist_ok=True)
    legacy_dir = comic_root / "PK" / "comics" / "作者B" / "作品B"
    legacy_dir.mkdir(parents=True, exist_ok=True)

    resolved_new = infer_existing_host_comic_dir(
        "PKabc123",
        {"author": "作者A", "title": "作品A"},
        comic_root=str(comic_root),
        local_root=str(local_root),
    )
    resolved_legacy = infer_existing_host_comic_dir(
        "PKdef456",
        {"author": "作者B", "title": "作品B"},
        comic_root=str(comic_root),
        local_root=str(local_root),
    )
    resolved_missing = infer_existing_host_comic_dir(
        "PKmissing",
        {"author": "作者C", "title": "作品C"},
        comic_root=str(comic_root),
        local_root=str(local_root),
    )

    assert resolved_new == str(new_dir)
    assert resolved_legacy == str(legacy_dir)
    assert resolved_missing == ""


def test_recommendation_cache_dir_for_pk_uses_protocol_templates_matching_local_library(tmp_path, monkeypatch):
    _install_protocol_registry(monkeypatch, tmp_path / "third_party")
    cache_root = tmp_path / "recommendation_cache" / "comic"
    existing_dir = cache_root / "PK" / "作者A" / "作品A"
    existing_dir.mkdir(parents=True, exist_ok=True)
    legacy_dir = cache_root / "PK" / "comics" / "作者B" / "作品B"
    legacy_dir.mkdir(parents=True, exist_ok=True)

    canonical = build_host_recommendation_cache_dir(
        "PKabc123",
        {"author": "作者A", "title": "作品A"},
        cache_root=str(cache_root),
    )
    resolved = infer_existing_host_recommendation_cache_dir(
        "PKabc123",
        {"author": "作者A", "title": "作品A"},
        cache_root=str(cache_root),
    )
    resolved_legacy = infer_existing_host_recommendation_cache_dir(
        "PKdef456",
        {"author": "作者B", "title": "作品B"},
        cache_root=str(cache_root),
    )

    assert canonical == str(existing_dir)
    assert resolved == str(existing_dir)
    assert resolved_legacy == str(legacy_dir)


def test_recommendation_cache_manager_rebuilds_pk_cache_dir_from_protocol_templates_when_stored_relative_is_invalid(
    tmp_path,
    monkeypatch,
):
    _install_protocol_registry(monkeypatch, tmp_path / "third_party")
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


def test_recommendation_cache_manager_reads_pk_cached_page_from_protocol_legacy_template(
    tmp_path,
    monkeypatch,
):
    _install_protocol_registry(monkeypatch, tmp_path / "third_party")
    data_dir = tmp_path / "data"
    meta_dir = data_dir / "meta_data"
    cache_root = data_dir / "recommendation_cache" / "comic"
    legacy_dir = cache_root / "PK" / "comics" / "旧作者" / "旧作品"
    legacy_dir.mkdir(parents=True, exist_ok=True)
    (legacy_dir / "001.png").write_bytes(b"fake-image")

    recommendations_json = meta_dir / "recommendations_database.json"
    _write_json(
        recommendations_json,
        {
            "recommendations": [
                {
                    "id": "PKlegacy0001",
                    "author": "旧作者",
                    "title": "旧作品",
                    "storage_path_relative": "recommendation_cache/comic/PK/legacy0001",
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

    image_path = manager.get_cached_page_path("PKlegacy0001", 1)

    assert image_path == str(legacy_dir / "001.png")


def test_infer_existing_host_comic_dir_for_pk_works_from_snapshot_only_registry(tmp_path, monkeypatch):
    snapshot_path = tmp_path / "mobile_protocol_snapshot.json"
    snapshot_path.write_text(
        json.dumps(
            {
                "version": 1,
                "manifests": [
                    {
                        "protocol_version": "2.0",
                        "plugin": {
                            "id": "comic.picacomic",
                            "name": "Picacomic",
                            "version": "0.0.0-snapshot",
                            "config_key": "picacomic",
                            "entrypoint": "protocol.snapshot_provider:MetadataOnlyProvider",
                        },
                        "media_types": ["comic"],
                        "identity": {
                            "platform_label": "PK",
                            "host_id_prefix": "PK",
                        },
                        "storage": {
                            "comic_dir": {
                                "template": "{author}/{title}",
                                "fallback_templates": [
                                    "comics/{author}/{title}",
                                    "{album_id}",
                                ],
                            }
                        },
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("BACKEND_PROTOCOL_SNAPSHOT_PATH", str(snapshot_path))
    registry = registry_module.PluginRegistry(search_root=str(tmp_path / "missing_third_party"))
    gateway = gateway_module.ProtocolGateway(registry=registry)
    monkeypatch.setattr(registry_module, "_registry_singleton", registry)
    monkeypatch.setattr(gateway_module, "_gateway_singleton", gateway)
    registry.refresh()

    comic_root = tmp_path / "comic"
    local_root = comic_root / "local"
    new_dir = comic_root / "PK" / "作者A" / "作品A"
    new_dir.mkdir(parents=True, exist_ok=True)
    legacy_dir = comic_root / "PK" / "comics" / "作者B" / "作品B"
    legacy_dir.mkdir(parents=True, exist_ok=True)

    resolved_new = infer_existing_host_comic_dir(
        "PKnew001",
        {"author": "作者A", "title": "作品A"},
        comic_root=str(comic_root),
        local_root=str(local_root),
    )
    resolved_legacy = infer_existing_host_comic_dir(
        "PKlegacy001",
        {"author": "作者B", "title": "作品B"},
        comic_root=str(comic_root),
        local_root=str(local_root),
    )

    assert resolved_new == str(new_dir)
    assert resolved_legacy == str(legacy_dir)


def test_recommendation_cache_manager_does_not_fabricate_album_id_cache_dir_without_snapshot(
    tmp_path,
    monkeypatch,
):
    monkeypatch.delenv("BACKEND_PROTOCOL_SNAPSHOT_PATH", raising=False)
    registry = registry_module.PluginRegistry(search_root=str(tmp_path / "missing_third_party"))
    gateway = gateway_module.ProtocolGateway(registry=registry)
    monkeypatch.setattr(registry_module, "_registry_singleton", registry)
    monkeypatch.setattr(gateway_module, "_gateway_singleton", gateway)
    registry.refresh()

    data_dir = tmp_path / "data"
    meta_dir = data_dir / "meta_data"
    cache_root = data_dir / "recommendation_cache" / "comic"
    recommendations_json = meta_dir / "recommendations_database.json"
    _write_json(
        recommendations_json,
        {
            "recommendations": [
                {
                    "id": "PKmissing0001",
                    "author": "缺失作者",
                    "title": "缺失作品",
                    "storage_path_relative": "",
                    "storage_path_kind": "",
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

    resolved = manager._get_comic_cache_dir("PKmissing0001")

    assert resolved == ""


def test_file_parser_ignores_invalid_relative_path_and_falls_back_to_protocol_template(tmp_path, monkeypatch):
    _install_protocol_registry(monkeypatch, tmp_path / "third_party")
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


def test_comic_app_service_rebuilds_storage_path_from_protocol_template(tmp_path, monkeypatch):
    _install_protocol_registry(monkeypatch, tmp_path / "third_party")
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


def test_merge_host_video_display_uses_protocol_presentation_with_generic_default_fallback(tmp_path, monkeypatch):
    _install_protocol_registry(monkeypatch, tmp_path / "third_party")
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


def test_video_app_service_annotates_local_video_with_protocol_presentation_when_available(tmp_path, monkeypatch):
    _install_protocol_registry(monkeypatch, tmp_path / "third_party")
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


def test_video_app_service_annotates_local_video_with_generic_landscape_default_when_display_empty(monkeypatch, tmp_path):
    _install_protocol_registry(monkeypatch, tmp_path / "third_party")
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
