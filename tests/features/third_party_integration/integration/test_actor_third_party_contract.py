from __future__ import annotations

import base64
import uuid
from io import BytesIO
from types import SimpleNamespace

import pytest
from PIL import Image

from tests.shared.runtime_data import find_by_id, load_json

def _ok_result(data=None, message="ok"):
    return SimpleNamespace(success=True, data=data, message=message)


def _unique_actor_name(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


@pytest.mark.integration
def test_actor_service_search_works_forwards_adapter_calls_and_interleaves_results(fake_third_party_client, monkeypatch):
    """
    Case Description:
    - Purpose: Guard actor service third-party contract in `_search_works`: adapter selection, call parameters, and cross-platform merge order.
    - Steps:
      1. Mock actor service protocol adapter loader for `video.alpha/video.beta`.
      2. Call `actor_service._search_works("Mina", page=2, max_pages=4)`.
      3. Verify adapter calls and merged result order.
    - Expected:
      1. Adapters are called with page/max_pages forwarded unchanged.
      2. Returned works include both platforms.
      3. Result order is grouped by platform: all `va` first, then `vb`.
    - History:
      - 2026-03-23: Added actor service third-party merge contract coverage.
    """
    actor_api = fake_third_party_client["actor_api"]
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
            if self.platform == "va":
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
                        "cover_url": "https://www.vb.com/pics/thumb/c0ou.jpg",
                    },
                ],
                "has_next": False,
            }

    monkeypatch.setattr(service, "_get_video_adapter", lambda platform: FakeAdapter(platform))

    result = service._search_works("Mina", page=2, max_pages=4)
    works = result.get("works", [])

    assert len(calls) == 2
    assert calls[0] == {"platform": "va", "creator_name": "Mina", "page": 2, "max_pages": 4}
    assert calls[1] == {"platform": "vb", "creator_name": "Mina", "page": 2, "max_pages": 4}
    assert [item["id"] for item in works] == ["DB-1", "DB-2", "BUS-1"]
    assert [item["platform"] for item in works] == ["va", "va", "vb"]
    assert result["has_more"] is True
    assert result["page"] == 2


@pytest.mark.integration
def test_actor_service_search_works_accepts_va_actor_works_result_key(fake_third_party_client, monkeypatch):
    """
    Case Description:
    - Purpose: Guard VA actor-works branch compatibility: `get_actor_works` may return `works` (not `videos`).
    - Steps:
      1. Mock va adapter to provide `search_actor` + `get_actor_works` returning `works`.
      2. Mock vb adapter to provide `search_videos`.
      3. Call `actor_service._search_works("Mina", page=1, max_pages=2)`.
    - Expected:
      1. VA works are not dropped.
      2. Output keeps grouped platform order: va first, then vb.
    """
    actor_api = fake_third_party_client["actor_api"]
    service = actor_api.actor_service
    captured = {"va_get_actor_works": 0, "va_search_videos": 0}

    class FakeAlphaAdapter:
        def search_actor(self, actor_name):
            assert actor_name == "Mina"
            return [{"id": "actor-mina", "name": "Mina"}]

        def get_actor_works(self, actor_id, page=1, max_pages=1):
            captured["va_get_actor_works"] += 1
            assert actor_id == "actor-mina"
            assert page == 1
            assert max_pages == 2
            return {
                "works": [
                    {"video_id": "DB-A1", "title": "DB Actor One", "cover_url": "https://img/db-a1.jpg"},
                ],
                "has_next": False,
            }

        def search_videos(self, *_args, **_kwargs):
            captured["va_search_videos"] += 1
            return {"videos": []}

    class FakeBetaAdapter:
        def search_videos(self, actor_name, page=1, max_pages=1):
            assert actor_name == "Mina"
            assert page == 1
            assert max_pages == 2
            return {
                "videos": [
                    {"code": "BUS-A1", "title": "BUS Actor One", "cover_url": "https://www.vb.com/pics/thumb/a9mj.jpg"},
                ],
                "has_next": False,
            }

    def fake_get_video_adapter(platform):
        if platform == "va":
            return FakeAlphaAdapter()
        return FakeBetaAdapter()

    monkeypatch.setattr(service, "_get_video_adapter", fake_get_video_adapter)

    result = service._search_works("Mina", page=1, max_pages=2)
    works = result.get("works", [])

    assert [item["id"] for item in works] == ["DB-A1", "BUS-A1"]
    assert [item["platform"] for item in works] == ["va", "vb"]
    assert captured["va_get_actor_works"] == 1
    assert captured["va_search_videos"] == 0


