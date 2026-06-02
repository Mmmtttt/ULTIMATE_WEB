from __future__ import annotations

import os
from io import BytesIO
from types import SimpleNamespace

import pytest
from PIL import Image

from tests.shared.runtime_data import load_json, save_json


class _FakeResponse:
    def __init__(self, chunks=None, status_code=206, headers=None):
        self._chunks = chunks or [b"video-bytes"]
        self.status_code = status_code
        self.headers = headers or {
            "Content-Type": "video/mp4",
            "Content-Range": "bytes 0-10/100",
            "Accept-Ranges": "bytes",
            "X-Ignored": "1",
        }
        self.closed = False

    def iter_content(self, chunk_size=1):
        for chunk in self._chunks:
            yield chunk

    def close(self):
        self.closed = True


def _png_bytes(color: str) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (12, 8), color).save(buffer, format="PNG")
    return buffer.getvalue()


@pytest.mark.integration
def test_teledrive_config_public_serialization_hides_token(third_party_client):
    from application.teledrive_app_service import TeleDriveProtocolProvider

    provider = TeleDriveProtocolProvider(manifest={}, manifest_path="")

    normalized = provider.normalize_config(
        {
            "enabled": "true",
            "bridge_base_url": "http://127.0.0.1:8892/",
            "api_token": "secret-token",
            "default_limit": "25",
            "convert_photos": "false",
        }
    )
    public = provider.serialize_public_config(normalized)

    assert normalized["bridge_base_url"] == "http://127.0.0.1:8892"
    assert normalized["api_token"] == "secret-token"
    assert normalized["default_limit"] == 25
    assert normalized["convert_photos"] is False
    assert "api_token" not in public
    assert public["api_token_configured"] is True


@pytest.mark.integration
def test_teledrive_import_and_catalog_routes_call_service(third_party_client, monkeypatch):
    client = third_party_client["client"]
    import api.v1.teledrive as teledrive_api

    calls = []

    class FakeService:
        def get_status(self):
            return {
                "enabled": True,
                "configured": True,
                "bridge_health": {"ok": True},
                "latest_import": {"last_result": {"imported": 2}},
            }

        def import_once(self, payload, dry_run):
            calls.append({"payload": payload, "dry_run": dry_run})
            return {"result": {"dry_run": dry_run, "imported": 1, "files": []}}

        def get_catalog(self, args):
            calls.append({"catalog_args": args})
            return {"items": [{"id": "file-1", "kind": "image"}], "count": 1}

        def get_tree(self, root, *, limit):
            calls.append({"tree_root": root, "tree_limit": limit})
            return {"root": root, "items": [{"id": "folder-1", "type": "folder"}], "count": 1}

        def sync_library(self, payload, dry_run):
            calls.append({"sync_payload": payload, "sync_dry_run": dry_run})
            return {"dry_run": dry_run, "stats": {"recognized_comics": 1, "recognized_videos": 0}}

    monkeypatch.setattr(teledrive_api, "get_teledrive_app_service", lambda: FakeService())

    status_response = client.get("/api/v1/teledrive/status")
    preview_response = client.post("/api/v1/teledrive/imports/preview", json={"limit": 10})
    import_response = client.post("/api/v1/teledrive/imports", json={"limit": 5, "convert_photos": False})
    catalog_response = client.get("/api/v1/teledrive/catalog?limit=3")
    tree_response = client.get("/api/v1/teledrive/tree?root=/comic&limit=20")
    sync_preview_response = client.post("/api/v1/teledrive/library-sync/preview", json={"limit": 20})
    sync_response = client.post("/api/v1/teledrive/library-sync", json={"limit": 20})

    assert status_response.status_code == 200
    assert status_response.get_json()["data"]["bridge_health"]["ok"] is True
    assert preview_response.get_json()["data"]["result"]["dry_run"] is True
    assert import_response.get_json()["data"]["result"]["dry_run"] is False
    assert catalog_response.get_json()["data"]["items"][0]["id"] == "file-1"
    assert tree_response.get_json()["data"]["root"] == "/comic"
    assert sync_preview_response.get_json()["data"]["dry_run"] is True
    assert sync_response.get_json()["data"]["dry_run"] is False
    assert calls[0] == {"payload": {"limit": 10}, "dry_run": True}
    assert calls[1] == {"payload": {"convert_photos": False, "limit": 5}, "dry_run": False}
    assert calls[2] == {"catalog_args": {"limit": "3"}}
    assert calls[3] == {"tree_root": "/comic", "tree_limit": 20}
    assert calls[4] == {"sync_payload": {"limit": 20}, "sync_dry_run": True}
    assert calls[5] == {"sync_payload": {"limit": 20}, "sync_dry_run": False}


