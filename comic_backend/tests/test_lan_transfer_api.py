import io

from flask import Flask
import werkzeug

from api.v1.transfer import transfer_bp
import api.v1.transfer as transfer_module
from infrastructure.common.result import ServiceResult

if not hasattr(werkzeug, "__version__"):
    werkzeug.__version__ = "test"


class FakeTransferService:
    def __init__(self):
        self.uploaded_filename = ""

    def list_items(self):
        return ServiceResult.ok({"items": []})

    def publish_text(self, text, name=""):
        return ServiceResult.ok({"id": "text-1", "kind": "text", "text": text, "name": name or "shared-text.txt"})

    def register_server_file(self, file_path, name=""):
        return ServiceResult.ok({"id": "file-1", "kind": "server_file", "server_path": file_path, "name": name})

    def save_upload(self, file_storage):
        self.uploaded_filename = file_storage.filename
        return ServiceResult.ok({"id": "upload-1", "kind": "upload", "name": file_storage.filename})

    def delete_item(self, item_id):
        return ServiceResult.ok({"id": item_id, "deleted": True})

    def resolve_download(self, item_id):
        return ServiceResult.ok(
            {
                "kind": "text",
                "content": f"download:{item_id}",
                "name": "download.txt",
                "mime_type": "text/plain; charset=utf-8",
            }
        )


def create_client(monkeypatch):
    app = Flask(__name__)
    fake_service = FakeTransferService()
    monkeypatch.setattr(transfer_module, "transfer_service", fake_service)
    app.register_blueprint(transfer_bp, url_prefix="/api/v1/transfer")
    return app.test_client(), fake_service


def test_transfer_list_api_returns_standard_response(monkeypatch):
    client, _ = create_client(monkeypatch)

    response = client.get("/api/v1/transfer/items")

    payload = response.get_json()
    assert payload["code"] == 200
    assert payload["data"]["items"] == []


def test_transfer_publish_text_api(monkeypatch):
    client, _ = create_client(monkeypatch)

    response = client.post("/api/v1/transfer/text", json={"text": "hello", "name": "hello.txt"})

    payload = response.get_json()
    assert payload["code"] == 200
    assert payload["data"]["text"] == "hello"


def test_transfer_upload_api(monkeypatch):
    client, fake_service = create_client(monkeypatch)

    response = client.post(
        "/api/v1/transfer/upload",
        data={"file": (io.BytesIO(b"abc"), "sample.txt")},
        content_type="multipart/form-data",
    )

    payload = response.get_json()
    assert payload["code"] == 200
    assert fake_service.uploaded_filename == "sample.txt"


def test_transfer_text_download_api(monkeypatch):
    client, _ = create_client(monkeypatch)

    response = client.get("/api/v1/transfer/download/text-1")

    assert response.status_code == 200
    assert response.data == b"download:text-1"
