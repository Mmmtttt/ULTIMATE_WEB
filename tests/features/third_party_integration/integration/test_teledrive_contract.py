from __future__ import annotations

import json

import pytest

from tests.shared.runtime_data import load_json, save_json


class FakeBridgeResponse:
    def __init__(self, status_code=200, payload=None, body=b"", headers=None):
        self.status_code = status_code
        self._payload = payload
        self._body = body
        self.headers = headers or {}
        self.content = body if body else (json.dumps(payload).encode("utf-8") if payload is not None else b"")
        self.text = self.content.decode("utf-8", errors="ignore")
        self.closed = False

    def json(self):
        if self._payload is not None:
            return self._payload
        return json.loads(self.text)

    def iter_content(self, chunk_size=1):
        for index in range(0, len(self._body), chunk_size):
            yield self._body[index:index + chunk_size]

    def close(self):
        self.closed = True


def _configure_teledrive(config_path, **updates):
    payload = load_json(config_path)
    adapter = payload.setdefault("adapters", {}).setdefault("teledrive", {})
    adapter.update(
        {
            "enabled": True,
            "bridge_base_url": "http://bridge.local",
            "api_token": "secret-token",
            "default_limit": 12,
            "convert_photos": False,
            "timeout_seconds": 9,
        }
    )
    adapter.update(updates)
    save_json(config_path, payload)


@pytest.mark.integration
def test_teledrive_manifest_config_defaults_and_token_redaction(third_party_client):
    client = third_party_client["client"]
    config_path = third_party_client["third_party_config_path"]

    response = client.get("/api/v1/comic/third-party/config")
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["code"] == 200
    data = payload["data"] or {}
    assert "teledrive" in (data.get("adapter_order") or [])
    assert ((data.get("schema") or {}).get("teledrive") or {}).get("label") == "TeleDrive"
    teledrive_config = ((data.get("adapters") or {}).get("teledrive") or {})
    assert teledrive_config["enabled"] is True
    assert teledrive_config["bridge_base_url"] == "http://127.0.0.1:8892"
    assert teledrive_config["default_limit"] == 100
    assert teledrive_config["convert_photos"] is True
    assert "api_token" not in teledrive_config

    save_response = client.post(
        "/api/v1/comic/third-party/config",
        json={
            "adapter": "teledrive",
            "config": {
                "enabled": True,
                "bridge_base_url": "http://bridge.local/",
                "api_token": "secret-token",
                "default_limit": 25,
                "convert_photos": False,
                "timeout_seconds": 8,
            },
        },
    )
    save_payload = save_response.get_json()
    assert save_response.status_code == 200
    assert save_payload["code"] == 200
    assert save_payload["data"]["updated_adapters"] == ["teledrive"]

    persisted = load_json(config_path)
    persisted_teledrive = ((persisted.get("adapters") or {}).get("teledrive") or {})
    assert persisted_teledrive["api_token"] == "secret-token"
    assert persisted_teledrive["bridge_base_url"] == "http://bridge.local"

    readback = client.get("/api/v1/comic/third-party/config").get_json()["data"]
    public_config = ((readback.get("adapters") or {}).get("teledrive") or {})
    assert "api_token" not in public_config
    assert public_config["api_token_configured"] is True