@pytest.mark.integration
def test_teledrive_directory_recognizer_uses_fixed_comic_and_video_roots(third_party_client):
    from application.teledrive_app_service import TeleDriveAppService

    service = TeleDriveAppService()
    skipped = []

    comic_items = [
        {"id": "comic-root", "type": "folder", "name": "comic", "path": "/comic"},
        {"id": "jm-root", "type": "folder", "name": "JM", "path": "/comic/JM"},
        {"id": "work-1", "type": "folder", "name": "86233", "path": "/comic/JM/86233"},
        {"id": "chapter-1", "type": "folder", "name": "1", "path": "/comic/JM/86233/1"},
        {"id": "page-2", "type": "file", "name": "002.jpg", "path": "/comic/JM/86233/1/002.jpg", "mime_type": "image/jpeg"},
        {"id": "page-1", "type": "file", "name": "001.jpg", "path": "/comic/JM/86233/1/001.jpg", "mime_type": "image/jpeg"},
        {"id": "loose-root", "type": "folder", "name": "MYBOOK", "path": "/comic/MYBOOK"},
        {"id": "loose-page", "type": "file", "name": "001.png", "path": "/comic/MYBOOK/001.png", "mime_type": "image/png"},
        {"id": "skip-zip", "type": "file", "name": "book.zip", "path": "/comic/MYBOOK/book.zip", "mime_type": "application/zip"},
    ]
    comics = service._recognize_comics(comic_items, skipped)

    assert [comic["title"] for comic in comics] == ["86233", "MYBOOK"]
    assert comics[0]["author"] == "JM"
    assert comics[0]["total_page"] == 2
    assert comics[0]["display"]["teledrive"]["pages"][0]["name"] == "001.jpg"
    assert any(item["reason"] == "unsupported_comic_file" for item in skipped)

    video_items = [
        {"id": "video-root", "type": "folder", "name": "video", "path": "/video"},
        {"id": "movie-root", "type": "folder", "name": "movie-a", "path": "/video/movie-a"},
        {"id": "thumb-root", "type": "folder", "name": "thumbs", "path": "/video/movie-a/thumbs"},
        {"id": "cover", "type": "file", "name": "cover.jpg", "path": "/video/movie-a/cover.jpg", "mime_type": "image/jpeg"},
        {"id": "thumb-2", "type": "file", "name": "002.jpg", "path": "/video/movie-a/thumbs/002.jpg", "mime_type": "image/jpeg"},
        {"id": "thumb-1", "type": "file", "name": "001.jpg", "path": "/video/movie-a/thumbs/001.jpg", "mime_type": "image/jpeg"},
        {"id": "ep2", "type": "file", "name": "02.mp4", "path": "/video/movie-a/02.mp4", "mime_type": "video/mp4"},
        {"id": "ep1", "type": "file", "name": "01.mp4", "path": "/video/movie-a/01.mp4", "mime_type": "video/mp4"},
    ]
    videos = service._recognize_videos(video_items, skipped)

    assert len(videos) == 1
    assert videos[0]["title"] == "movie-a"
    assert videos[0]["total_units"] == 2
    assert videos[0]["preview_video"].endswith("name=01.mp4")
    assert videos[0]["cover_path"].endswith("name=cover.jpg")
    assert len(videos[0]["thumbnail_images"]) == 2
    assert videos[0]["thumbnail_images"][0].endswith("name=001.jpg")
    assert videos[0]["display"]["teledrive"]["thumbnails"][0]["name"] == "001.jpg"


