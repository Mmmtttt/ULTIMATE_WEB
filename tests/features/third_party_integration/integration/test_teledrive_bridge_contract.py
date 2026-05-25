from __future__ import annotations

from types import SimpleNamespace

import pytest


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