@pytest.mark.integration
def test_teledrive_json_routes_proxy_bridge_with_bearer_token(third_party_client, monkeypatch):
    client = third_party_client["client"]
    _configure_teledrive(third_party_client["third_party_config_path"])
    calls = []

    def fake_request(method, url, **kwargs):
        calls.append({"method": method, "url": url, "kwargs": kwargs})
        assert kwargs.get("headers", {}).get("Authorization") == "Bearer secret-token"
        if url == "http://bridge.local/health":
            return FakeBridgeResponse(payload={"ok": True, "service": "teledrive-bridge"})
        if url == "http://bridge.local/v1/imports/latest":
            return FakeBridgeResponse(payload={"ok": True, "last_result": {"scanned": 9, "imported": 2}})
        if url == "http://bridge.local/v1/catalog/items":
            return FakeBridgeResponse(
                payload={
                    "items": [{"id": "file-video", "name": "video.mp4", "kind": "video", "size": 10}],
                    "count": 1,
                }
            )
        if url == "http://bridge.local/v1/imports":
            body = kwargs.get("json") or {}
            return FakeBridgeResponse(
                payload={
                    "result": {
                        "dry_run": body.get("dry_run"),
                        "limit": body.get("limit"),
                        "convert_photos": body.get("convert_photos"),
                    }
                }
            )
        raise AssertionError(f"unexpected bridge request: {method} {url}")

    monkeypatch.setattr("requests.request", fake_request)

    status = client.get("/api/v1/teledrive/status").get_json()
    assert status["code"] == 200
    assert status["data"]["bridge_health"]["ok"] is True
    assert status["data"]["latest_import"]["last_result"]["imported"] == 2
    assert "api_token" not in status["data"]["config"]

    preview = client.post("/api/v1/teledrive/imports/preview", json={"limit": 3}).get_json()
    assert preview["code"] == 200
    assert preview["data"]["result"]["dry_run"] is True
    assert preview["data"]["result"]["limit"] == 3
    assert preview["data"]["result"]["convert_photos"] is False

    imported = client.post("/api/v1/teledrive/imports", json={"limit": 4, "convert_photos": True}).get_json()
    assert imported["code"] == 200
    assert imported["data"]["result"]["dry_run"] is False
    assert imported["data"]["result"]["limit"] == 4
    assert imported["data"]["result"]["convert_photos"] is True

    catalog = client.get("/api/v1/teledrive/catalog").get_json()
    assert catalog["code"] == 200
    assert catalog["data"]["items"][0]["id"] == "file-video"

    catalog_call = next(item for item in calls if item["url"] == "http://bridge.local/v1/catalog/items")
    assert catalog_call["kwargs"]["params"]["limit"] == 12


@pytest.mark.integration
def test_teledrive_file_content_preserves_range_and_stream_headers(third_party_client, monkeypatch):
    client = third_party_client["client"]
    _configure_teledrive(third_party_client["third_party_config_path"])
    calls = []

    def fake_request(method, url, **kwargs):
        calls.append({"method": method, "url": url, "kwargs": kwargs})
        assert kwargs.get("stream") is True
        assert kwargs.get("headers", {}).get("Authorization") == "Bearer secret-token"
        if method == "GET":
            assert kwargs.get("headers", {}).get("Range") == "bytes=0-2"
            return FakeBridgeResponse(
                status_code=206,
                body=b"abc",
                headers={
                    "Content-Type": "video/mp4",
                    "Content-Length": "3",
                    "Content-Range": "bytes 0-2/10",
                    "Accept-Ranges": "bytes",
                    "X-Internal": "hidden",
                },
            )
        if method == "HEAD":
            return FakeBridgeResponse(
                status_code=200,
                headers={
                    "Content-Type": "video/mp4",
                    "Content-Length": "10",
                    "Accept-Ranges": "bytes",
                },
            )
        raise AssertionError(f"unexpected method: {method}")

    monkeypatch.setattr("requests.request", fake_request)

    response = client.get(
        "/api/v1/teledrive/files/file-1/content?name=video.mp4",
        headers={"Range": "bytes=0-2"},
    )
    assert response.status_code == 206
    assert response.data == b"abc"
    assert response.headers["Content-Type"] == "video/mp4"
    assert response.headers["Content-Range"] == "bytes 0-2/10"
    assert response.headers["Accept-Ranges"] == "bytes"
    assert "X-Internal" not in response.headers

    head = client.head("/api/v1/teledrive/files/file-1/content?name=video.mp4")
    assert head.status_code == 200
    assert head.data == b""
    assert head.headers["Content-Length"] == "10"

    get_call = calls[0]
    assert get_call["url"] == "http://bridge.local/v1/files/file-1/content?name=video.mp4"
