from __future__ import annotations

import pytest


def _assert_disabled_payload(response) -> None:
    payload = response.get_json()
    assert response.status_code == 200
    assert payload["code"] == 503
    assert "third-party integration is disabled" in str(payload["msg"]).lower()


@pytest.mark.integration
def test_runtime_guard_returns_503_for_third_party_endpoints_when_disabled(third_party_client, monkeypatch):
    """
    Case Description:
    - Purpose: Guard runtime-profile disable behavior for decorated third-party endpoints:
      once runtime says third-party is off, guarded routes must fail closed with business `503`.
    - Steps:
      1. Patch `api.v1.runtime_guard.is_third_party_enabled` to return `False`.
      2. Call representative guarded endpoints from comic/video/list/author modules.
      3. Assert consistent unavailable payload.
    - Expected:
      1. Every endpoint returns HTTP 200 with business `code=503`.
      2. Error message includes third-party disabled hint.
    - History:
      - 2026-03-23: Added centralized runtime-guard contract test (decorator path).
    """
    client = third_party_client["client"]
    comic_api = third_party_client["comic_api"]
    video_api = third_party_client["video_api"]
    list_api = third_party_client["list_api"]
    author_api = third_party_client["author_api"]

    guarded_views = [
        comic_api.search_third_party_comics,
        video_api.third_party_search,
        list_api.get_platform_user_lists,
        author_api.search_author_works,
    ]
    for view in guarded_views:
        monkeypatch.setitem(view.__globals__, "is_third_party_enabled", lambda: False)
        monkeypatch.setitem(view.__globals__, "get_runtime_profile", lambda: "mobile_core")

    responses = [
        client.get("/api/v1/comic/search-third-party", query_string={"keyword": "k", "platform": "all"}),
        client.get("/api/v1/video/third-party/search", query_string={"keyword": "k", "platform": "all"}),
        client.get("/api/v1/list/platform/lists", query_string={"platform": "JAVDB"}),
        client.get("/api/v1/author/search-works", query_string={"author_name": "Author-X"}),
    ]

    for response in responses:
        _assert_disabled_payload(response)
