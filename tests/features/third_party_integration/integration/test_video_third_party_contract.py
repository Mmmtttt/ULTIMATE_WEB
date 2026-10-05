from __future__ import annotations

import importlib
import time
from types import SimpleNamespace

import pytest

from tests.shared.runtime_data import load_json, save_json


def _ok_result(data=None, message="ok"):
    return SimpleNamespace(success=True, data=data, message=message)


def _error_result(message="error"):
    return SimpleNamespace(success=False, data=None, message=message)


@pytest.mark.integration
def test_video_platform_health_status_generic_route_reads_manifest_bound_config(fake_third_party_client):
    client = fake_third_party_client["client"]
    config_path = fake_third_party_client["third_party_config_path"]

    config = load_json(config_path)
    config.setdefault("adapters", {}).setdefault("video_alpha", {})["cookies"] = {
        "_session": "sess-generic",
        "over18": "1",
    }
    save_json(config_path, config)

    response = client.get("/api/v1/video/third-party/va/health-status")
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["code"] == 200
    assert payload["data"]["configured"] is True
    assert payload["data"]["has_session_cookie"] is True


@pytest.mark.integration
def test_video_third_party_search_all_forwards_adapter_calls(fake_third_party_client, monkeypatch):
    """
    用例描述:
    - 用例目的: 看护视频远程搜索接口到第三方适配器的调用契约，防止平台分发/分页参数透传错误。
    - 测试步骤:
      1. mock get_video_adapter，返回可记录入参的假适配器。
      2. 调用 GET /api/v1/video/third-party/search?platform=all&page=2。
      3. 断言 va/vb 均被调用且 page/max_pages 参数正确。
    - 预期结果:
      1. HTTP 200 且业务 code=200。
      2. 两个平台调用完整，返回数据包含 platform 字段并合并到同一结果集。
    - 历史变更:
      - 2026-03-23: 初始创建，覆盖视频第三方搜索调用契约。
    """
    client = fake_third_party_client["client"]
    config_path = fake_third_party_client["third_party_config_path"]
    video_api = fake_third_party_client["video_api"]
    config = load_json(config_path)
    config.setdefault("adapters", {}).setdefault("video_alpha", {}).update(
            {"enabled": True, "cookies": {"_session": "test-session"}}
    )
    save_json(config_path, config)
    calls = []

    class FakeAdapter:
        def __init__(self, platform):
            self.platform = platform

        def search_videos(self, keyword, page=1, max_pages=1):
            calls.append(
                {
                    "platform": self.platform,
                    "keyword": keyword,
                    "page": page,
                    "max_pages": max_pages,
                }
            )
            return {
                "videos": [
                    {
                        "id": f"{self.platform}-video-1",
                        "title": f"{self.platform}-title",
                        "cover_url": "https://www.vb.com/pics/abc.jpg",
                    }
                ],
                "page": page,
                "has_next": self.platform == "va",
                "total_pages": 3,
            }

    monkeypatch.setattr(video_api, "get_video_adapter", lambda platform, *a, **k: FakeAdapter(platform))

    response = client.get(
        "/api/v1/video/third-party/search",
        query_string={"keyword": "star", "platform": "all", "page": 2},
    )
    payload = response.get_json()
    assert response.status_code == 200
    assert payload["code"] == 200
    data = payload["data"]
    assert len(data["videos"]) == 2
    assert data["has_next"] is True
    assert {item.get("plugin_id") for item in data["videos"]} == {"video.alpha", "video.beta"}
    display_by_platform = {item.get("platform"): (((item.get("display") or {}).get("cover") or {})) for item in data["videos"]}
    assert display_by_platform["va"].get("aspect_ratio") == "16 / 9"
    assert display_by_platform["vb"].get("fit") == "contain"

    by_platform = {item["platform"]: item for item in calls}
    assert set(by_platform.keys()) == {"va", "vb"}
    assert all(item["keyword"] == "star" for item in calls)
    assert all(item["page"] == 2 for item in calls)
    assert all(item["max_pages"] == 1 for item in calls)

