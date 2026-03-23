from __future__ import annotations

from types import SimpleNamespace

import pytest


def _ok_result(data=None, message="ok"):
    return SimpleNamespace(success=True, data=data, message=message)


@pytest.mark.integration
def test_video_actor_search_works_route_forwards_offset_limit(third_party_client, monkeypatch):
    """
    Case Description:
    - Purpose: Guard `/api/v1/video/actor/search-works` contract from frontend query args to actor service call.
    - Steps:
      1. Mock `video_api.actor_service.search_actor_works_by_name` and record args.
      2. Call search route with `actor_name/offset/limit`.
      3. Assert args and response payload.
    - Expected:
      1. HTTP 200 with business `code=200`.
      2. Service receives `("Airi", 2, 4)`.
      3. Response contains mocked works list.
    - History:
      - 2026-03-23: Added video actor search entry contract guard.
    """
    client = third_party_client["client"]
    video_api = third_party_client["video_api"]
    captured = {}

    def fake_search(actor_name, offset=0, limit=5):
        captured["actor_name"] = actor_name
        captured["offset"] = offset
        captured["limit"] = limit
        return _ok_result(
            {
                "creator_name": actor_name,
                "works": [{"id": "V-ACT-11", "title": "Video Actor Work"}],
                "total": 1,
                "offset": offset,
                "limit": limit,
                "has_more": False,
            }
        )

    monkeypatch.setattr(video_api.actor_service, "search_actor_works_by_name", fake_search)

    response = client.get(
        "/api/v1/video/actor/search-works",
        query_string={"actor_name": "Airi", "offset": 2, "limit": 4},
    )
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["code"] == 200
    assert captured == {"actor_name": "Airi", "offset": 2, "limit": 4}
    assert payload["data"]["works"][0]["id"] == "V-ACT-11"


@pytest.mark.integration
def test_video_actor_works_route_forwards_actor_id_offset_limit(third_party_client, monkeypatch):
    """
    Case Description:
    - Purpose: Guard `/api/v1/video/actor/works/<actor_id>` contract so route-level paging is forwarded unchanged.
    - Steps:
      1. Mock `video_api.actor_service.get_actor_works_paginated`.
      2. Call route with `offset/limit`.
      3. Assert forwarded args and response.
    - Expected:
      1. HTTP 200 with business `code=200`.
      2. Service receives `(actor_id, offset, limit)` exactly.
      3. Response data contains mocked actor works payload.
    - History:
      - 2026-03-23: Added video actor works entry contract guard.
    """
    client = third_party_client["client"]
    video_api = third_party_client["video_api"]
    captured = {}

    def fake_get(actor_id, offset=0, limit=5):
        captured["actor_id"] = actor_id
        captured["offset"] = offset
        captured["limit"] = limit
        return _ok_result(
            {
                "actor": {"id": actor_id, "name": "Video-Actor"},
                "works": [{"id": "V-ACT-21", "title": "Video Actor Work 21"}],
                "total": 1,
                "offset": offset,
                "limit": limit,
                "has_more": False,
            }
        )

    monkeypatch.setattr(video_api.actor_service, "get_actor_works_paginated", fake_get)

    response = client.get("/api/v1/video/actor/works/actor-video-8", query_string={"offset": 5, "limit": 3})
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["code"] == 200
    assert captured == {"actor_id": "actor-video-8", "offset": 5, "limit": 3}
    assert payload["data"]["works"][0]["id"] == "V-ACT-21"


@pytest.mark.integration
def test_video_actor_works_cache_clear_route_forwards_actor_name(third_party_client, monkeypatch):
    """
    Case Description:
    - Purpose: Guard `/api/v1/video/actor/works-cache/clear` route contract so optional `actor_name` query is forwarded
      unchanged to actor service cache-clear method.
    - Steps:
      1. Mock `video_api.actor_service.clear_actor_works_cache` and record `actor_name`.
      2. Call `DELETE /api/v1/video/actor/works-cache/clear?actor_name=Airi`.
      3. Assert forwarded argument and response mapping.
    - Expected:
      1. HTTP 200 with business `code=200`.
      2. Service receives exactly `actor_name="Airi"`.
      3. Response `data` matches mocked clear result.
    - History:
      - 2026-03-24: Added cache-clear contract guard for video actor third-party works cache path.
    """
    client = third_party_client["client"]
    video_api = third_party_client["video_api"]
    captured = {}

    def fake_clear(actor_name=None):
        captured["actor_name"] = actor_name
        return _ok_result({"cleared": 1, "scope": actor_name or "all"})

    monkeypatch.setattr(video_api.actor_service, "clear_actor_works_cache", fake_clear)

    response = client.delete(
        "/api/v1/video/actor/works-cache/clear",
        query_string={"actor_name": "Airi"},
    )
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["code"] == 200
    assert captured == {"actor_name": "Airi"}
    assert payload["data"] == {"cleared": 1, "scope": "Airi"}
