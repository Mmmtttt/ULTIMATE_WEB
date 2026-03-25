from __future__ import annotations

from types import SimpleNamespace

import pytest

from tests.shared.runtime_data import find_by_id, load_json

def _ok_result(data=None, message="ok"):
    return SimpleNamespace(success=True, data=data, message=message)


@pytest.mark.integration
def test_actor_service_search_works_forwards_adapter_calls_and_interleaves_results(third_party_client, monkeypatch):
    """
    Case Description:
    - Purpose: Guard actor service third-party contract in `_search_works`: adapter selection, call parameters, and cross-platform merge order.
    - Steps:
      1. Mock `api.v1.video.get_video_adapter` for `javdb/javbus`.
      2. Call `actor_service._search_works("Mina", page=2, max_pages=4)`.
      3. Verify adapter calls and merged result order.
    - Expected:
      1. Adapters are called with page/max_pages forwarded unchanged.
      2. Returned works include both platforms.
      3. Result order is grouped by platform: all `javdb` first, then `javbus`.
    - History:
      - 2026-03-23: Added actor service third-party merge contract coverage.
    """
    actor_api = third_party_client["actor_api"]
    video_api = third_party_client["video_api"]
    service = actor_api.actor_service
    calls = []

    class FakeAdapter:
        def __init__(self, platform):
            self.platform = platform

        def search_videos(self, creator_name, page=1, max_pages=1):
            calls.append(
                {
                    "platform": self.platform,
                    "creator_name": creator_name,
                    "page": page,
                    "max_pages": max_pages,
                }
            )
            if self.platform == "javdb":
                return {
                    "videos": [
                        {"video_id": "DB-1", "title": "DB One", "cover_url": "https://img/db1.jpg"},
                        {"video_id": "DB-2", "title": "DB Two", "cover_url": "https://img/db2.jpg"},
                    ],
                    "has_next": True,
                }
            return {
                "videos": [
                    {
                        "code": "BUS-1",
                        "title": "BUS One",
                        "cover_url": "https://www.javbus.com/pics/thumb/c0ou.jpg",
                    },
                ],
                "has_next": False,
            }

    monkeypatch.setattr(video_api, "get_video_adapter", lambda platform, *args, **kwargs: FakeAdapter(platform))

    result = service._search_works("Mina", page=2, max_pages=4)
    works = result.get("works", [])

    assert len(calls) == 2
    assert calls[0] == {"platform": "javdb", "creator_name": "Mina", "page": 2, "max_pages": 4}
    assert calls[1] == {"platform": "javbus", "creator_name": "Mina", "page": 2, "max_pages": 4}
    assert [item["id"] for item in works] == ["DB-1", "DB-2", "BUS-1"]
    assert [item["platform"] for item in works] == ["javdb", "javdb", "javbus"]
    assert str(works[-1]["cover_url"]).startswith("/api/v1/video/proxy2?url=")
    assert result["has_more"] is True
    assert result["page"] == 2


@pytest.mark.integration
def test_actor_videos_route_keeps_platform_group_order_and_proxies_javbus_cover(third_party_client, monkeypatch):
    """
    Case Description:
    - Purpose: Guard actor videos route contract for two key behaviors:
      1) grouped output order (`javdb` before `javbus`), 2) javbus anti-hotlink cover proxy mapping.
    - Steps:
      1. Mock `api.v1.video.get_video_adapter` for `javdb/javbus`.
      2. Call `GET /api/v1/actor/videos?actor_name=Mina`.
      3. Assert order and javbus proxy cover url.
    - Expected:
      1. HTTP 200 with business `code=200`.
      2. Output order is `javdb` group first, then `javbus`.
      3. Javbus cover url is transformed to `/api/v1/video/proxy2?url=...`.
    """
    client = third_party_client["client"]
    video_api = third_party_client["video_api"]

    class FakeAdapter:
        def __init__(self, platform):
            self.platform = platform

        def search_videos(self, creator_name, page=1, max_pages=1):
            if self.platform == "javdb":
                return {
                    "videos": [
                        {"video_id": "DB-11", "title": "DB Eleven", "cover_url": "https://img/db11.jpg"},
                    ],
                    "has_next": False,
                }
            return {
                "videos": [
                    {
                        "code": "BUS-11",
                        "title": "BUS Eleven",
                        "cover_url": "https://www.javbus.com/pics/thumb/c0ou.jpg",
                    }
                ],
                "has_next": False,
            }

    monkeypatch.setattr(video_api, "get_video_adapter", lambda platform, *args, **kwargs: FakeAdapter(platform))

    response = client.get("/api/v1/actor/videos", query_string={"actor_name": "Mina"})
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["code"] == 200
    works = payload["data"]
    assert [item["id"] for item in works] == ["DB-11", "BUS-11"]
    assert [item["platform"] for item in works] == ["javdb", "javbus"]
    assert str(works[1]["cover_url"]).startswith("/api/v1/video/proxy2?url=")