@pytest.mark.integration
def test_video_third_party_search_all_skips_unconfigured_va(fake_third_party_client, monkeypatch):
    client = fake_third_party_client["client"]
    config_path = fake_third_party_client["third_party_config_path"]
    video_api = fake_third_party_client["video_api"]
    original_config = load_json(config_path)

    config = load_json(config_path)
    config.setdefault("adapters", {}).setdefault("video_alpha", {}).update(
        {"enabled": True, "cookies": {"_session": ""}}
    )
    save_json(config_path, config)

    calls = []

    class FakeAdapter:
        def __init__(self, platform):
            self.platform = platform

        def search_videos(self, keyword, page=1, max_pages=1):
            calls.append(self.platform)
            return {
                "videos": [{"id": f"{self.platform}-1", "title": f"{self.platform}-title"}],
                "page": page,
                "has_next": False,
                "total_pages": 1,
            }

    monkeypatch.setattr(video_api, "get_video_adapter", lambda platform, *a, **k: FakeAdapter(platform))

    try:
        response = client.get(
            "/api/v1/video/third-party/search",
            query_string={"keyword": "abc", "platform": "all", "page": 1},
        )
        payload = response.get_json()
        assert response.status_code == 200
        assert payload["code"] == 200
        assert calls == ["vb"]
        assert len((payload["data"] or {}).get("videos") or []) == 1
        platform_errors = (payload["data"] or {}).get("platform_errors") or {}
        assert "va" in platform_errors
        assert platform_errors.get("va")
    finally:
        save_json(config_path, original_config)


@pytest.mark.integration
def test_video_platform_search_by_tags_generic_route_dispatches_by_path_platform(fake_third_party_client, monkeypatch):
    client = fake_third_party_client["client"]
    video_api = fake_third_party_client["video_api"]

    def fake_execute(platform_name, capability, params=None):
        assert platform_name == "va"
        assert capability == "taxonomy.tag_search"
        assert params == {"page": 3, "tag_ids": ["c1=23"]}
        return (
            "va",
                SimpleNamespace(plugin_id="video.alpha"),
            {
                "platform": "va",
                "page": 3,
                "has_next": True,
                "total_pages": 5,
                "requested_tag_ids": ["c1=23"],
                "effective_tag_ids": ["c1=23"],
                "invalid_tag_ids": [],
                "overridden_tag_ids": [],
                "videos": [{"video_id": "GEN-1", "title": "Generic Route"}],
            },
        )

    monkeypatch.setattr(video_api, "_execute_video_plugin_capability", fake_execute)

    response = client.get(
        "/api/v1/video/third-party/va/search-by-tags",
        query_string={"tag_ids": "c1=23", "page": 3},
    )
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["code"] == 200
    assert payload["data"]["platform"] == "va"
    assert payload["data"]["page"] == 3
    assert payload["data"]["has_next"] is True