@pytest.mark.integration
def test_teledrive_sync_library_downloads_preview_covers_locally(third_party_client, monkeypatch):
    from application.teledrive_app_service import TeleDriveAppService

    service = TeleDriveAppService()
    comic_id = "TD-COMIC-folder-cover"
    video_id = "TD-VIDEO-folder-cover"

    scan_payload = {
        "comics": [
            {
                "id": comic_id,
                "title": "TeleDrive Comic Cover",
                "title_jp": "",
                "author": "JM",
                "desc": "TeleDrive: /comic/JM/cover-demo",
                "cover_path": f"/api/v1/comic/image?comic_id={comic_id}&page_num=1",
                "total_page": 2,
                "current_page": 1,
                "score": 8.0,
                "tag_ids": [],
                "list_ids": [],
                "create_time": "2026-06-02T00:00:00",
                "last_read_time": "2026-06-02T00:00:00",
                "is_deleted": False,
                "preview_image_urls": [
                    f"/api/v1/comic/image?comic_id={comic_id}&page_num=1",
                    f"/api/v1/comic/image?comic_id={comic_id}&page_num=2",
                ],
                "preview_pages": [1, 2],
                "platform": "TeleDrive",
                "plugin_id": "storage.teledrive",
                "plugin_name": "TeleDrive",
                "storage_path_relative": "teledrive://folder/folder-cover",
                "storage_path_kind": "teledrive_dir",
                "display": {
                    "teledrive": {
                        "type": "comic",
                        "root": "/comic",
                        "path": "/comic/JM/cover-demo",
                        "folder_id": "folder-cover",
                        "work_id": "cover-demo",
                        "platform_segment": "JM",
                        "pages": [
                            {"file_id": "page-1", "name": "001.png", "relative_path": "1/001.png"},
                            {"file_id": "page-2", "name": "002.png", "relative_path": "1/002.png"},
                        ],
                    }
                },
                "source_missing": False,
            }
        ],
        "videos": [
            {
                "id": video_id,
                "title": "TeleDrive Video Cover",
                "title_jp": "",
                "creator": "",
                "desc": "TeleDrive: /video/cover-demo",
                "cover_path": "",
                "total_units": 1,
                "current_unit": 1,
                "score": 8.0,
                "tag_ids": [],
                "list_ids": [],
                "create_time": "2026-06-02T00:00:00",
                "last_access_time": "2026-06-02T00:00:00",
                "is_deleted": False,
                "platform": "TeleDrive",
                "plugin_id": "storage.teledrive",
                "plugin_name": "TeleDrive",
                "storage_path_relative": "teledrive://folder/folder-video-cover",
                "storage_path_kind": "teledrive_dir",
                "code": "td-cover-video",
                "date": "",
                "series": "",
                "magnets": [],
                "thumbnail_images": ["/api/v1/teledrive/files/thumb-1/content?name=001.png"],
                "preview_video": "/api/v1/teledrive/files/ep-1/content?name=01.mp4",
                "cover_path_local": "",
                "thumbnail_images_local": [],
                "preview_video_local": "",
                "actor_refs": [],
                "actors": [],
                "display": {
                    "teledrive": {
                        "type": "video",
                        "root": "/video",
                        "path": "/video/cover-demo",
                        "folder_id": "folder-video-cover",
                        "work_id": "cover-demo",
                        "platform_segment": "",
                        "episodes": [
                            {"file_id": "ep-1", "name": "01.mp4", "relative_path": "01.mp4"},
                        ],
                        "cover": {},
                        "thumbnails": [
                            {"file_id": "thumb-1", "name": "001.png", "relative_path": "thumbs/001.png"},
                        ],
                    }
                },
                "source_missing": False,
            }
        ],
        "skipped": [],
    }

    monkeypatch.setattr(service, "_scan_library", lambda *, limit: scan_payload)

    binary_payloads = {
        "page-1": _png_bytes("#ff6b6b"),
        "thumb-1": _png_bytes("#4dabf7"),
    }

    def fake_download(file_id, target_path, *, name="", progress_callback=None):
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        with open(target_path, "wb") as file_obj:
            file_obj.write(binary_payloads[file_id])
        if progress_callback:
            progress_callback(
                {
                    "bytes_written": os.path.getsize(target_path),
                    "total_bytes": os.path.getsize(target_path),
                    "force": True,
                }
            )
        return {"path": target_path, "bytes": os.path.getsize(target_path)}

    monkeypatch.setattr(service, "download_file_to_path", fake_download)

    result = service.sync_library({"limit": 50}, dry_run=False)

    assert result["stats"]["comic_added"] == 1
    assert result["stats"]["video_added"] == 1
    assert result["stats"]["comic_cover_cached"] == 1
    assert result["stats"]["video_cover_cached"] == 1

    meta_dir = third_party_client["meta_dir"]
    data_dir = third_party_client["data_dir"]

    recommendation_db = load_json(meta_dir / "recommendations_database.json")
    recommendation = next(item for item in recommendation_db["recommendations"] if item["id"] == comic_id)
    assert recommendation["cover_path"] == f"/static/cover/TeleDrive/{comic_id}.jpg"
    comic_cover_path = data_dir / "static" / "cover" / "TeleDrive" / f"{comic_id}.jpg"
    assert comic_cover_path.is_file()

    video_db = load_json(meta_dir / "video_recommendations_database.json")
    video = next(item for item in video_db["video_recommendations"] if item["id"] == video_id)
    assert str(video["cover_path_local"]).startswith("/media/recommendation_cache/video/TeleDrive/")
    relative_video_cover = str(video["cover_path_local"]).removeprefix("/media/").replace("/", os.sep)
    video_cover_path = data_dir / relative_video_cover
    assert video_cover_path.is_file()


