from __future__ import annotations

import os
from pathlib import Path

import pytest
import requests
from PIL import Image

from tests.shared.runtime_data import find_by_id, load_json, save_json


@pytest.mark.integration
def test_organize_options_returns_mode_specific_actions(integration_runtime):
    base_url = integration_runtime["base_url"]

    comic_resp = requests.get(
        f"{base_url}/api/v1/organize/options",
        params={"mode": "comic"},
        timeout=30,
    )
    assert comic_resp.status_code == 200
    comic_payload = comic_resp.json()
    assert comic_payload["code"] == 200
    comic_data = comic_payload["data"] or {}
    assert comic_data.get("mode") == "comic"

    action_map = {item.get("action"): item for item in (comic_data.get("options") or [])}
    assert {"repair_cover", "deduplicate_by_title", "enrich_local_metadata", "refresh_persisted_metadata"}.issubset(set(action_map))
    assert action_map["repair_cover"]["implemented"] is True
    assert action_map["deduplicate_by_title"]["implemented"] is True
    assert action_map["enrich_local_metadata"]["implemented"] is True
    assert action_map["refresh_persisted_metadata"]["implemented"] is True

    video_resp = requests.get(
        f"{base_url}/api/v1/organize/options",
        params={"mode": "video"},
        timeout=30,
    )
    assert video_resp.status_code == 200
    video_payload = video_resp.json()
    assert video_payload["code"] == 200
    video_data = video_payload["data"] or {}
    assert video_data.get("mode") == "video"
    video_action_map = {item.get("action"): item for item in (video_data.get("options") or [])}
    assert {"deduplicate_by_code", "enrich_local_metadata", "refresh_persisted_metadata"}.issubset(set(video_action_map))
    assert video_action_map["deduplicate_by_code"]["implemented"] is True
    assert video_action_map["enrich_local_metadata"]["implemented"] is True
    assert video_action_map["refresh_persisted_metadata"]["implemented"] is True