@pytest.mark.integration
def test_video_third_party_detail_actor_search_and_works_contract(fake_third_party_client, monkeypatch):
    """
    用例描述:
    - 用例目的: 看护视频第三方详情/演员搜索/演员作品接口对适配器方法调用契约，防止参数映射错误。
    - 测试步骤:
      1. mock get_video_adapter 返回 detail/search_actor/get_actor_works 可记录入参的假适配器。
      2. 分别调用 detail、actor/search、actor/works 三个接口。
      3. 校验返回值与入参映射。
    - 预期结果:
      1. 三个接口均 HTTP 200 且业务 code=200。
      2. 适配器收到的 video_id/actor_name/actor_id/page 参数正确。
    - 历史变更:
      - 2026-03-23: 初始创建，覆盖第三方详情与演员链路契约。
    """
    client = fake_third_party_client["client"]
    video_api = fake_third_party_client["video_api"]
    calls = {"detail": [], "actor_search": [], "actor_works": []}

    class FakeAdapter:
        def get_video_detail(self, video_id):
            calls["detail"].append(video_id)
            return {"video_id": video_id, "title": "DetailTitle"}

        def search_actor(self, actor_name):
            calls["actor_search"].append(actor_name)
            return [{"id": "A-1", "name": actor_name}]

        def get_actor_works(self, actor_id, page=1, max_pages=1):
            calls["actor_works"].append({"actor_id": actor_id, "page": page, "max_pages": max_pages})
            return {"page": page, "has_next": False, "total_pages": 1, "works": [{"id": "W-1", "cover_url": "https://a.b/c.jpg"}]}

    monkeypatch.setattr(video_api, "get_video_adapter", lambda *args, **kwargs: FakeAdapter())

    detail_resp = client.get("/api/v1/video/third-party/detail", query_string={"video_id": "X-001", "platform": "va"})
    detail_payload = detail_resp.get_json()
    assert detail_resp.status_code == 200
    assert detail_payload["code"] == 200
    assert detail_payload["data"]["video_id"] == "X-001"
    assert detail_payload["data"]["plugin_id"] == "video.alpha"

    actor_search_resp = client.get(
        "/api/v1/video/third-party/actor/search",
        query_string={"actor_name": "Mina", "platform": "va"},
    )
    actor_search_payload = actor_search_resp.get_json()
    assert actor_search_resp.status_code == 200
    assert actor_search_payload["code"] == 200
    assert actor_search_payload["data"][0]["name"] == "Mina"

    actor_works_resp = client.get(
        "/api/v1/video/third-party/actor/works",
        query_string={"actor_id": "ACT-9", "page": 3, "platform": "va"},
    )
    actor_works_payload = actor_works_resp.get_json()
    assert actor_works_resp.status_code == 200
    assert actor_works_payload["code"] == 200
    assert actor_works_payload["data"]["page"] == 3
    assert actor_works_payload["data"]["works"][0]["plugin_id"] == "video.alpha"

    assert calls["detail"] == ["X-001"]
    assert calls["actor_search"] == ["Mina"]
    assert calls["actor_works"] == [{"actor_id": "ACT-9", "page": 3, "max_pages": 1}]


@pytest.mark.integration
def test_video_third_party_import_home_normalizes_id_and_calls_expected_dependencies(fake_third_party_client, monkeypatch):
    """
    用例描述:
    - 用例目的: 看护视频第三方导入接口在 ID 规范化、第三方详情查询、导入服务调用、资源缓存调度上的契约。
    - 测试步骤:
      1. mock get_video_adapter/get_video_detail，返回带 code/tags/预览地址的详情。
      2. mock TagAppService、video_service.import_video、apply_recent_import_tags、_schedule_video_asset_cache。
      3. 调用 POST /api/v1/video/third-party/import，传入 video_id=VA_ABP123,target=home。
      4. 校验各依赖收到的参数和值映射。
    - 预期结果:
      1. HTTP 200 且业务 code=200。
      2. adapter.get_video_detail 收到规范化后的 ABP123。
      3. import_video 收到前缀化后的 ID（VAABP123）和正确 code。
      4. 资源缓存调度收到 source=local 与对应资源参数。
    - 历史变更:
      - 2026-03-23: 初始创建，覆盖第三方导入核心契约。
    """
    client = fake_third_party_client["client"]
    video_api = fake_third_party_client["video_api"]
    tag_service_module = __import__("application.tag_app_service", fromlist=["TagAppService"])

    adapter_calls = {"detail": []}
    import_payloads = []
    schedule_calls = []

    class FakeAdapter:
        def get_video_detail(self, video_id):
            adapter_calls["detail"].append(video_id)
            return {
                "video_id": video_id,
                "title": "ABP123 title",
                "code": "ABP-123",
                "actors": ["Actor-X"],
                "tags": ["TagA"],
                "cover_url": "https://assets.example/cover.jpg",
                "thumbnail_images": ["https://assets.example/t1.jpg"],
                "preview_video": "https://assets.example/preview.m3u8",
                "magnets": [],
            }

    class FakeTagService:
        def get_tag_list(self, *_args, **_kwargs):
            return _ok_result([{"id": "tag_1", "name": "TagA"}])

        def create_tag(self, tag_name, *_args, **_kwargs):
            return _ok_result({"id": f"created_{tag_name}"})

    monkeypatch.setattr(video_api, "get_video_adapter", lambda *args, **kwargs: FakeAdapter())
    monkeypatch.setattr(tag_service_module, "TagAppService", FakeTagService)

    monkeypatch.setattr(video_api.video_service, "get_video_by_code", lambda code: _error_result("not found"))
    monkeypatch.setattr(
        video_api.video_service,
        "import_video",
        lambda payload: import_payloads.append(payload) or _ok_result(payload, "ok"),
    )
    monkeypatch.setattr(
        video_api.video_service,
        "apply_recent_import_tags",
        lambda ids, source="local", clear_previous=True: _ok_result({"ids": ids, "source": source}),
    )
    monkeypatch.setattr(
        video_api,
        "_schedule_video_asset_cache",
        lambda **kwargs: schedule_calls.append(kwargs),
    )

    response = client.post(
        "/api/v1/video/third-party/import",
        json={"video_id": "VA_ABP123", "target": "home", "platform": "va"},
    )
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["code"] == 200
    assert adapter_calls["detail"] == ["ABP123"]

    assert len(import_payloads) == 1
    imported = import_payloads[0]
    assert imported["id"] == "VAABP123"
    assert imported["code"] == "ABP-123"
    assert imported["tag_ids"] == ["tag_1"]
    assert imported["creator"] == "Actor-X"

    assert len(schedule_calls) == 1
    assert schedule_calls[0]["video_id"] == "VAABP123"
    assert schedule_calls[0]["source"] == "local"
    assert schedule_calls[0]["allow_preview_video"] is True