@pytest.mark.integration
def test_teledrive_file_proxy_preserves_range_and_stream_headers(third_party_client, monkeypatch):
    client = third_party_client["client"]
    import api.v1.teledrive as teledrive_api
    from application.teledrive_app_service import TeleDriveAppService

    captured = {}
    fake_response = _FakeResponse()

    class FakeService:
        STREAM_RESPONSE_HEADERS = TeleDriveAppService.STREAM_RESPONSE_HEADERS
        filter_headers = staticmethod(TeleDriveAppService.filter_headers)

        def proxy_file_content(self, file_id, *, method, query_string="", incoming_headers=None):
            captured["file_id"] = file_id
            captured["method"] = method
            captured["query_string"] = query_string
            captured["range"] = incoming_headers.get("Range")
            return fake_response

        def close_response(self, response):
            response.close()

    monkeypatch.setattr(teledrive_api, "get_teledrive_app_service", lambda: FakeService())

    response = client.get(
        "/api/v1/teledrive/files/abc/content?name=movie.mp4",
        headers={"Range": "bytes=0-10"},
    )

    assert response.status_code == 206
    assert response.data == b"video-bytes"
    assert response.headers["Content-Type"] == "video/mp4"
    assert response.headers["Content-Range"] == "bytes 0-10/100"
    assert response.headers["Accept-Ranges"] == "bytes"
    assert "X-Ignored" not in response.headers
    assert fake_response.closed is True
    assert captured == {
        "file_id": "abc",
        "method": "GET",
        "query_string": "name=movie.mp4",
        "range": "bytes=0-10",
    }


@pytest.mark.integration
def test_teledrive_file_proxy_bridge_error_uses_http_status(third_party_client, monkeypatch):
    client = third_party_client["client"]
    import api.v1.teledrive as teledrive_api
    from application.teledrive_app_service import TeleDriveAppService, TeleDriveBridgeError

    class FakeService:
        STREAM_RESPONSE_HEADERS = TeleDriveAppService.STREAM_RESPONSE_HEADERS
        filter_headers = staticmethod(TeleDriveAppService.filter_headers)

        def proxy_file_content(self, *_args, **_kwargs):
            raise TeleDriveBridgeError("bridge down", status_code=502)

        def close_response(self, _response):
            pass

    monkeypatch.setattr(teledrive_api, "get_teledrive_app_service", lambda: FakeService())

    response = client.get("/api/v1/teledrive/files/abc/content")

    assert response.status_code == 502
    assert b"bridge down" in response.data