@pytest.mark.integration
def test_actor_service_prefers_subscribed_actor_ref_for_person_works(fake_third_party_client, monkeypatch):
    client = fake_third_party_client["client"]
    actor_api = fake_third_party_client["actor_api"]
    service = actor_api.actor_service
    captured = {"actor_works": []}
    actor_name = _unique_actor_name("Actor-TP-Ref-Works")

    monkeypatch.setattr(service, "_resolve_actor_refs", lambda _name: [])
    subscribe_resp = client.post(
        "/api/v1/actor/subscribe",
        json={
            "name": actor_name,
            "actor_refs": [
                {
                    "platform": "va",
                    "actor_id": "0R1n3",
                    "actor_name": actor_name,
                    "actor_url": "https://va.com/actors/0R1n3",
                }
            ],
        },
    )
    assert subscribe_resp.status_code == 200
    assert subscribe_resp.get_json()["code"] == 200
    actor = service._actor_repo.get_by_id(subscribe_resp.get_json()["data"]["id"])

    class FakeAlphaAdapter:
        def search_actor(self, _actor_name):
            raise AssertionError("subscribed actor_refs should avoid name-based actor lookup")

        def get_actor_works(self, actor_id, page=1, max_pages=1):
            captured["actor_works"].append({"actor_id": actor_id, "page": page, "max_pages": max_pages})
            return {
                "works": [
                    {"video_id": "VA-REF-1", "title": "Actor Ref Work", "cover_url": "https://img/ref.jpg"},
                ],
                "has_next": True,
            }

        def search_videos(self, *_args, **_kwargs):
            raise AssertionError("actor_refs should use person.works before keyword search")

    class EmptyAdapter:
        def search_videos(self, *_args, **_kwargs):
            return {"videos": [], "has_next": False}

    monkeypatch.setattr(
        service,
        "_get_video_adapter",
        lambda platform: FakeAlphaAdapter() if platform == "va" else EmptyAdapter(),
    )

    result = service._search_works_for_creator(actor, page=2, max_pages=1)

    assert captured["actor_works"] == [{"actor_id": "0R1n3", "page": 2, "max_pages": 1}]
    assert result["works"][0]["id"] == "VA-REF-1"
    assert result["works"][0]["platform"] == "va"
    assert result["has_more"] is True