@pytest.mark.integration
def test_actor_search_works_route_forwards_offset_limit_to_service(third_party_client, monkeypatch):
    """
    Case Description:
    - Purpose: Guard `/api/v1/actor/search-works` route contract so `actor_name/offset/limit` are passed to service exactly.
    - Steps:
      1. Mock `actor_service.search_actor_works_by_name` and record parameters.
      2. Call `GET /api/v1/actor/search-works?actor_name=Rika&offset=3&limit=2`.
      3. Assert forwarded parameters and response payload.
    - Expected:
      1. HTTP 200 with business `code=200`.
      2. Service receives `("Rika", 3, 2)`.
      3. Response contains mocked pagination payload.
    - History:
      - 2026-03-23: Added actor search route forwarding guard.
    """
    client = third_party_client["client"]
    actor_api = third_party_client["actor_api"]
    captured = {}

    def fake_search(actor_name, offset=0, limit=5):
        captured["actor_name"] = actor_name
        captured["offset"] = offset
        captured["limit"] = limit
        return _ok_result(
            {
                "creator_name": actor_name,
                "works": [{"id": "ACT-W1", "title": "Actor Work"}],
                "total": 1,
                "offset": offset,
                "limit": limit,
                "has_more": False,
            }
        )

    monkeypatch.setattr(actor_api.actor_service, "search_actor_works_by_name", fake_search)

    response = client.get(
        "/api/v1/actor/search-works",
        query_string={"actor_name": "Rika", "offset": 3, "limit": 2},
    )
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["code"] == 200
    assert captured == {"actor_name": "Rika", "offset": 3, "limit": 2}
    assert payload["data"]["works"][0]["id"] == "ACT-W1"


@pytest.mark.integration
def test_actor_videos_route_forwards_actor_name_to_service(third_party_client, monkeypatch):
    """
    Case Description:
    - Purpose: Guard `/api/v1/actor/videos` backend contract from query input to service call and response mapping.
    - Steps:
      1. Mock `actor_service.get_actor_videos` and record actor name.
      2. Call `GET /api/v1/actor/videos?actor_name=Yui`.
      3. Assert service input and returned work fields.
    - Expected:
      1. HTTP 200 with business `code=200`.
      2. Service receives actor name `Yui`.
      3. Response contains mocked third-party works.
    - History:
      - 2026-03-23: Added actor videos route third-party contract guard.
    """
    client = third_party_client["client"]
    actor_api = third_party_client["actor_api"]
    captured = {}

    def fake_get_actor_videos(actor_name):
        captured["actor_name"] = actor_name
        return _ok_result(
            [
                {
                    "id": "JAVDB-ACT-100",
                    "title": "Actor Route Video",
                    "platform": "javdb",
                }
            ]
        )

    monkeypatch.setattr(actor_api.actor_service, "get_actor_videos", fake_get_actor_videos)

    response = client.get("/api/v1/actor/videos", query_string={"actor_name": "Yui"})
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["code"] == 200
    assert captured == {"actor_name": "Yui"}
    assert payload["data"][0]["id"] == "JAVDB-ACT-100"