@pytest.mark.integration
def test_video_third_party_import_home_falls_back_to_get_video_by_code(fake_third_party_client, monkeypatch):
    """
    Case Description:
    - Purpose: Guard fallback contract when `get_video_detail` misses and adapter uses `get_video_by_code`.
    - Steps:
      1. Mock adapter `get_video_detail` -> None and `get_video_by_code` -> valid detail with canonical `video_id`.
      2. Mock import and cache scheduling dependencies.
      3. Call `POST /api/v1/video/third-party/import` to home target.
      4. Verify fallback call path and imported ID mapping.
    - Expected:
      1. HTTP 200 with business `code=200`.
      2. Adapter receives fallback call with original lookup value.
      3. Imported record uses canonical `video_id` returned by fallback detail.
    - History:
      - 2026-03-23: Added fallback branch coverage for third-party import.
    """
    client = fake_third_party_client["client"]
    video_api = fake_third_party_client["video_api"]
    tag_service_module = __import__("application.tag_app_service", fromlist=["TagAppService"])
    calls = {"detail": [], "fallback": []}
    imported_payloads = []

    class FakeAdapter:
        def get_video_detail(self, video_id):
            calls["detail"].append(video_id)
            return None

        def get_video_by_code(self, code):
            calls["fallback"].append(code)
            return {
                "video_id": "ABP-123",
                "title": "Fallback title",
                "code": "ABP-123",
                "actors": ["Actor-Y"],
                "tags": ["TagA"],
                "cover_url": "https://assets.example/cover-fallback.jpg",
                "thumbnail_images": [],
                "preview_video": "https://assets.example/preview-fallback.m3u8",
                "magnets": [],
            }

    class FakeTagService:
        def get_tag_list(self, *_args, **_kwargs):
            return _ok_result([{"id": "tag_1", "name": "TagA"}])

        def create_tag(self, tag_name, *_args, **_kwargs):
            return _ok_result({"id": f"created_{tag_name}"})

    monkeypatch.setattr(video_api, "get_video_adapter", lambda *args, **kwargs: FakeAdapter())
    monkeypatch.setattr(tag_service_module, "TagAppService", FakeTagService)
    monkeypatch.setattr(video_api.video_service, "get_video_by_code", lambda _code: _error_result("not found"))
    monkeypatch.setattr(
        video_api.video_service,
        "import_video",
        lambda payload: imported_payloads.append(payload) or _ok_result(payload),
    )
    monkeypatch.setattr(
        video_api.video_service,
        "apply_recent_import_tags",
        lambda ids, source="local", clear_previous=True: _ok_result({"ids": ids, "source": source}),
    )
    monkeypatch.setattr(video_api, "_schedule_video_asset_cache", lambda **_kwargs: None)

    response = client.post(
        "/api/v1/video/third-party/import",
        json={"video_id": "ABP123", "target": "home", "platform": "va"},
    )
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["code"] == 200
    assert calls["detail"] == ["ABP123"]
    assert calls["fallback"] == ["ABP123"]
    assert imported_payloads[0]["id"] == "VAABP-123"
    assert imported_payloads[0]["code"] == "ABP-123"


