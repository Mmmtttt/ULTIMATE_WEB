from flask import Flask
import werkzeug

from api.v1.history import history_bp
import api.v1.history as history_module
from infrastructure.common.result import ServiceResult

if not hasattr(werkzeug, "__version__"):
    werkzeug.__version__ = "test"


class FakeHistoryService:
    def __init__(self):
        self.visit_payload = None

    def list_history(self, content_type):
        return ServiceResult.ok(
            {
                "content_type": content_type,
                "items": [],
                "total": 0,
                "limit": 30,
            }
        )

    def record_visit(self, content_type, content_id, source):
        self.visit_payload = {
            "content_type": content_type,
            "content_id": content_id,
            "source": source,
        }
        return ServiceResult.ok(self.visit_payload)


def create_client(monkeypatch):
    app = Flask(__name__)
    fake_service = FakeHistoryService()
    monkeypatch.setattr(history_module, "history_service", fake_service)
    app.register_blueprint(history_bp, url_prefix="/api/v1/history")
    return app.test_client(), fake_service


def test_history_list_api_returns_standard_response(monkeypatch):
    client, _ = create_client(monkeypatch)

    response = client.get("/api/v1/history/list?content_type=video")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["code"] == 200
    assert payload["data"]["content_type"] == "video"


def test_history_visit_api_accepts_content_id(monkeypatch):
    client, fake_service = create_client(monkeypatch)

    response = client.post(
        "/api/v1/history/visit",
        json={"content_type": "comic", "content_id": "c1", "source": "preview"},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["code"] == 200
    assert fake_service.visit_payload == {
        "content_type": "comic",
        "content_id": "c1",
        "source": "preview",
    }
