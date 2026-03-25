from __future__ import annotations

from types import SimpleNamespace

import pytest

from tests.shared.runtime_data import find_by_id, load_json


def _ok_result(data=None, message="ok"):
    return SimpleNamespace(success=True, data=data, message=message)


@pytest.mark.integration
def test_author_search_works_route_forwards_offset_limit_and_author_name(third_party_client, monkeypatch):
    """
    Case Description:
    - Purpose: Guard `/api/v1/author/search-works` route-to-service contract so `author_name/offset/limit` are not rewritten.
    - Steps:
      1. Mock `author_service.search_author_works_by_name` and record call arguments.
      2. Call `GET /api/v1/author/search-works?author_name=Alice&offset=2&limit=3`.
      3. Assert recorded parameters and response payload.
    - Expected:
      1. HTTP 200 with business `code=200`.
      2. Service receives `("Alice", 2, 3)` exactly.
      3. Response contains mocked works payload.
    - History:
      - 2026-03-23: Added route forwarding contract guard for author search works.
    """
    client = third_party_client["client"]
    author_api = third_party_client["author_api"]
    captured = {}

    def fake_search(author_name, offset=0, limit=5):
        captured["author_name"] = author_name
        captured["offset"] = offset
        captured["limit"] = limit
        return _ok_result(
            {
                "creator_name": author_name,
                "works": [{"id": "W1", "title": "Work-1", "platform": "JM"}],
                "total": 1,
                "offset": offset,
                "limit": limit,
                "has_more": False,
            }
        )

    monkeypatch.setattr(author_api.author_service, "search_author_works_by_name", fake_search)

    response = client.get(
        "/api/v1/author/search-works",
        query_string={"author_name": "Alice", "offset": 2, "limit": 3},
    )
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["code"] == 200
    assert captured == {"author_name": "Alice", "offset": 2, "limit": 3}
    assert payload["data"]["works"][0]["id"] == "W1"
    assert payload["data"]["offset"] == 2
    assert payload["data"]["limit"] == 3


@pytest.mark.integration
def test_author_check_updates_route_triggers_remote_search_and_persists_latest_work(third_party_client, monkeypatch):
    """
    Case Description:
    - Purpose: Guard `/api/v1/author/check-updates` end-to-end backend chain: third-party search result -> author metadata persistence.
    - Steps:
      1. Subscribe a test author and get `author_id`.
      2. Mock in-memory cache access and `author_service._search_works`.
      3. Call `POST /api/v1/author/check-updates`.
      4. Verify search call parameters and `authors_database.json` persisted fields.
    - Expected:
      1. HTTP 200 with business `code=200`.
      2. `_search_works` is called with `page=1,max_pages=3`.
      3. Persisted author record updates `last_work_id/last_work_title/new_work_count`.
    - History:
      - 2026-03-23: Added update-check persistence contract guard for author third-party chain.
    """
    client = third_party_client["client"]
    author_api = third_party_client["author_api"]
    meta_dir = third_party_client["meta_dir"]
    service = author_api.author_service
    captured = {"search": [], "cache_set": []}

    subscribe_resp = client.post("/api/v1/author/subscribe", json={"name": "Author-TP-Check-01"})
    subscribe_payload = subscribe_resp.get_json()
    assert subscribe_resp.status_code == 200
    assert subscribe_payload["code"] == 200
    author_id = subscribe_payload["data"]["id"]

    class FakeCache:
        def get_persistent(self, *_args, **_kwargs):
            return None

        def set_persistent(self, key, value, category):
            captured["cache_set"].append({"key": key, "count": len(value or []), "category": category})
            return True

    def fake_search(author_name, page=1, max_pages=1):
        captured["search"].append({"author_name": author_name, "page": page, "max_pages": max_pages})
        return {
            "works": [
                {"id": "910001", "title": "Newest Work", "platform": "JM", "cover_url": "u1"},
                {"id": "910000", "title": "Older Work", "platform": "PK", "cover_url": "u2"},
            ],
            "has_more": False,
            "page": page,
        }

    monkeypatch.setattr(service, "_cache_manager", FakeCache())
    monkeypatch.setattr(service, "_search_works", fake_search)

    response = client.post("/api/v1/author/check-updates", json={"author_id": author_id})
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["code"] == 200
    assert captured["search"] == [{"author_name": "Author-TP-Check-01", "page": 1, "max_pages": 3}]
    assert len(payload["data"]["updated_authors"]) == 1
    assert payload["data"]["total_new_works"] == 1
    assert any(item["category"] == "author_works" for item in captured["cache_set"])

    authors = load_json(meta_dir / "authors_database.json").get("authors", [])
    saved = find_by_id(authors, author_id)
    assert saved is not None
    assert saved["last_work_id"] == "910001"
    assert saved["last_work_title"] == "Newest Work"
    assert int(saved["new_work_count"]) == 1