@pytest.mark.integration
def test_actor_check_updates_persists_latest_work_and_calls_search_contract(third_party_client, monkeypatch):
    """
    Case Description:
    - Purpose: Guard actor update-check third-party chain: search contract (`page/max_pages`) and persisted latest work metadata.
    - Steps:
      1. Subscribe a test actor and get `actor_id`.
      2. Mock cache manager and `actor_service._search_works`.
      3. Call `POST /api/v1/actor/check-updates`.
      4. Assert search call parameters and `actors_database.json` persisted fields.
    - Expected:
      1. HTTP 200 with business `code=200`.
      2. `_search_works` is called with `page=1,max_pages=3`.
      3. Persisted actor record updates `last_work_id/last_work_title/new_work_count`.
    - History:
      - 2026-03-23: Added actor update-check persistence contract guard.
    """
    client = third_party_client["client"]
    actor_api = third_party_client["actor_api"]
    meta_dir = third_party_client["meta_dir"]
    service = actor_api.actor_service
    captured = {"search": [], "cache_set": []}

    subscribe_resp = client.post("/api/v1/actor/subscribe", json={"name": "Actor-TP-Check-01"})
    subscribe_payload = subscribe_resp.get_json()
    assert subscribe_resp.status_code == 200
    assert subscribe_payload["code"] == 200
    actor_id = subscribe_payload["data"]["id"]

    class FakeCache:
        def get_persistent(self, *_args, **_kwargs):
            return None

        def set_persistent(self, key, value, category):
            captured["cache_set"].append({"key": key, "count": len(value or []), "category": category})
            return True

    def fake_search(actor_name, page=1, max_pages=1):
        captured["search"].append({"actor_name": actor_name, "page": page, "max_pages": max_pages})
        return {
            "works": [
                {"id": "AV-9001", "title": "Latest Actor Work", "platform": "javdb"},
                {"id": "AV-9000", "title": "Old Actor Work", "platform": "javbus"},
            ],
            "has_more": False,
            "page": page,
        }

    monkeypatch.setattr(service, "_cache_manager", FakeCache())
    monkeypatch.setattr(service, "_search_works", fake_search)

    response = client.post("/api/v1/actor/check-updates", json={"actor_id": actor_id})
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["code"] == 200
    assert captured["search"] == [{"actor_name": "Actor-TP-Check-01", "page": 1, "max_pages": 3}]
    assert len(payload["data"]["updated_actors"]) == 1
    assert payload["data"]["total_new_works"] == 1
    assert payload["data"]["updated_actors"][0]["new_works"][0]["platform"] == "javdb"
    assert any(item["category"] == "actor_works" for item in captured["cache_set"])

    actors = load_json(meta_dir / "actors_database.json").get("actors", [])
    saved = find_by_id(actors, actor_id)
    assert saved is not None
    assert saved["last_work_id"] == "AV-9001"
    assert saved["last_work_title"] == "Latest Actor Work"
    assert int(saved["new_work_count"]) == 1


@pytest.mark.integration
def test_actor_new_works_endpoint_returns_items_before_last_work_id(third_party_client, monkeypatch):
    """
    Case Description:
    - Purpose: Guard actor new-works slicing logic after third-party search so only items newer than `last_work_id` are returned.
    - Steps:
      1. Subscribe actor and set `last_work_id`.
      2. Mock `_search_works` with ordered latest-first works.
      3. Call `GET /api/v1/actor/new-works/<actor_id>`.
      4. Assert response includes only works before the stored last id.
    - Expected:
      1. HTTP 200 with business `code=200`.
      2. Response `new_works` contains latest works before boundary id only.
    - History:
      - 2026-03-23: Added actor new-works delta slicing guard.
    """
    client = third_party_client["client"]
    actor_api = third_party_client["actor_api"]
    service = actor_api.actor_service

    subscribe_resp = client.post("/api/v1/actor/subscribe", json={"name": "Actor-TP-New-Works"})
    subscribe_payload = subscribe_resp.get_json()
    assert subscribe_resp.status_code == 200
    assert subscribe_payload["code"] == 200
    actor_id = subscribe_payload["data"]["id"]

    update_resp = client.put(
        "/api/v1/actor/update-last-work",
        json={
            "actor_subscription_id": actor_id,
            "work_id": "AV-1002",
            "work_title": "Known Old Work",
            "new_count": 0,
        },
    )
    update_payload = update_resp.get_json()
    assert update_resp.status_code == 200
    assert update_payload["code"] == 200

    monkeypatch.setattr(
        service,
        "_search_works",
        lambda *_args, **_kwargs: {
            "works": [
                {"id": "AV-1004", "title": "Newest"},
                {"id": "AV-1003", "title": "Second New"},
                {"id": "AV-1002", "title": "Known Old Work"},
                {"id": "AV-1001", "title": "Older"},
            ],
            "has_more": False,
            "page": 1,
        },
    )

    response = client.get(f"/api/v1/actor/new-works/{actor_id}")
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["code"] == 200
    assert [item["id"] for item in payload["data"]["new_works"]] == ["AV-1004", "AV-1003"]