def _write_test_image(path: Path, size: tuple[int, int], color: tuple[int, int, int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, color).save(path, format="JPEG")


@pytest.mark.integration
def test_refresh_persisted_metadata_backfills_comic_relative_storage_path(integration_runtime):
    base_url = integration_runtime["base_url"]
    data_dir: Path = integration_runtime["data_dir"]
    meta_dir: Path = integration_runtime["meta_dir"]
    comics_path = meta_dir / "comics_database.json"

    original = load_json(comics_path)
    comic_dir = data_dir / "comic" / "JM" / "1436655"
    _write_test_image(comic_dir / "001.jpg", (90, 140), (220, 40, 40))

    try:
        save_json(
            comics_path,
            {
                "collection_name": "Test Comics",
                "user": "test-user",
                "total_comics": 1,
                "last_updated": "2026-05-08",
                "comics": [
                    {
                        "id": "JM1436655",
                        "title": "协议回填漫画",
                        "author": "作者A",
                        "cover_path": "/static/cover/JM/1436655.jpg",
                        "total_page": 1,
                        "current_page": 1,
                        "tag_ids": [],
                        "list_ids": [],
                        "is_deleted": False,
                    }
                ],
            },
        )

        response = requests.post(
            f"{base_url}/api/v1/organize/run",
            json={"mode": "comic", "action": "refresh_persisted_metadata"},
            timeout=60,
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["code"] == 200

        refreshed = load_json(comics_path).get("comics") or []
        record = find_by_id(refreshed, "JM1436655")
        assert record is not None
        assert record.get("storage_path_relative") == "comic/JM/1436655"
        assert record.get("storage_path_kind") == "local_dir"
    finally:
        save_json(comics_path, original)


@pytest.mark.integration
def test_refresh_persisted_metadata_backfills_video_display_and_relative_path(integration_runtime):
    base_url = integration_runtime["base_url"]
    data_dir: Path = integration_runtime["data_dir"]
    meta_dir: Path = integration_runtime["meta_dir"]
    videos_path = meta_dir / "videos_database.json"

    original = load_json(videos_path)
    source_file = data_dir / "video" / "JAVDB" / "BACKFILL001" / "source.mp4"
    source_file.parent.mkdir(parents=True, exist_ok=True)
    source_file.write_bytes(b"\x00\x00\x00\x18ftypmp42")
    local_source_file = data_dir / "video" / "LOCAL" / "BACKFILL_LOCAL" / "source.mp4"
    local_source_file.parent.mkdir(parents=True, exist_ok=True)
    local_source_file.write_bytes(b"\x00\x00\x00\x18ftypmp42")
    _write_test_image(data_dir / "static" / "cover" / "JAVDB" / "BACKFILL001.jpg", (160, 90), (40, 40, 220))

    try:
        save_json(
            videos_path,
            {
                "collection_name": "Test Videos",
                "user": "test-user",
                "total_videos": 2,
                "last_updated": "2026-05-08",
                "videos": [
                    {
                        "id": "JAVDBBACKFILL001",
                        "title": "协议回填视频",
                        "code": "ABP-123",
                        "cover_path": "/static/cover/JAVDB/BACKFILL001.jpg",
                        "local_video_path": "/media/video/JAVDB/BACKFILL001/source.mp4",
                        "local_source_path": str(source_file),
                        "preview_video": "",
                        "thumbnail_images": [],
                        "tag_ids": [],
                        "list_ids": [],
                        "create_time": "2026-05-08T00:00:00",
                        "last_access_time": "2026-05-08T00:00:00",
                        "is_deleted": False,
                    },
                    {
                        "id": "LOCALVBACKFILL001",
                        "title": "本地回填视频",
                        "code": "LOCAL-001",
                        "cover_path": "",
                        "local_video_path": "/media/video/LOCAL/BACKFILL_LOCAL/source.mp4",
                        "local_source_path": str(local_source_file),
                        "preview_video": "",
                        "thumbnail_images": [],
                        "tag_ids": [],
                        "list_ids": [],
                        "create_time": "2026-05-08T00:00:00",
                        "last_access_time": "2026-05-08T00:00:00",
                        "is_deleted": False,
                    },
                ],
            },
        )

        response = requests.post(
            f"{base_url}/api/v1/organize/run",
            json={"mode": "video", "action": "refresh_persisted_metadata"},
            timeout=60,
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["code"] == 200

        refreshed = load_json(videos_path).get("videos") or []
        record = find_by_id(refreshed, "JAVDBBACKFILL001")
        assert record is not None
        assert record.get("storage_path_relative") == "video/JAVDB/BACKFILL001/source.mp4"
        assert record.get("storage_path_kind") == "local_file"
        cover_display = ((record.get("display") or {}).get("cover") or {})
        assert cover_display.get("aspect_ratio") == "16 / 9"

        local_record = find_by_id(refreshed, "LOCALVBACKFILL001")
        assert local_record is not None
        assert local_record.get("storage_path_relative") == "video/LOCAL/BACKFILL_LOCAL/source.mp4"
        assert local_record.get("storage_path_kind") == "local_file"
        local_cover_display = ((local_record.get("display") or {}).get("cover") or {})
        assert local_cover_display.get("aspect_ratio") == "16 / 9"
        assert local_cover_display.get("mobile_aspect_ratio") == "16 / 9"
    finally:
        save_json(videos_path, original)


@pytest.mark.integration
def test_deduplicate_by_title_keeps_different_chapter_records(integration_runtime):
    base_url = integration_runtime["base_url"]
    meta_dir: Path = integration_runtime["meta_dir"]

    home_path = meta_dir / "comics_database.json"
    recommendation_path = meta_dir / "recommendations_database.json"

    original_home = load_json(home_path)
    original_recommendation = load_json(recommendation_path)

    try:
        home_data = {
            "collection_name": "Test Comics",
            "user": "test-user",
            "total_comics": 3,
            "last_updated": "2026-04-01",
            "comics": [
                {"id": "LOCAL_A", "title": "银河战士 [机翻] 第1话", "is_deleted": False},
                {"id": "LOCAL_B", "title": "银河战士【重置版】第1话", "is_deleted": False},
                {"id": "LOCAL_C", "title": "银河战士 第2话", "is_deleted": False},
            ],
        }
        recommendation_data = {
            "collection_name": "Test Comic Recommendations",
            "user": "test-user",
            "total_recommendations": 3,
            "last_updated": "2026-04-01",
            "recommendations": [
                {"id": "JM900001", "title": "预览样本 第1卷", "is_deleted": False},
                {"id": "JM900002", "title": "预览样本【修订】第1卷", "is_deleted": False},
                {"id": "JM900003", "title": "预览样本 第2卷", "is_deleted": False},
            ],
        }
        save_json(home_path, home_data)
        save_json(recommendation_path, recommendation_data)

        run_resp = requests.post(
            f"{base_url}/api/v1/organize/run",
            json={"mode": "comic", "action": "deduplicate_by_title"},
            timeout=60,
        )
        assert run_resp.status_code == 200
        run_payload = run_resp.json()
        assert run_payload["code"] == 200
        result = run_payload["data"] or {}
        assert (result.get("home") or {}).get("moved_to_trash") == 1
        assert (result.get("recommendation") or {}).get("moved_to_trash") == 1

        refreshed_home = load_json(home_path)
        refreshed_recommendation = load_json(recommendation_path)

        home_comics = refreshed_home.get("comics") or []
        recommendation_comics = refreshed_recommendation.get("recommendations") or []

        assert find_by_id(home_comics, "LOCAL_A")["is_deleted"] is False
        assert find_by_id(home_comics, "LOCAL_B")["is_deleted"] is True
        assert find_by_id(home_comics, "LOCAL_C")["is_deleted"] is False

        assert find_by_id(recommendation_comics, "JM900001")["is_deleted"] is False
        assert find_by_id(recommendation_comics, "JM900002")["is_deleted"] is True
        assert find_by_id(recommendation_comics, "JM900003")["is_deleted"] is False
    finally:
        save_json(home_path, original_home)
        save_json(recommendation_path, original_recommendation)


@pytest.mark.integration
def test_video_deduplicate_by_code_moves_duplicates_to_trash(integration_runtime):
    base_url = integration_runtime["base_url"]
    meta_dir: Path = integration_runtime["meta_dir"]

    home_path = meta_dir / "videos_database.json"
    recommendation_path = meta_dir / "video_recommendations_database.json"

    original_home = load_json(home_path)
    original_recommendation = load_json(recommendation_path)

    try:
        home_data = {
            "collection_name": "Test Videos",
            "user": "test-user",
            "total_videos": 4,
            "last_updated": "2026-04-01",
            "videos": [
                {"id": "LOCALV_A", "code": "ABP-123", "title": "A", "is_deleted": False},
                {"id": "LOCALV_B", "code": "abp_123", "title": "B", "is_deleted": False},
                {"id": "LOCALV_C", "code": "FC2-PPV-123456", "title": "C", "is_deleted": False},
                {"id": "LOCALV_D", "code": "FC2PPV123456", "title": "D", "is_deleted": False},
            ],
        }
        recommendation_data = {
            "collection_name": "Test Video Recommendations",
            "user": "test-user",
            "total_video_recommendations": 3,
            "last_updated": "2026-04-01",
            "video_recommendations": [
                {"id": "JAVDB_A", "code": "IPX-001", "title": "A", "is_deleted": False},
                {"id": "JAVDB_B", "code": "ipx001", "title": "B", "is_deleted": False},
                {"id": "JAVBUS_C", "code": "SSIS-777", "title": "C", "is_deleted": False},
            ],
        }
        save_json(home_path, home_data)
        save_json(recommendation_path, recommendation_data)

        run_resp = requests.post(
            f"{base_url}/api/v1/organize/run",
            json={"mode": "video", "action": "deduplicate_by_code"},
            timeout=60,
        )
        assert run_resp.status_code == 200
        run_payload = run_resp.json()
        assert run_payload["code"] == 200
        result = run_payload["data"] or {}
        assert (result.get("home") or {}).get("moved_to_trash") == 2
        assert (result.get("recommendation") or {}).get("moved_to_trash") == 1

        refreshed_home = load_json(home_path).get("videos") or []
        refreshed_recommendation = load_json(recommendation_path).get("video_recommendations") or []

        assert find_by_id(refreshed_home, "LOCALV_A")["is_deleted"] is False
        assert find_by_id(refreshed_home, "LOCALV_B")["is_deleted"] is True
        assert find_by_id(refreshed_home, "LOCALV_C")["is_deleted"] is False
        assert find_by_id(refreshed_home, "LOCALV_D")["is_deleted"] is True

        assert find_by_id(refreshed_recommendation, "JAVDB_A")["is_deleted"] is False
        assert find_by_id(refreshed_recommendation, "JAVDB_B")["is_deleted"] is True
        assert find_by_id(refreshed_recommendation, "JAVBUS_C")["is_deleted"] is False
    finally:
        save_json(home_path, original_home)
        save_json(recommendation_path, original_recommendation)


@pytest.mark.integration
def test_video_local_import_from_path_supports_recursive_scan_and_code_extract(integration_runtime):
    base_url = integration_runtime["base_url"]
    runtime_root: Path = integration_runtime["runtime_root"]
    data_dir: Path = integration_runtime["data_dir"]
    meta_dir: Path = integration_runtime["meta_dir"]
    videos_path = meta_dir / "videos_database.json"

    original_videos = load_json(videos_path)

    source_root = runtime_root / "video_local_import_source"
    dir_a = source_root / "dir_a"
    dir_b = source_root / "dir_b"
    dir_c = source_root / "dir_c"
    dir_d = source_root / "dir_d"
    for d in (dir_a, dir_b, dir_c, dir_d):
        d.mkdir(parents=True, exist_ok=True)

    (dir_a / "ABP-123 demo.mp4").write_bytes(b"\x00\x00\x00\x18ftypmp42")
    (dir_b / "fc2_ppv_123456 clip.mkv").write_bytes(b"\x1A\x45\xDF\xA3")
    (dir_c / "XYZ999 trailer.avi").write_bytes(b"RIFF")
    (dir_d / "no_code_sample.webm").write_bytes(b"\x1A\x45\xDF\xA3")
    (source_root / "archive.zip").write_bytes(b"PK\x03\x04")
    (source_root / "readme.txt").write_text("ignore", encoding="utf-8")

    try:
        response = requests.post(
            f"{base_url}/api/v1/video/local-import/from-path",
            json={"source_path": str(source_root), "import_mode": "hardlink_move"},
            timeout=90,
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["code"] == 200

        data = payload["data"] or {}
        assert data.get("imported_count") == 4
        assert data.get("import_mode") == "hardlink_move"
        assert data.get("scanned_video_files") == 4
        assert data.get("skipped_count", 0) >= 1
        imported_ids = data.get("imported_ids") or []
        assert len(imported_ids) == 4

        refreshed_videos = load_json(videos_path).get("videos") or []
        imported_records = [item for item in refreshed_videos if item.get("id") in imported_ids]
        assert len(imported_records) == 4

        imported_codes = {str(item.get("code") or "") for item in imported_records}
        assert "ABP-123" in imported_codes
        assert "FC2-PPV-123456" in imported_codes
        assert "XYZ-999" in imported_codes
        assert any(code.startswith("LOCALERR_") for code in imported_codes)

        for item in imported_records:
            local_video_path = str(item.get("local_video_path") or "")
            assert local_video_path.startswith("/media/video/LOCAL/")
            relative_parts = local_video_path[len("/media/video/LOCAL/"):].split("/")
            assert len(relative_parts) == 2
            storage_dir_name, source_filename = relative_parts
            assert source_filename
            assert source_filename != f"source{Path(source_filename).suffix}"
            assert str(item.get("local_asset_dir_name") or "") == storage_dir_name
            assert str(item.get("local_source_filename") or "") == source_filename
            rel = local_video_path[len("/media/"):].replace("/", os.sep)
            abs_path = data_dir / rel
            assert abs_path.exists(), f"missing imported file: {abs_path}"

        assert not (dir_a / "ABP-123 demo.mp4").exists()
        assert not (dir_b / "fc2_ppv_123456 clip.mkv").exists()
        assert not (dir_c / "XYZ999 trailer.avi").exists()
        assert not (dir_d / "no_code_sample.webm").exists()
    finally:
        save_json(videos_path, original_videos)


@pytest.mark.integration
def test_video_local_import_softlink_mode_keeps_source_and_streams_from_local_source(integration_runtime):
    base_url = integration_runtime["base_url"]
    runtime_root: Path = integration_runtime["runtime_root"]
    meta_dir: Path = integration_runtime["meta_dir"]
    videos_path = meta_dir / "videos_database.json"

    original_videos = load_json(videos_path)

    source_root = runtime_root / "video_local_import_source_softlink"
    nested = source_root / "nested"
    nested.mkdir(parents=True, exist_ok=True)

    first_file = source_root / "SOFT-321 sample.mp4"
    second_file = nested / "fc2_ppv_765432 sample.mkv"
    first_file.write_bytes(b"\x00\x00\x00\x18ftypmp42")
    second_file.write_bytes(b"\x1A\x45\xDF\xA3")

    try:
        response = requests.post(
            f"{base_url}/api/v1/video/local-import/from-path",
            json={"source_path": str(source_root), "import_mode": "softlink_ref"},
            timeout=90,
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["code"] == 200

        data = payload["data"] or {}
        assert data.get("import_mode") == "softlink_ref"
        assert data.get("imported_count") == 2

        imported_ids = data.get("imported_ids") or []
        assert len(imported_ids) == 2

        refreshed_videos = load_json(videos_path).get("videos") or []
        imported_records = [item for item in refreshed_videos if item.get("id") in imported_ids]
        assert len(imported_records) == 2

        for item in imported_records:
            local_video_path = str(item.get("local_video_path") or "")
            local_source_path = str(item.get("local_source_path") or "")
            assert local_video_path.startswith("/api/v1/video/local-stream/")
            assert local_source_path
            assert os.path.isfile(local_source_path)

            stream_resp = requests.get(
                f"{base_url}{local_video_path}",
                timeout=30,
            )
            assert stream_resp.status_code == 200
            assert stream_resp.content

        assert first_file.exists()
        assert second_file.exists()
    finally:
        save_json(videos_path, original_videos)


@pytest.mark.integration
def test_video_local_import_duplicate_local_record_skips(integration_runtime):
    base_url = integration_runtime["base_url"]
    runtime_root: Path = integration_runtime["runtime_root"]
    meta_dir: Path = integration_runtime["meta_dir"]
    videos_path = meta_dir / "videos_database.json"

    original_videos = load_json(videos_path)
    source_root = runtime_root / "video_local_import_duplicate_local"
    source_root.mkdir(parents=True, exist_ok=True)
    incoming_file = source_root / "ABP-123 sample.mp4"
    incoming_file.write_bytes(b"\x00\x00\x00\x18ftypmp42")

    try:
        save_json(
            videos_path,
            {
                "collection_name": "Test Videos",
                "user": "test-user",
                "total_videos": 1,
                "last_updated": "2026-04-01",
                "videos": [
                    {
                        "id": "LOCALV_DUP_001",
                        "code": "abp_123",
                        "title": "existing local",
                        "local_video_path": "/api/v1/video/local-stream/LOCALV_DUP_001",
                        "local_source_path": "",
                        "is_deleted": False,
                    }
                ],
            },
        )

        response = requests.post(
            f"{base_url}/api/v1/video/local-import/from-path",
            json={"source_path": str(source_root), "import_mode": "hardlink_move"},
            timeout=90,
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["code"] == 200
        data = payload["data"] or {}
        assert data.get("imported_count") == 0
        assert data.get("skipped_count") == 1
        skipped_items = data.get("skipped_items") or []
        assert skipped_items
        assert skipped_items[0].get("reason") == "duplicate_local_import"
        assert skipped_items[0].get("duplicate_id") == "LOCALV_DUP_001"
        assert incoming_file.exists()
    finally:
        save_json(videos_path, original_videos)


@pytest.mark.integration
def test_video_local_import_duplicate_non_local_without_source_attaches_source(integration_runtime):
    base_url = integration_runtime["base_url"]
    runtime_root: Path = integration_runtime["runtime_root"]
    data_dir: Path = integration_runtime["data_dir"]
    meta_dir: Path = integration_runtime["meta_dir"]
    videos_path = meta_dir / "videos_database.json"

    original_videos = load_json(videos_path)
    source_root = runtime_root / "video_local_import_attach_source"
    source_root.mkdir(parents=True, exist_ok=True)
    incoming_file = source_root / "abp 123 from_local.mp4"
    incoming_file.write_bytes(b"\x00\x00\x00\x18ftypmp42")

    try:
        save_json(
            videos_path,
            {
                "collection_name": "Test Videos",
                "user": "test-user",
                "total_videos": 1,
                "last_updated": "2026-04-01",
                "videos": [
                    {
                        "id": "JAVDB900001",
                        "code": "ABP_123",
                        "title": "remote only",
                        "local_video_path": "",
                        "local_source_path": "",
                        "is_deleted": False,
                    }
                ],
            },
        )

        response = requests.post(
            f"{base_url}/api/v1/video/local-import/from-path",
            json={"source_path": str(source_root), "import_mode": "hardlink_move"},
            timeout=90,
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["code"] == 200
        data = payload["data"] or {}
        assert data.get("imported_count") == 1
        assert data.get("attached_source_count") == 1
        assert data.get("imported_ids") == ["JAVDB900001"]

        refreshed = load_json(videos_path).get("videos") or []
        assert len(refreshed) == 1
        record = find_by_id(refreshed, "JAVDB900001")
        assert record is not None
        assert str(record.get("local_video_path") or "").startswith("/media/video/JAVDB/abp 123 from_local/abp 123 from_local.")
        assert str(record.get("local_source_path") or "").endswith(
            os.path.join("video", "JAVDB", "abp 123 from_local", "abp 123 from_local.mp4")
        )
        assert record.get("local_asset_dir_name") == "abp 123 from_local"
        assert record.get("local_source_filename") == "abp 123 from_local.mp4"
        assert record.get("source_origin") == "local_import"
        assert str(record.get("source_updated_time") or "").strip()

        media_rel = str(record.get("local_video_path") or "")[len("/media/"):].replace("/", os.sep)
        assert (data_dir / media_rel).exists()
        assert not incoming_file.exists()
    finally:
        save_json(videos_path, original_videos)


@pytest.mark.integration
def test_video_local_import_duplicate_non_local_with_source_skips(integration_runtime):
    base_url = integration_runtime["base_url"]
    runtime_root: Path = integration_runtime["runtime_root"]
    data_dir: Path = integration_runtime["data_dir"]
    meta_dir: Path = integration_runtime["meta_dir"]
    videos_path = meta_dir / "videos_database.json"

    original_videos = load_json(videos_path)
    source_root = runtime_root / "video_local_import_skip_existing_source"
    source_root.mkdir(parents=True, exist_ok=True)
    incoming_file = source_root / "ABP123 another.mp4"
    incoming_file.write_bytes(b"\x00\x00\x00\x18ftypmp42")

    existing_source_rel = "video/JAVDB/JAVDB900001/source.mp4"
    existing_source_abs = data_dir / existing_source_rel.replace("/", os.sep)
    existing_source_abs.parent.mkdir(parents=True, exist_ok=True)
    existing_source_abs.write_bytes(b"\x00\x00\x00\x18ftypmp42")

    try:
        save_json(
            videos_path,
            {
                "collection_name": "Test Videos",
                "user": "test-user",
                "total_videos": 1,
                "last_updated": "2026-04-01",
                "videos": [
                    {
                        "id": "JAVDB900001",
                        "code": "ABP-123",
                        "title": "remote with source",
                        "local_video_path": "/media/video/JAVDB/JAVDB900001/source.mp4",
                        "local_source_path": str(existing_source_abs),
                        "source_origin": "magnet_download",
                        "is_deleted": False,
                    }
                ],
            },
        )

        response = requests.post(
            f"{base_url}/api/v1/video/local-import/from-path",
            json={"source_path": str(source_root), "import_mode": "hardlink_move"},
            timeout=90,
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["code"] == 200
        data = payload["data"] or {}
        assert data.get("imported_count") == 0
        assert data.get("skipped_count") == 1
        skipped_items = data.get("skipped_items") or []
        assert skipped_items
        assert skipped_items[0].get("reason") == "duplicate_code_source_exists"
        assert skipped_items[0].get("duplicate_id") == "JAVDB900001"
        assert incoming_file.exists()
    finally:
        save_json(videos_path, original_videos)