@pytest.mark.integration
def test_author_works_route_returns_503_when_external_api_unavailable_and_cache_only_false(third_party_client, monkeypatch):
    """
    Case Description:
    - Purpose: Guard `/api/v1/author/works/<author_id>` non-cache branch runtime guard: no third-party means explicit unavailable response.
    - Steps:
      1. Mock `author_service._get_external_api` to raise `RuntimeError`.
      2. Call `GET /api/v1/author/works/<author_id>?cache_only=false`.
      3. Verify business error code and message.
    - Expected:
      1. HTTP 200 with business `code=503`.
      2. Message contains third-party unavailable hint.
    - History:
      - 2026-03-23: Added runtime guard branch test for author works route.
    """
    client = third_party_client["client"]
    author_api = third_party_client["author_api"]

    monkeypatch.setattr(
        author_api.author_service,
        "_get_external_api",
        lambda: (_ for _ in ()).throw(RuntimeError("third-party integration is disabled in current runtime profile: full")),
    )

    response = client.get(
        "/api/v1/author/works/non-exist-author",
        query_string={"offset": 0, "limit": 5, "cache_only": "false"},
    )
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["code"] == 503
    assert "third-party integration is disabled" in str(payload["msg"]).lower()


@pytest.mark.integration
def test_author_works_route_cache_only_bypasses_external_api_guard(third_party_client, monkeypatch):
    """
    Case Description:
    - Purpose: Guard `/api/v1/author/works/<author_id>?cache_only=true` branch so cache-only requests never require external API availability.
    - Steps:
      1. Mock `author_service._get_external_api` to fail if called.
      2. Mock `author_service.get_author_works_paginated` and record `cache_only` argument.
      3. Call route with `cache_only=true`.
      4. Verify route succeeds and forwards `cache_only=True`.
    - Expected:
      1. HTTP 200 with business `code=200`.
      2. `_get_external_api` is not used.
      3. Service gets `cache_only=True`.
    - History:
      - 2026-03-23: Added cache-only bypass guard for author works route.
    """
    client = third_party_client["client"]
    author_api = third_party_client["author_api"]
    captured = {}

    def fail_if_called():
        raise AssertionError("_get_external_api should not be called for cache_only=true")

    def fake_get_paginated(author_id, offset, limit, cache_only=False, force_refresh=False):
        captured["author_id"] = author_id
        captured["offset"] = offset
        captured["limit"] = limit
        captured["cache_only"] = cache_only
        captured["force_refresh"] = force_refresh
        return _ok_result(
            {
                "author": {"id": author_id, "name": "AuthorCache"},
                "works": [],
                "total": 0,
                "offset": offset,
                "limit": limit,
                "has_more": False,
                "from_cache": True,
                "cache_only": cache_only,
                "force_refresh": force_refresh,
            }
        )

    monkeypatch.setattr(author_api.author_service, "_get_external_api", fail_if_called)
    monkeypatch.setattr(author_api.author_service, "get_author_works_paginated", fake_get_paginated)

    response = client.get(
        "/api/v1/author/works/cache-author-01",
        query_string={"offset": 1, "limit": 4, "cache_only": "true"},
    )
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["code"] == 200
    assert captured == {
        "author_id": "cache-author-01",
        "offset": 1,
        "limit": 4,
        "cache_only": True,
        "force_refresh": False,
    }
