from __future__ import annotations

import importlib
from types import SimpleNamespace

import pytest


def _ok_result(data=None, message="ok"):
    return SimpleNamespace(success=True, data=data, message=message)


@pytest.mark.integration
def test_recommendation_cache_download_returns_503_when_third_party_unavailable(third_party_client, monkeypatch):
    """
    Case Description:
    - Purpose: Guard `/api/v1/recommendation/cache/download` unavailable branch so disabled third-party runtime is reported clearly.
    - Steps:
      1. Mock cache manager `is_cached=False`.
      2. Mock `recommendation_service._get_platform_service` to raise `RuntimeError`.
      3. Call cache download API.
    - Expected:
      1. HTTP 200 with business `code=503`.
      2. Message includes third-party unavailable hint.
    - History:
      - 2026-03-23: Added runtime-guard branch coverage for recommendation cache download.
    """
    client = third_party_client["client"]
    recommendation_api = importlib.import_module("api.v1.recommendation")

    monkeypatch.setattr(recommendation_api.recommendation_cache_manager, "is_cached", lambda _rid: False)
    monkeypatch.setattr(
        recommendation_api.recommendation_service,
        "_get_platform_service",
        lambda: (_ for _ in ()).throw(RuntimeError("third-party integration is disabled in current runtime profile: full")),
    )

    response = client.post(
        "/api/v1/recommendation/cache/download",
        json={"recommendation_id": "JM000001"},
    )
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["code"] == 503
    assert "third-party integration is disabled" in str(payload["msg"]).lower()


@pytest.mark.integration
def test_recommendation_cache_download_forwards_platform_download_contract(third_party_client, monkeypatch):
    """
    Case Description:
    - Purpose: Guard recommendation cache download contract with third-party platform service:
      API input -> platform/original_id mapping -> download_album args -> cache/page mapping.
    - Steps:
      1. Mock recommendation detail, cache manager methods, and `update_total_page`.
      2. Mock `third_party.platform_service.get_platform_service().download_album`.
      3. Call `POST /api/v1/recommendation/cache/download` with a JM recommendation id.
      4. Assert third-party call args and final API payload.
    - Expected:
      1. HTTP 200 with business `code=200`.
      2. `download_album` receives `platform=JM`, `original_id`, `show_progress=False`, and JM cache dir.
      3. API returns `status=downloaded` with cached pages and normalized `total_pages`.
    - History:
      - 2026-03-23: Added strong contract guard for recommendation cache download chain.
    """
    client = third_party_client["client"]
    recommendation_api = importlib.import_module("api.v1.recommendation")
    platform_service_module = importlib.import_module("third_party.platform_service")
    captured = {"download": [], "add_to_cache": [], "update_total_page": []}
    recommendation_id = "JM777001"

    monkeypatch.setattr(recommendation_api.recommendation_cache_manager, "is_cached", lambda _rid: False)
    monkeypatch.setattr(recommendation_api.recommendation_service, "_get_platform_service", lambda: object())
    monkeypatch.setattr(
        recommendation_api.recommendation_service,
        "get_recommendation_detail",
        lambda rid: _ok_result({"id": rid, "total_page": 6, "title": "Rec-777001"}),
    )
    monkeypatch.setattr(
        recommendation_api.recommendation_service,
        "update_total_page",
        lambda rid, total_page: captured["update_total_page"].append((rid, total_page))
        or _ok_result({"id": rid, "total_page": total_page}),
    )
    monkeypatch.setattr(
        recommendation_api.recommendation_cache_manager,
        "add_to_cache",
        lambda rid, page_count: captured["add_to_cache"].append((rid, page_count)) or True,
    )
    monkeypatch.setattr(
        recommendation_api.recommendation_cache_manager,
        "get_cached_pages",
        lambda _rid: [1, 2, 3, 4],
    )

    class FakePlatformService:
        def download_album(self, platform, original_id, download_dir=None, show_progress=True):
            captured["download"].append(
                {
                    "platform": getattr(platform, "value", str(platform)),
                    "original_id": str(original_id),
                    "download_dir": str(download_dir or ""),
                    "show_progress": show_progress,
                }
            )
            return {"local_pages": 6, "pages_count": 6}, True

    monkeypatch.setattr(platform_service_module, "get_platform_service", lambda: FakePlatformService())

    response = client.post(
        "/api/v1/recommendation/cache/download",
        json={"recommendation_id": recommendation_id},
    )
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["code"] == 200
    assert payload["data"]["status"] == "downloaded"
    assert payload["data"]["total_pages"] == 4
    assert payload["data"]["cached_pages"] == [1, 2, 3, 4]

    assert len(captured["download"]) == 1
    assert captured["download"][0]["platform"] == "JM"
    assert captured["download"][0]["original_id"] == "777001"
    assert captured["download"][0]["show_progress"] is False
    assert "/recommendation_cache/comic/JM" in captured["download"][0]["download_dir"].replace("\\", "/")

    # First add uses third-party reported local page count, second add uses actual cached page count.
    assert captured["add_to_cache"] == [(recommendation_id, 6), (recommendation_id, 4)]
    assert captured["update_total_page"] == [(recommendation_id, 4)]