@pytest.mark.integration
def test_actor_works_force_refresh_persists_latest_work_for_subscription_summary(third_party_client, monkeypatch):
    """
    Case Description:
    - Purpose: Guard actor detail refresh write-back contract:
      fetching works from actor detail (`offset=0`) must persist latest work fields for subscription summary display.
    - Steps:
      1. Subscribe actor and get `actor_id`.
      2. Mock `actor_service.get_works_paginated_impl` to return latest-first works.
      3. Call `GET /api/v1/actor/works/<actor_id>?force_refresh=1`.
      4. Verify `actors_database.json` latest work fields are updated.
    - Expected:
      1. HTTP 200 with business `code=200`.
      2. Response returns mocked works.
      3. Persisted actor record updates `last_work_id/last_work_title` from first work item.
    """
    client = third_party_client["client"]
    actor_api = third_party_client["actor_api"]
    meta_dir = third_party_client["meta_dir"]
    service = actor_api.actor_service

    subscribe_resp = client.post("/api/v1/actor/subscribe", json={"name": "Actor-TP-Detail-Sync"})
    subscribe_payload = subscribe_resp.get_json()
    assert subscribe_resp.status_code == 200
    assert subscribe_payload["code"] == 200
    actor_id = subscribe_payload["data"]["id"]

    def fake_paginated(_actor, offset=0, limit=5, force_refresh=False):
        return _ok_result(
            {
                "creator": {"id": actor_id, "name": "Actor-TP-Detail-Sync"},
                "works": [
                    {"id": "AV-7701", "title": "Actor Detail Latest", "platform": "javdb"},
                    {"id": "AV-7700", "title": "Actor Detail Old", "platform": "javbus"},
                ],
                "total": 2,
                "offset": offset,
                "limit": limit,
                "has_more": False,
            }
        )

    monkeypatch.setattr(service, "get_works_paginated_impl", fake_paginated)

    response = client.get(
        f"/api/v1/actor/works/{actor_id}",
        query_string={"offset": 0, "limit": 5, "force_refresh": 1},
    )
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["code"] == 200
    assert payload["data"]["works"][0]["id"] == "AV-7701"

    actors = load_json(meta_dir / "actors_database.json").get("actors", [])
    saved = find_by_id(actors, actor_id)
    assert saved is not None
    assert saved["last_work_id"] == "AV-7701"
    assert saved["last_work_title"] == "Actor Detail Latest"


@pytest.mark.integration
def test_actor_works_route_forwards_offset_limit_to_service(third_party_client, monkeypatch):
    """
    Case Description:
    - Purpose: Guard `/api/v1/actor/works/<actor_id>` route contract so pagination parameters are forwarded unchanged.
    - Steps:
      1. Mock `actor_service.get_actor_works_paginated` and record arguments.
      2. Call `GET /api/v1/actor/works/<actor_id>?offset=4&limit=6`.
      3. Assert forwarded arguments and response mapping.
    - Expected:
      1. HTTP 200 with business `code=200`.
      2. Service receives `(actor_id, 4, 6, cache_only=false, force_refresh=false)`.
      3. Response includes mocked works payload.
    - History:
      - 2026-03-23: Added actor works route paging contract guard.
    """
    client = third_party_client["client"]
    actor_api = third_party_client["actor_api"]
    captured = {}

    def fake_get(actor_id, offset=0, limit=5, cache_only=False, force_refresh=False):
        captured["actor_id"] = actor_id
        captured["offset"] = offset
        captured["limit"] = limit
        captured["cache_only"] = cache_only
        captured["force_refresh"] = force_refresh
        return _ok_result(
            {
                "actor": {"id": actor_id, "name": "Route Actor"},
                "works": [{"id": "W-ACT-1"}],
                "total": 1,
                "offset": offset,
                "limit": limit,
                "has_more": False,
            }
        )

    monkeypatch.setattr(actor_api.actor_service, "get_actor_works_paginated", fake_get)

    response = client.get("/api/v1/actor/works/actor-route-1", query_string={"offset": 4, "limit": 6})
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["code"] == 200
    assert captured == {
        "actor_id": "actor-route-1",
        "offset": 4,
        "limit": 6,
        "cache_only": False,
        "force_refresh": False,
    }
    assert payload["data"]["works"][0]["id"] == "W-ACT-1"