@pytest.mark.integration
def test_video_third_party_import_home_rejects_duplicate_code(fake_third_party_client, monkeypatch):
    """
    Case Description:
    - Purpose: Guard duplicate branch for home import: if local library already has same video `code`,
      third-party import must fail fast and skip downstream write calls.
    - Steps:
      1. Mock adapter detail with code `ABP-123`.
      2. Mock `video_service.get_video_by_code` to return existing record.
      3. Call `POST /api/v1/video/third-party/import` to home target.
      4. Ensure `import_video` is not executed.
    - Expected:
      1. HTTP 200 with business `code=400`.
      2. Error message indicates duplicate/existing video.
      3. No import write call occurs.
    - History:
      - 2026-03-23: Added duplicate-code guard for home third-party import.
    """
    client = fake_third_party_client["client"]
    video_api = fake_third_party_client["video_api"]
    called = {"import_video": 0}

    class FakeAdapter:
        def get_video_detail(self, _video_id):
            return {
                "video_id": "ABP123",
                "title": "Duplicate Video",
                "code": "ABP-123",
                "actors": ["Actor-D"],
                "tags": ["TagA"],
                "cover_url": "https://assets.example/dup-cover.jpg",
                "thumbnail_images": [],
                "preview_video": "",
                "magnets": [],
            }

    monkeypatch.setattr(video_api, "get_video_adapter", lambda *_args, **_kwargs: FakeAdapter())
    monkeypatch.setattr(
        video_api.video_service,
        "get_video_by_code",
        lambda _code: _ok_result({"id": "VAEXIST001", "code": "ABP-123"}),
    )
    monkeypatch.setattr(
        video_api.video_service,
        "import_video",
        lambda _payload: called.__setitem__("import_video", called["import_video"] + 1) or _ok_result({}),
    )

    response = client.post(
        "/api/v1/video/third-party/import",
        json={"video_id": "ABP123", "target": "home", "platform": "va"},
    )
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["code"] == 400
    assert "存在" in str(payload["msg"])
    assert called["import_video"] == 0


@pytest.mark.integration
def test_video_third_party_import_recommendation_rejects_duplicate_code(fake_third_party_client, monkeypatch):
    """
    Case Description:
    - Purpose: Guard duplicate branch for recommendation import: existing preview DB code should block duplicate writes.
    - Steps:
      1. Seed isolated `video_recommendations_database.json` with code `DUP-001`.
      2. Mock adapter detail returning the same code.
      3. Call `POST /api/v1/video/third-party/import` with target recommendation.
      4. Assert API rejects duplicate and DB size remains unchanged.
    - Expected:
      1. HTTP 200 with business `code=400`.
      2. Error message indicates duplicate.
      3. Recommendation DB keeps a single `DUP-001` entry.
    - History:
      - 2026-03-23: Added duplicate-code guard for recommendation third-party import.
    """
    client = fake_third_party_client["client"]
    video_api = fake_third_party_client["video_api"]
    meta_dir = fake_third_party_client["meta_dir"]
    db_path = meta_dir / "video_recommendations_database.json"

    db_payload = load_json(db_path)
    db_payload.setdefault("video_recommendations", []).append(
        {
            "id": "VADUP001",
            "title": "Existing Dup",
            "code": "DUP-001",
            "actors": [],
            "tag_ids": [],
            "list_ids": [],
            "create_time": "2026-03-23T00:00:00",
            "last_access_time": "2026-03-23T00:00:00",
            "is_deleted": False,
        }
    )
    save_json(db_path, db_payload)

    class FakeAdapter:
        def get_video_detail(self, _video_id):
            return {
                "video_id": "DUP001",
                "title": "Duplicate Recommendation",
                "code": "DUP-001",
                "actors": ["Actor-R"],
                "tags": ["TagA"],
                "cover_url": "https://assets.example/dup-rec-cover.jpg",
                "thumbnail_images": [],
                "preview_video": "",
                "magnets": [],
            }

    monkeypatch.setattr(video_api, "get_video_adapter", lambda *_args, **_kwargs: FakeAdapter())

    response = client.post(
        "/api/v1/video/third-party/import",
        json={"video_id": "DUP001", "target": "recommendation", "platform": "va"},
    )
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["code"] == 400
    assert "存在" in str(payload["msg"])

    refreshed = load_json(db_path).get("video_recommendations", [])
    dup_codes = [item for item in refreshed if (item.get("code") or "").strip().upper() == "DUP-001"]
    assert len(dup_codes) == 1