@pytest.mark.integration
def test_actor_works_route_reads_cached_middle_page_and_fetches_only_provisional_last_page(fake_third_party_client, monkeypatch):
    client = fake_third_party_client["client"]
    actor_api = fake_third_party_client["actor_api"]
    service = actor_api.actor_service
    actor_name = _unique_actor_name("Actor-TP-Cache-Paging")
    captured = {"actor_works": []}

    monkeypatch.setattr(service, "_resolve_actor_refs", lambda _name: [])
    monkeypatch.setattr(service, "_list_video_search_platforms", lambda: ["va"])
    monkeypatch.setattr(service, "_list_video_person_platforms", lambda: ["va"])

    subscribe_resp = client.post(
        "/api/v1/actor/subscribe",
        json={
            "name": actor_name,
            "actor_refs": [
                {
                    "platform": "va",
                    "actor_id": "actor-cache-paging",
                    "actor_name": actor_name,
                    "actor_url": "https://va.com/actors/actor-cache-paging",
                }
            ],
        },
    )
    assert subscribe_resp.status_code == 200
    actor_id = subscribe_resp.get_json()["data"]["id"]

    class FakeAlphaAdapter:
        def get_actor_works(self, actor_id, page=1, max_pages=1):
            captured["actor_works"].append({"actor_id": actor_id, "page": page, "max_pages": max_pages})
            start = (page - 1) * 40
            return {
                "works": [
                    {
                        "video_id": f"DB-CACHE-{index:03d}",
                        "title": f"Cached Actor Work {index:03d}",
                        "cover_url": f"https://img/cache-{index:03d}.jpg",
                    }
                    for index in range(start, start + 40)
                ],
                "has_next": page < 2,
            }

        def search_videos(self, *_args, **_kwargs):
            raise AssertionError("actor_refs should use person.works")

    monkeypatch.setattr(service, "_get_video_adapter", lambda _platform: FakeAlphaAdapter())

    first_resp = client.get(
        f"/api/v1/actor/works/{actor_id}",
        query_string={"offset": 0, "limit": 20, "force_refresh": 1},
    )
    assert first_resp.status_code == 200
    assert captured["actor_works"] == [
        {"actor_id": "actor-cache-paging", "page": 1, "max_pages": 1}
    ]

    cached_resp = client.get(
        f"/api/v1/actor/works/{actor_id}",
        query_string={"offset": 20, "limit": 20, "cache_only": 1},
    )
    cached_payload = cached_resp.get_json()
    assert cached_resp.status_code == 200
    assert [item["id"] for item in cached_payload["data"]["works"][:2]] == ["DB-CACHE-020", "DB-CACHE-021"]
    assert captured["actor_works"] == [
        {"actor_id": "actor-cache-paging", "page": 1, "max_pages": 1}
    ]

    last_resp = client.get(
        f"/api/v1/actor/works/{actor_id}",
        query_string={"offset": 40, "limit": 20},
    )
    last_payload = last_resp.get_json()
    assert last_resp.status_code == 200
    assert [item["id"] for item in last_payload["data"]["works"][:2]] == ["DB-CACHE-040", "DB-CACHE-041"]
    assert captured["actor_works"] == [
        {"actor_id": "actor-cache-paging", "page": 1, "max_pages": 1},
        {"actor_id": "actor-cache-paging", "page": 2, "max_pages": 1},
    ]


@pytest.mark.integration
def test_actor_search_works_route_forwards_offset_limit_to_service(fake_third_party_client, monkeypatch):
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
    client = fake_third_party_client["client"]
    actor_api = fake_third_party_client["actor_api"]
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
def test_actor_subscribe_accepts_protocol_actor_refs(fake_third_party_client, monkeypatch):
    client = fake_third_party_client["client"]
    actor_api = fake_third_party_client["actor_api"]
    service = actor_api.actor_service
    actor_name = _unique_actor_name("Actor-TP-Ref-Subscribe")

    monkeypatch.setattr(service, "_resolve_actor_refs", lambda _name: [])

    response = client.post(
        "/api/v1/actor/subscribe",
        json={
            "name": actor_name,
            "actor_refs": [
                {
                    "platform": "va",
                    "actor_id": "actor-ref-subscribe",
                    "actor_name": actor_name,
                    "actor_url": "https://va.com/actors/actor-ref-subscribe",
                }
            ],
        },
    )
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["code"] == 200
    assert payload["data"]["actor_id"] == "actor-ref-subscribe"
    assert payload["data"]["actor_refs"][0]["platform"] == "va"

    saved = service._actor_repo.get_by_id(payload["data"]["id"]).to_dict()
    assert saved["actor_id"] == "actor-ref-subscribe"
    assert saved["actor_refs"][0]["actor_id"] == "actor-ref-subscribe"


