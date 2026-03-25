from __future__ import annotations

import os

import pytest

from tests.shared.runtime_data import load_json, save_json


@pytest.mark.integration
def test_video_migrate_to_local_prefers_preview_cache_and_rewrites_local_asset_paths(third_party_client, monkeypatch):
    """
    Case Description:
    - Purpose: Guard video preview->local migrate cache behavior. When preview cache exists, assets must be copied
      into local video directory and local-field URLs must be rewritten from preview path to local path.
    - Steps:
      1. Seed preview recommendation with preview-local asset URLs and create cached files in preview cache dir.
      2. Run `VideoAppService.migrate_recommendations_to_local`.
      3. Assert copied files exist in local dir and persisted local URLs point to `/media/video/...`.
    - Expected:
      1. migrate succeeds with imported_count=1.
      2. `preview_video_local/thumbnail_images_local/cover_path_local` are rewritten to local paths.
      3. Fallback async cache download is not triggered.
    """
    video_service_module = third_party_client["video_service_module"]
    service = video_service_module.VideoAppService()
    meta_dir = third_party_client["meta_dir"]

    video_id = "JAVDB_CACHE001"
    video_code = "CACHE-001"

    preview_dir, _, preview_prefix, local_prefix = service._build_preview_asset_prefixes(video_id)
    thumbs_dir = os.path.join(preview_dir, "thumbs")
    os.makedirs(thumbs_dir, exist_ok=True)

    preview_cover_rel = f"{preview_prefix}cover.jpg"
    preview_thumb_rel = f"{preview_prefix}thumbs/thumb-0001.jpg"
    preview_video_rel = f"{preview_prefix}preview.mp4"

    with open(os.path.join(preview_dir, "cover.jpg"), "wb") as f:
        f.write(b"cover-bytes")
    with open(os.path.join(thumbs_dir, "thumb-0001.jpg"), "wb") as f:
        f.write(b"thumb-bytes")
    with open(os.path.join(preview_dir, "preview.mp4"), "wb") as f:
        f.write(b"video-bytes")

    recommendation_db_path = meta_dir / "video_recommendations_database.json"
    recommendation_db = load_json(recommendation_db_path)
    recommendation_items = [
        item
        for item in recommendation_db.get("video_recommendations", [])
        if str((item or {}).get("id", "")) != video_id
    ]
    recommendation_items.append(
        {
            "id": video_id,
            "title": "cached migrate video",
            "title_jp": "",
            "creator": "tester",
            "desc": "",
            "cover_path": "https://remote.example/cover.jpg",
            "total_units": 1,
            "current_unit": 1,
            "score": 8.0,
            "tag_ids": [],
            "list_ids": [],
            "create_time": "2026-03-25T00:00:00",
            "last_access_time": "2026-03-25T00:00:00",
            "is_deleted": False,
            "content_type": "video",
            "code": video_code,
            "date": "2025-01-01",
            "series": "",
            "magnets": [],
            "thumbnail_images": ["https://remote.example/thumb.jpg"],
            "preview_video": "https://remote.example/preview.mp4",
            "cover_path_local": preview_cover_rel,
            "thumbnail_images_local": [preview_thumb_rel],
            "preview_video_local": preview_video_rel,
            "actors": ["actor"],
        }
    )
    recommendation_db["video_recommendations"] = recommendation_items
    save_json(recommendation_db_path, recommendation_db)

    local_video_db_path = meta_dir / "videos_database.json"
    local_video_db = load_json(local_video_db_path)
    local_video_db["videos"] = [
        item
        for item in local_video_db.get("videos", [])
        if str((item or {}).get("id", "")) != video_id
        and str((item or {}).get("code", "")).upper() != video_code.upper()
    ]
    save_json(local_video_db_path, local_video_db)

    calls = {"cover": 0, "thumb": 0, "preview": 0}

    def _mark(name):
        calls[name] += 1

    monkeypatch.setattr(service, "cache_cover_to_static_async", lambda *args, **kwargs: _mark("cover"))
    monkeypatch.setattr(service, "cache_thumbnail_images_async", lambda *args, **kwargs: _mark("thumb"))
    monkeypatch.setattr(service, "cache_preview_video_async", lambda *args, **kwargs: _mark("preview"))

    result = service.migrate_recommendations_to_local([video_id])
    assert result.success
    assert result.data["imported_count"] == 1

    local_video = service._video_repo.get_by_id(video_id)
    assert local_video is not None
    assert local_video.cover_path_local == f"{local_prefix}cover.jpg"
    assert local_video.thumbnail_images_local == [f"{local_prefix}thumbs/thumb-0001.jpg"]
    assert local_video.preview_video_local == f"{local_prefix}preview.mp4"

    for url in [
        local_video.cover_path_local,
        local_video.thumbnail_images_local[0],
        local_video.preview_video_local,
    ]:
        abs_path = service._resolve_static_asset_abs_path(url)
        assert abs_path and os.path.exists(abs_path)

    assert calls == {"cover": 0, "thumb": 0, "preview": 0}