@pytest.mark.integration
def test_preview_video_refresh_route_forwards_required_contract(fake_third_party_client, monkeypatch):
    """
    用例描述:
    - 用例目的: 看护预览视频刷新接口对内部刷新函数的调用契约，防止 source/force_download 参数丢失。
    - 测试步骤:
      1. mock _refresh_preview_video_now 记录 video_id/source/force_download。
      2. 调用 POST /api/v1/video/preview-video/refresh。
      3. 校验接口返回与调用参数。
    - 预期结果:
      1. HTTP 200 且业务 code=200。
      2. _refresh_preview_video_now 收到 force_download=True 与请求 source。
    - 历史变更:
      - 2026-03-23: 初始创建，覆盖在线播放刷新调用契约。
    """
    client = fake_third_party_client["client"]
    video_api = fake_third_party_client["video_api"]
    captured = {}

    def fake_refresh(video_id, source="local", force_download=False):
        captured["video_id"] = video_id
        captured["source"] = source
        captured["force_download"] = force_download
        return {"success": True, "message": "ok", "data": {"id": video_id, "preview_video": "/media/preview.m3u8"}}

    monkeypatch.setattr(video_api, "_refresh_preview_video_now", fake_refresh)

    response = client.post(
        "/api/v1/video/preview-video/refresh",
        json={"video_id": "VA900001", "source": "preview"},
    )
    payload = response.get_json()
    assert response.status_code == 200
    assert payload["code"] == 200
    assert captured == {"video_id": "VA900001", "source": "preview", "force_download": True}


@pytest.mark.integration
def test_video_recommendation_migrate_to_local_task_uses_protocol_resolved_platform(fake_third_party_client, monkeypatch):
    client = fake_third_party_client["client"]
    task_manager_module = importlib.import_module("infrastructure.task_manager")
    captured = {}

    def fake_create_task(
        platform,
        import_type,
        target,
        comic_id=None,
        keyword=None,
        comic_ids=None,
        content_type="comic",
        extra_data=None,
    ):
        captured.update(
            {
                "platform": platform,
                "import_type": import_type,
                "target": target,
                "comic_id": comic_id,
                "keyword": keyword,
                "comic_ids": comic_ids,
                "content_type": content_type,
                "extra_data": extra_data,
            }
        )
        return "task-video-migrate-001"

    monkeypatch.setattr(task_manager_module.task_manager, "create_task", fake_create_task)

    response = client.post(
        "/api/v1/video/recommendation/migrate-to-local",
        json={"video_ids": ["VAABP123", "VB_XYZ777"]},
    )
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["code"] == 200
    assert payload["data"]["task_id"] == "task-video-migrate-001"
    assert captured["platform"] == "VA"
    assert captured["import_type"] == "migrate_to_local"
    assert captured["target"] == "home"
    assert captured["comic_ids"] == ["VAABP123", "VB_XYZ777"]
    assert captured["content_type"] == "video"
    assert captured["extra_data"] == {
        "source": "preview",
        "entry": "video_recommendation_migrate_to_local",
    }