@pytest.mark.integration
def test_actor_subscribe_accepts_manual_actor_url(fake_third_party_client, monkeypatch):
    client = fake_third_party_client["client"]
    actor_api = fake_third_party_client["actor_api"]
    service = actor_api.actor_service
    actor_name = _unique_actor_name("Actor-TP-Manual-Url")

    monkeypatch.setattr(service, "_resolve_actor_refs", lambda _name: [])

    response = client.post(
        "/api/v1/actor/subscribe",
        json={
            "name": actor_name,
            "platform": "va",
            "actor_url": "https://va.com/actors/J2EwW",
        },
    )
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["code"] == 200
    assert payload["data"]["actor_id"] == "J2EwW"
    assert payload["data"]["actor_refs"][0]["platform"] == "va"
    assert payload["data"]["actor_refs"][0]["actor_url"] == "https://va.com/actors/J2EwW"

    saved = service._actor_repo.get_by_id(payload["data"]["id"]).to_dict()
    assert saved["actor_id"] == "J2EwW"
    assert saved["actor_refs"][0]["actor_id"] == "J2EwW"


@pytest.mark.integration
def test_actor_videos_route_forwards_actor_name_to_service(fake_third_party_client, monkeypatch):
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
    client = fake_third_party_client["client"]
    actor_api = fake_third_party_client["actor_api"]
    captured = {}

    def fake_get_actor_videos(actor_name):
        captured["actor_name"] = actor_name
        return _ok_result(
            [
                {
                    "id": "VA-ACT-100",
                    "title": "Actor Route Video",
                    "platform": "va",
                }
            ]
        )

    monkeypatch.setattr(actor_api.actor_service, "get_actor_videos", fake_get_actor_videos)

    response = client.get("/api/v1/actor/videos", query_string={"actor_name": "Yui"})
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["code"] == 200
    assert captured == {"actor_name": "Yui"}
    assert payload["data"][0]["id"] == "VA-ACT-100"
    assert payload["data"][0]["plugin_id"] == "video.alpha"
    assert payload["data"][0]["display"]["badge"]["label"] == "VA"


@pytest.mark.integration
def test_actor_check_updates_persists_latest_work_and_calls_search_contract(fake_third_party_client, monkeypatch):
    """
    Case Description:
    - Purpose: Guard actor update-check third-party chain: search contract (`page/max_pages`) and persisted latest work metadata.
    - Steps:
      1. Subscribe a test actor and get `actor_id`.
      2. Mock cache manager and `actor_service._search_works_for_creator`.
      3. Call `POST /api/v1/actor/check-updates`.
      4. Assert search call parameters and `actors_database.json` persisted fields.
    - Expected:
      1. HTTP 200 with business `code=200`.
      2. `_search_works_for_creator` is called with `page=1,max_pages=3`.
      3. Persisted actor record updates `last_work_id/last_work_title/new_work_count`.
    - History:
      - 2026-03-23: Added actor update-check persistence contract guard.
    """
    client = fake_third_party_client["client"]
    actor_api = fake_third_party_client["actor_api"]
    service = actor_api.actor_service
    captured = {"search": [], "cache_set": []}
    actor_name = _unique_actor_name("Actor-TP-Check")
    monkeypatch.setattr(service, "_resolve_actor_refs", lambda _name: [])

    subscribe_resp = client.post(
        "/api/v1/actor/subscribe",
        json={
            "name": actor_name,
            "actor_refs": [
                {
                    "platform": "va",
                    "actor_id": "actor-check-01",
                    "actor_name": actor_name,
                    "actor_url": "https://va.com/actors/actor-check-01",
                }
            ],
        },
    )
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

    def fake_search(actor, page=1, max_pages=1):
        captured["search"].append(
            {
                "actor_name": actor.name,
                "actor_refs": list(actor.actor_refs or []),
                "page": page,
                "max_pages": max_pages,
            }
        )
        return {
            "works": [
                {"id": "AV-9001", "title": "Latest Actor Work", "platform": "va"},
                {"id": "AV-9000", "title": "Old Actor Work", "platform": "vb"},
            ],
            "has_more": False,
            "page": page,
        }

    monkeypatch.setattr(service, "_cache_manager", FakeCache())
    monkeypatch.setattr(service, "_search_works_for_creator", fake_search)

    response = client.post("/api/v1/actor/check-updates", json={"actor_id": actor_id})
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["code"] == 200
    assert captured["search"] == [
        {
            "actor_name": actor_name,
            "actor_refs": [
                {
                    "platform": "va",
                    "actor_id": "actor-check-01",
                    "actor_name": actor_name,
                    "actor_url": "https://va.com/actors/actor-check-01",
                }
            ],
            "page": 1,
            "max_pages": 3,
        }
    ]
    assert len(payload["data"]["updated_actors"]) == 1
    assert payload["data"]["total_new_works"] == 1
    assert payload["data"]["updated_actors"][0]["new_works"][0]["platform"] == "va"
    assert any(item["category"] == "actor_works" for item in captured["cache_set"])

    saved = service._actor_repo.get_by_id(actor_id).to_dict()
    assert saved["last_work_id"] == "AV-9001"
    assert saved["last_work_title"] == "Latest Actor Work"
    assert int(saved["new_work_count"]) == 1