@pytest.mark.integration
def test_teledrive_recommendation_cache_routes_stream_remote_pages(third_party_client, monkeypatch):
    client = third_party_client["client"]
    import api.v1.recommendation as recommendation_api
    from application.teledrive_app_service import TeleDriveAppService

    fake_response = _FakeResponse(chunks=[b"image-bytes"], status_code=200, headers={"Content-Type": "image/jpeg"})

    class FakeService:
        STREAM_RESPONSE_HEADERS = TeleDriveAppService.STREAM_RESPONSE_HEADERS
        filter_headers = staticmethod(TeleDriveAppService.filter_headers)

        def get_teledrive_comic_pages(self, recommendation_id):
            assert recommendation_id == "TD-COMIC-folder-1"
            return [{"file_id": "page-1", "name": "001.jpg"}, {"file_id": "page-2", "name": "002.jpg"}]

        def proxy_teledrive_comic_page(self, recommendation_id, page_num, *, method="GET", incoming_headers=None):
            assert recommendation_id == "TD-COMIC-folder-1"
            assert page_num == 1
            assert method == "GET"
            return fake_response

        def close_response(self, response):
            response.close()

    monkeypatch.setattr(recommendation_api, "get_teledrive_app_service", lambda: FakeService())

    status = client.get("/api/v1/recommendation/cache/status?recommendation_id=TD-COMIC-folder-1")
    download = client.post("/api/v1/recommendation/cache/download", json={"recommendation_id": "TD-COMIC-folder-1"})
    image = client.get("/api/v1/recommendation/cache/image?recommendation_id=TD-COMIC-folder-1&page_num=1")

    assert status.get_json()["data"]["cached_pages"] == [1, 2]
    assert status.get_json()["data"]["cache_info"]["source"] == "teledrive"
    assert download.get_json()["data"]["status"] == "teledrive"
    assert image.status_code == 200
    assert image.data == b"image-bytes"
    assert fake_response.closed is True