@pytest.mark.integration
def test_actor_new_works_endpoint_returns_items_before_last_work_id(fake_third_party_client, monkeypatch):
    """
    Case Description:
    - Purpose: Guard actor new-works slicing logic after third-party search so only items newer than `last_work_id` are returned.
    - Steps:
      1. Subscribe actor and set `last_work_id`.
      2. Mock `_search_works_for_creator` with ordered latest-first works.
      3. Call `GET /api/v1/actor/new-works/<actor_id>`.
      4. Assert response includes only works before the stored last id.
    - Expected:
      1. HTTP 200 with business `code=200`.
      2. Response `new_works` contains latest works before boundary id only.
    - History:
      - 2026-03-23: Added actor new-works delta slicing guard.
    """
    client = fake_third_party_client["client"]
    actor_api = fake_third_party_client["actor_api"]
    service = actor_api.actor_service
    actor_name = _unique_actor_name("Actor-TP-New-Works")

    subscribe_resp = client.post("/api/v1/actor/subscribe", json={"name": actor_name})
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
        "_search_works_for_creator",
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
def test_actor_works_force_refresh_persists_latest_work_for_subscription_summary(fake_third_party_client, monkeypatch):
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
    client = fake_third_party_client["client"]
    actor_api = fake_third_party_client["actor_api"]
    service = actor_api.actor_service
    actor_name = _unique_actor_name("Actor-TP-Detail-Sync")

    subscribe_resp = client.post("/api/v1/actor/subscribe", json={"name": actor_name})
    subscribe_payload = subscribe_resp.get_json()
    assert subscribe_resp.status_code == 200
    assert subscribe_payload["code"] == 200
    actor_id = subscribe_payload["data"]["id"]

    def fake_paginated(_actor, offset=0, limit=5, force_refresh=False):
        return _ok_result(
            {
                "creator": {"id": actor_id, "name": actor_name},
                "works": [
                    {"id": "AV-7701", "title": "Actor Detail Latest", "platform": "va"},
                    {"id": "AV-7700", "title": "Actor Detail Old", "platform": "vb"},
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
    assert payload["data"]["works"][0]["plugin_id"] == "video.alpha"
    assert payload["data"]["works"][1]["plugin_id"] == "video.beta"

    saved = service._actor_repo.get_by_id(actor_id).to_dict()
    assert saved["last_work_id"] == "AV-7701"
    assert saved["last_work_title"] == "Actor Detail Latest"


@pytest.mark.integration
def test_actor_works_route_forwards_offset_limit_to_service(fake_third_party_client, monkeypatch):
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
    client = fake_third_party_client["client"]
    actor_api = fake_third_party_client["actor_api"]
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