@pytest.mark.integration
def test_teledrive_service_builds_bridge_requests_and_auth_headers(third_party_client):
    from application.teledrive_app_service import TeleDriveAppService

    calls = []

    class FakeConfigStore:
        def get_plugin_config(self, *_args, **_kwargs):
            return {
                "enabled": True,
                "bridge_base_url": "http://bridge.local",
                "api_token": "token-1",
                "default_limit": 50,
                "convert_photos": True,
                "timeout_seconds": 7,
            }

    class FakeHttpClient:
        def request(self, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace(
                status_code=200,
                content=b'{"ok":true}',
                json=lambda: {"ok": True},
                headers={},
            )

    service = TeleDriveAppService(config_store=FakeConfigStore(), http_client=FakeHttpClient())

    service.import_once({"limit": 5}, dry_run=False)
    service._request_json("GET", "/v1/catalog/items", params={"limit": 5})
    stream_response = service.proxy_file_content(
        "file-1",
        method="GET",
        query_string="name=a.mp4",
        incoming_headers={"Range": "bytes=0-99", "X-Other": "skip"},
    )

    assert calls[0]["url"] == "http://bridge.local/v1/imports"
    assert calls[0]["headers"]["Authorization"] == "Bearer token-1"
    assert calls[0]["timeout"] == (7, None)
    assert calls[1]["url"] == "http://bridge.local/v1/catalog/items"
    assert calls[1]["params"] == {"limit": 5}
    assert calls[1]["headers"]["Authorization"] == "Bearer token-1"
    assert calls[1]["timeout"] == 7
    assert calls[2]["url"] == "http://bridge.local/v1/files/file-1/content?name=a.mp4"
    assert calls[2]["headers"]["Authorization"] == "Bearer token-1"
    assert calls[2]["headers"]["Range"] == "bytes=0-99"
    assert calls[2]["headers"].get("X-Other") is None
    assert calls[2]["timeout"] == (7, None)
    assert stream_response.status_code == 200


@pytest.mark.integration
def test_teledrive_recommendation_migrate_to_local_downloads_pages(third_party_client, monkeypatch):
    from application.recommendation_app_service import RecommendationAppService
    from application.persisted_content_metadata import resolve_data_relative_path
    import application.teledrive_app_service as teledrive_service_module

    comic_id = "TD-COMIC-folder-1"
    meta_dir = third_party_client["meta_dir"]

    recommendation_db_path = meta_dir / "recommendations_database.json"
    recommendation_db = load_json(recommendation_db_path)
    recommendation_db["recommendations"] = [
        item
        for item in recommendation_db.get("recommendations", [])
        if str((item or {}).get("id", "")) != comic_id
    ]
    recommendation_db["recommendations"].append(
        {
            "id": comic_id,
            "title": "TeleDrive Comic",
            "title_jp": "",
            "author": "",
            "desc": "",
            "cover_path": "/api/v1/comic/image?comic_id=TD-COMIC-folder-1&page_num=1",
            "total_page": 2,
            "current_page": 1,
            "score": 8.0,
            "tag_ids": [],
            "list_ids": [],
            "create_time": "2026-05-25T00:00:00",
            "last_read_time": "2026-05-25T00:00:00",
            "is_deleted": False,
            "platform": "TeleDrive",
            "plugin_id": "storage.teledrive",
            "plugin_name": "TeleDrive",
            "storage_path_relative": "teledrive://folder/folder-1",
            "storage_path_kind": "teledrive_dir",
            "display": {
                "teledrive": {
                    "type": "comic",
                    "path": "/comic/JM/86233",
                    "folder_id": "folder-1",
                    "work_id": "86233",
                    "pages": [
                        {"file_id": "page-1", "name": "001.jpg", "relative_path": "1/001.jpg"},
                        {"file_id": "page-2", "name": "002.jpg", "relative_path": "1/002.jpg"},
                    ],
                }
            },
        }
    )
    save_json(recommendation_db_path, recommendation_db)

    comic_db_path = meta_dir / "comics_database.json"
    comic_db = load_json(comic_db_path)
    comic_db["comics"] = [
        item
        for item in comic_db.get("comics", [])
        if str((item or {}).get("id", "")) != comic_id
    ]
    save_json(comic_db_path, comic_db)

    class FakeTeleDriveService:
        def download_file_to_path(self, file_id, target_path, *, name="", progress_callback=None):
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            with open(target_path, "wb") as file_obj:
                file_obj.write(f"{file_id}:{name}".encode("utf-8"))
            if progress_callback:
                progress_callback({
                    "bytes_written": os.path.getsize(target_path),
                    "total_bytes": os.path.getsize(target_path),
                    "force": True,
                })
            return {"path": target_path, "bytes": os.path.getsize(target_path)}

    monkeypatch.setattr(teledrive_service_module, "get_teledrive_app_service", lambda: FakeTeleDriveService())

    result = RecommendationAppService().migrate_to_local([comic_id])
    assert result.success
    assert result.data["imported_count"] == 1

    service = RecommendationAppService()
    local_comic = service._comic_repo.get_by_id(comic_id)
    assert local_comic is not None
    assert local_comic.storage_path_kind == "local_dir"
    assert "teledrive" not in local_comic.display
    assert local_comic.display["teledrive_origin"]["page_count"] == 2

    local_dir = resolve_data_relative_path(local_comic.storage_path_relative)
    assert os.path.isdir(local_dir)
    assert os.path.exists(os.path.join(local_dir, "1", "001.jpg"))
    assert os.path.exists(os.path.join(local_dir, "1", "002.jpg"))

    teledrive_lookup = teledrive_service_module.TeleDriveAppService()
    assert teledrive_lookup.get_teledrive_comic_pages(comic_id, include_recommendation=False) is None
    assert len(teledrive_lookup.get_teledrive_comic_pages(comic_id)) == 2


@pytest.mark.integration
def test_teledrive_video_migrate_to_local_downloads_episode_and_assets(third_party_client, monkeypatch):
    from application.video_app_service import VideoAppService
    import application.teledrive_app_service as teledrive_service_module

    client = third_party_client["client"]
    video_id = "TD-VIDEO-folder-2"
    meta_dir = third_party_client["meta_dir"]

    recommendation_db_path = meta_dir / "video_recommendations_database.json"
    recommendation_db = load_json(recommendation_db_path)
    recommendation_db["video_recommendations"] = [
        item
        for item in recommendation_db.get("video_recommendations", [])
        if str((item or {}).get("id", "")) != video_id
    ]
    recommendation_db["video_recommendations"].append(
        {
            "id": video_id,
            "title": "TeleDrive Video",
            "title_jp": "",
            "creator": "",
            "desc": "",
            "cover_path": "/api/v1/teledrive/files/cover/content?name=cover.jpg",
            "total_units": 1,
            "current_unit": 1,
            "score": 8.0,
            "tag_ids": [],
            "list_ids": [],
            "create_time": "2026-05-25T00:00:00",
            "last_access_time": "2026-05-25T00:00:00",
            "is_deleted": False,
            "platform": "TeleDrive",
            "plugin_id": "storage.teledrive",
            "plugin_name": "TeleDrive",
            "code": "td-video",
            "thumbnail_images": ["/api/v1/teledrive/files/thumb/content?name=001.jpg"],
            "preview_video": "/api/v1/teledrive/files/ep-1/content?name=01.mp4",
            "display": {
                "teledrive": {
                    "type": "video",
                    "path": "/video/td-video",
                    "folder_id": "folder-2",
                    "work_id": "td-video",
                    "episodes": [
                        {"file_id": "ep-1", "name": "01.mp4", "relative_path": "01.mp4"},
                    ],
                    "cover": {"file_id": "cover", "name": "cover.jpg", "relative_path": "cover.jpg"},
                    "thumbnails": [
                        {"file_id": "thumb", "name": "001.jpg", "relative_path": "thumbs/001.jpg"},
                    ],
                }
            },
        }
    )
    save_json(recommendation_db_path, recommendation_db)

    video_db_path = meta_dir / "videos_database.json"
    video_db = load_json(video_db_path)
    video_db["videos"] = [
        item
        for item in video_db.get("videos", [])
        if str((item or {}).get("id", "")) != video_id
        and str((item or {}).get("code", "")) != "td-video"
    ]
    save_json(video_db_path, video_db)

    class FakeTeleDriveService:
        def download_file_to_path(self, file_id, target_path, *, name="", progress_callback=None):
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            with open(target_path, "wb") as file_obj:
                file_obj.write(f"{file_id}:{name}".encode("utf-8"))
            if progress_callback:
                progress_callback({
                    "bytes_written": os.path.getsize(target_path),
                    "total_bytes": os.path.getsize(target_path),
                    "force": True,
                })
            return {"path": target_path, "bytes": os.path.getsize(target_path)}

    monkeypatch.setattr(teledrive_service_module, "get_teledrive_app_service", lambda: FakeTeleDriveService())

    service = VideoAppService()
    monkeypatch.setattr(service, "cache_cover_to_static_async", lambda *args, **kwargs: None)
    monkeypatch.setattr(service, "cache_thumbnail_images_async", lambda *args, **kwargs: None)
    monkeypatch.setattr(service, "cache_preview_video_async", lambda *args, **kwargs: None)

    progress_events = []
    result = service.migrate_recommendations_to_local(
        [video_id],
        progress_callback=lambda update: progress_events.append(dict(update or {})),
    )
    assert result.success
    assert result.data["imported_count"] == 1
    assert any(event.get("progress", 0) > 10 for event in progress_events)
    assert any("正在下载 TeleDrive 视频" in str(event.get("message", "")) for event in progress_events)

    local_video = service._video_repo.get_by_id(video_id)
    assert local_video is not None
    assert local_video.local_video_path.startswith("/media/video/TeleDrive/")
    assert local_video.preview_video_local == local_video.local_video_path
    assert local_video.cover_path_local.startswith("/media/video/TeleDrive/")
    assert local_video.thumbnail_images_local[0].startswith("/media/video/TeleDrive/")
    assert "teledrive" not in local_video.display
    assert local_video.display["teledrive_origin"]["episode_count"] == 1
    assert local_video.display["local_episodes"][0]["url"] == local_video.local_video_path

    detail_response = client.get("/api/v1/video/detail", query_string={"video_id": video_id})
    assert detail_response.status_code == 200
    detail_payload = detail_response.get_json()
    assert detail_payload["code"] == 200
    detail = detail_payload["data"] or {}
    playback = detail.get("playback") or {}
    primary = playback.get("primary") or {}
    preview = playback.get("preview") or {}
    assert primary.get("mode") == "local"
    assert [item.get("name") for item in (primary.get("episodes") or [])] == ["01.mp4"]
    assert preview.get("available") is False
    assert preview.get("assets") == []

    play_response = client.get(f"/api/v1/video/{video_id}/play-urls")
    assert play_response.status_code == 200
    play_payload = play_response.get_json()
    assert play_payload["code"] == 200
    stream_url = play_payload["data"]["sources"][0]["streams"][0]["url"]
    assert stream_url.startswith(f"/api/v1/video/local-stream/{video_id}")

    resolved_video_path = service.resolve_local_video_file_path(video_id)
    assert resolved_video_path and os.path.exists(resolved_video_path)
