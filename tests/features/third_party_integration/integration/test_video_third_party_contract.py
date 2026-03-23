from __future__ import annotations

from types import SimpleNamespace

import pytest

from tests.shared.runtime_data import load_json, save_json


def _ok_result(data=None, message="ok"):
    return SimpleNamespace(success=True, data=data, message=message)


def _error_result(message="error"):
    return SimpleNamespace(success=False, data=None, message=message)


@pytest.mark.integration
def test_video_javdb_cookie_status_reads_isolated_config(third_party_client):
    """
    用例描述:
    - 用例目的: 看护视频端对 JAVDB cookie 配置读取契约，确保运行时路径切换后仍能读取到隔离配置。
    - 测试步骤:
      1. 修改 tests/.runtime/integration_third_party/third_party_config.json 的 javdb.cookies。
      2. 调用 GET /api/v1/video/third-party/javdb/cookie-status。
      3. 校验 configured 与 cookie_keys 返回值。
    - 预期结果:
      1. HTTP 200 且业务 code=200。
      2. configured 仅由 _jdb_session 决定，cookie_keys 返回排序后的键集合。
    - 历史变更:
      - 2026-03-23: 初始创建，覆盖第三方配置路径/字段读取契约。
    """
    client = third_party_client["client"]
    config_path = third_party_client["third_party_config_path"]

    config = load_json(config_path)
    config.setdefault("adapters", {}).setdefault("javdb", {})["cookies"] = {
        "over18": "1",
        "_jdb_session": "sess-abc",
        "locale": "zh",
    }
    save_json(config_path, config)

    response = client.get("/api/v1/video/third-party/javdb/cookie-status")
    payload = response.get_json()
    assert response.status_code == 200
    assert payload["code"] == 200
    assert payload["data"]["configured"] is True
    assert payload["data"]["has_session_cookie"] is True
    assert payload["data"]["cookie_keys"] == ["_jdb_session", "locale", "over18"]


@pytest.mark.integration
def test_video_javdb_cookie_status_without_session_returns_not_configured(third_party_client):
    """
    用例描述:
    - 用例目的: 看护 JAVDB cookie 状态判定规则，确保缺少 _jdb_session 时会返回未配置状态。
    - 测试步骤:
      1. 将隔离配置写为仅含 over18 的 cookies（不含 _jdb_session）。
      2. 调用 GET /api/v1/video/third-party/javdb/cookie-status。
      3. 校验 configured/has_session_cookie 为 false。
    - 预期结果:
      1. HTTP 200 且业务 code=200。
      2. configured=False，避免误判为已登录状态。
    - 历史变更:
      - 2026-03-23: 初始创建，覆盖 cookie 缺失防御逻辑。
    """
    client = third_party_client["client"]
    config_path = third_party_client["third_party_config_path"]

    config = load_json(config_path)
    config.setdefault("adapters", {}).setdefault("javdb", {})["cookies"] = {"over18": "1"}
    save_json(config_path, config)

    response = client.get("/api/v1/video/third-party/javdb/cookie-status")
    payload = response.get_json()
    assert response.status_code == 200
    assert payload["code"] == 200
    assert payload["data"]["configured"] is False
    assert payload["data"]["has_session_cookie"] is False


@pytest.mark.integration
def test_video_third_party_search_all_forwards_adapter_calls(third_party_client, monkeypatch):
    """
    用例描述:
    - 用例目的: 看护视频远程搜索接口到第三方适配器的调用契约，防止平台分发/分页参数透传错误。
    - 测试步骤:
      1. mock get_video_adapter，返回可记录入参的假适配器。
      2. 调用 GET /api/v1/video/third-party/search?platform=all&page=2。
      3. 断言 javdb/javbus 均被调用且 page/max_pages 参数正确。
    - 预期结果:
      1. HTTP 200 且业务 code=200。
      2. 两个平台调用完整，返回数据包含 platform 字段并合并到同一结果集。
    - 历史变更:
      - 2026-03-23: 初始创建，覆盖视频第三方搜索调用契约。
    """
    client = third_party_client["client"]
    video_api = third_party_client["video_api"]
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
                        "cover_url": "https://www.javbus.com/pics/abc.jpg",
                    }
                ],
                "page": page,
                "has_next": self.platform == "javdb",
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

    by_platform = {item["platform"]: item for item in calls}
    assert set(by_platform.keys()) == {"javdb", "javbus"}
    assert all(item["keyword"] == "star" for item in calls)
    assert all(item["page"] == 2 for item in calls)
    assert all(item["max_pages"] == 1 for item in calls)

    # javbus cover_url should be rewritten to proxy URL.
    assert any(str(item.get("cover_url", "")).startswith("/api/v1/video/proxy2?url=") for item in data["videos"])


@pytest.mark.integration
def test_video_javdb_search_by_tags_builds_expected_query(third_party_client, monkeypatch):
    """
    用例描述:
    - 用例目的: 看护 JAVDB 标签搜索 tag_ids 解析和 third-party 调用 query 构建契约，防止参数拼接导致搜索失效。
    - 测试步骤:
      1. mock get_video_adapter，提供 api.get 和 _parse_work_item。
      2. mock _is_javdb_tag_search_available 返回 True。
      3. 调用 GET /api/v1/video/third-party/javdb/search-by-tags(tag_ids=c4=22,19&c1=23&page=2)。
      4. 校验 third-party 请求路径与响应中的 effective_tag_ids。
    - 预期结果:
      1. HTTP 200 且业务 code=200。
      2. 请求路径为 /tags?c1=23&c4=22,19&page=2。
      3. effective_tag_ids 顺序稳定且符合分类排序规则。
    - 历史变更:
      - 2026-03-23: 初始创建，覆盖标签搜索 query 构建契约。
    """
    client = third_party_client["client"]
    video_api = third_party_client["video_api"]
    requested_paths = []

    class FakeJavdbApi:
        def get(self, path):
            requested_paths.append(path)
            html = '<html><body><div class="item"><a href="/v/1"></a></div></body></html>'
            return SimpleNamespace(text=html)

        def _parse_work_item(self, _item):
            return {"video_id": "J1", "title": "JAVDB-Work"}

    class FakeAdapter:
        def __init__(self):
            self.api = FakeJavdbApi()

    monkeypatch.setattr(video_api, "get_video_adapter", lambda *args, **kwargs: FakeAdapter())
    monkeypatch.setattr(video_api, "_is_javdb_tag_search_available", lambda adapter: True)

    response = client.get(
        "/api/v1/video/third-party/javdb/search-by-tags",
        query_string=[("tag_ids", "c4=22,19"), ("tag_ids", "c1=23"), ("page", "2")],
    )
    payload = response.get_json()
    assert response.status_code == 200
    assert payload["code"] == 200
    assert payload["data"]["effective_tag_ids"] == ["c1=23", "c4=22", "c4=19"]
    assert payload["data"]["invalid_tag_ids"] == []
    assert requested_paths[-1] == "/tags?c1=23&c4=22,19&page=2"


@pytest.mark.integration
def test_video_javdb_search_by_tags_rejects_invalid_tag_ids(third_party_client):
    """
    用例描述:
    - 用例目的: 看护 JAVDB 标签搜索对非法 tag_ids 的校验分支，防止错误参数触发异常调用。
    - 测试步骤:
      1. 调用 GET /api/v1/video/third-party/javdb/search-by-tags，传入非法 tag_ids。
      2. 检查返回错误码。
    - 预期结果:
      1. HTTP 200，业务 code=400。
      2. 错误信息提示至少需要一个有效 tag_id。
    - 历史变更:
      - 2026-03-23: 初始创建，覆盖非法 tag_ids 防御路径。
    """
    client = third_party_client["client"]
    response = client.get(
        "/api/v1/video/third-party/javdb/search-by-tags",
        query_string=[("tag_ids", "abc"), ("tag_ids", "c4=not_number")],
    )
    payload = response.get_json()
    assert response.status_code == 200
    assert payload["code"] == 400
    assert "tag_id" in str(payload["msg"]).lower()


@pytest.mark.integration
def test_video_javdb_search_by_tags_requires_login_cookie(third_party_client, monkeypatch):
    """
    Case Description:
    - Purpose: Guard the "tag search requires login" branch so missing/expired cookie does not silently query third-party.
    - Steps:
      1. Mock `get_video_adapter` and force `_is_javdb_tag_search_available` to return False.
      2. Call `GET /api/v1/video/third-party/javdb/search-by-tags` with valid `tag_ids`.
      3. Verify business error code and message.
    - Expected:
      1. HTTP 200 with business `code=401`.
      2. Error message indicates login/cookie is required.
    - History:
      - 2026-03-23: Added to cover cookie-required contract branch.
    """
    client = third_party_client["client"]
    video_api = third_party_client["video_api"]

    class FakeAdapter:
        api = SimpleNamespace()

    monkeypatch.setattr(video_api, "get_video_adapter", lambda *args, **kwargs: FakeAdapter())
    monkeypatch.setattr(video_api, "_is_javdb_tag_search_available", lambda *_args, **_kwargs: False)

    response = client.get(
        "/api/v1/video/third-party/javdb/search-by-tags",
        query_string=[("tag_ids", "c1=23"), ("page", "1")],
    )
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["code"] == 401
    assert "cookie" in str(payload["msg"]).lower() or "登录" in str(payload["msg"])


@pytest.mark.integration
def test_video_third_party_detail_actor_search_and_works_contract(third_party_client, monkeypatch):
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
    client = third_party_client["client"]
    video_api = third_party_client["video_api"]
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

    detail_resp = client.get("/api/v1/video/third-party/detail", query_string={"video_id": "X-001", "platform": "javdb"})
    detail_payload = detail_resp.get_json()
    assert detail_resp.status_code == 200
    assert detail_payload["code"] == 200
    assert detail_payload["data"]["video_id"] == "X-001"

    actor_search_resp = client.get(
        "/api/v1/video/third-party/actor/search",
        query_string={"actor_name": "Mina", "platform": "javdb"},
    )
    actor_search_payload = actor_search_resp.get_json()
    assert actor_search_resp.status_code == 200
    assert actor_search_payload["code"] == 200
    assert actor_search_payload["data"][0]["name"] == "Mina"

    actor_works_resp = client.get(
        "/api/v1/video/third-party/actor/works",
        query_string={"actor_id": "ACT-9", "page": 3, "platform": "javdb"},
    )
    actor_works_payload = actor_works_resp.get_json()
    assert actor_works_resp.status_code == 200
    assert actor_works_payload["code"] == 200
    assert actor_works_payload["data"]["page"] == 3

    assert calls["detail"] == ["X-001"]
    assert calls["actor_search"] == ["Mina"]
    assert calls["actor_works"] == [{"actor_id": "ACT-9", "page": 3, "max_pages": 1}]


@pytest.mark.integration
def test_video_third_party_import_home_normalizes_id_and_calls_expected_dependencies(third_party_client, monkeypatch):
    """
    用例描述:
    - 用例目的: 看护视频第三方导入接口在 ID 规范化、第三方详情查询、导入服务调用、资源缓存调度上的契约。
    - 测试步骤:
      1. mock get_video_adapter/get_video_detail，返回带 code/tags/预览地址的详情。
      2. mock TagAppService、video_service.import_video、apply_recent_import_tags、_schedule_video_asset_cache。
      3. 调用 POST /api/v1/video/third-party/import，传入 video_id=JAVDB_ABP123,target=home。
      4. 校验各依赖收到的参数和值映射。
    - 预期结果:
      1. HTTP 200 且业务 code=200。
      2. adapter.get_video_detail 收到规范化后的 ABP123。
      3. import_video 收到前缀化后的 ID（JAVDBABP123）和正确 code。
      4. 资源缓存调度收到 source=local 与对应资源参数。
    - 历史变更:
      - 2026-03-23: 初始创建，覆盖第三方导入核心契约。
    """
    client = third_party_client["client"]
    video_api = third_party_client["video_api"]
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
        json={"video_id": "JAVDB_ABP123", "target": "home", "platform": "javdb"},
    )
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["code"] == 200
    assert adapter_calls["detail"] == ["ABP123"]

    assert len(import_payloads) == 1
    imported = import_payloads[0]
    assert imported["id"] == "JAVDBABP123"
    assert imported["code"] == "ABP-123"
    assert imported["tag_ids"] == ["tag_1"]
    assert imported["creator"] == "Actor-X"

    assert len(schedule_calls) == 1
    assert schedule_calls[0]["video_id"] == "JAVDBABP123"
    assert schedule_calls[0]["source"] == "local"
    assert schedule_calls[0]["allow_preview_video"] is True


@pytest.mark.integration
def test_video_third_party_import_home_falls_back_to_get_video_by_code(third_party_client, monkeypatch):
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
    client = third_party_client["client"]
    video_api = third_party_client["video_api"]
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
        json={"video_id": "ABP123", "target": "home", "platform": "javdb"},
    )
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["code"] == 200
    assert calls["detail"] == ["ABP123"]
    assert calls["fallback"] == ["ABP123"]
    assert imported_payloads[0]["id"] == "JAVDBABP-123"
    assert imported_payloads[0]["code"] == "ABP-123"


@pytest.mark.integration
def test_preview_video_refresh_route_forwards_required_contract(third_party_client, monkeypatch):
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
    client = third_party_client["client"]
    video_api = third_party_client["video_api"]
    captured = {}

    def fake_refresh(video_id, source="local", force_download=False):
        captured["video_id"] = video_id
        captured["source"] = source
        captured["force_download"] = force_download
        return {"success": True, "message": "ok", "data": {"id": video_id, "preview_video": "/media/preview.m3u8"}}

    monkeypatch.setattr(video_api, "_refresh_preview_video_now", fake_refresh)

    response = client.post(
        "/api/v1/video/preview-video/refresh",
        json={"video_id": "JAVDB900001", "source": "preview"},
    )
    payload = response.get_json()
    assert response.status_code == 200
    assert payload["code"] == 200
    assert captured == {"video_id": "JAVDB900001", "source": "preview", "force_download": True}


@pytest.mark.integration
def test_video_preview_headers_include_javdb_cookie_from_isolated_config(third_party_client):
    """
    用例描述:
    - 用例目的: 看护视频在线播放预览请求头构建契约，确保 JAVDB 场景会携带 Cookie 与 Referer。
    - 测试步骤:
      1. 写入隔离 third_party_config.json 的 javdb.cookies。
      2. 调用 VideoAppService._build_preview_video_headers(javdb 预览 URL)。
      3. 检查 Cookie 与 Referer 字段。
    - 预期结果:
      1. Referer 固定为 https://javdb.com/。
      2. Cookie 包含 _jdb_session 与 over18 键值。
    - 历史变更:
      - 2026-03-23: 初始创建，覆盖在线播放 Cookie 头契约。
    """
    config_path = third_party_client["third_party_config_path"]
    video_service_module = third_party_client["video_service_module"]

    config = load_json(config_path)
    config.setdefault("adapters", {}).setdefault("javdb", {})["cookies"] = {
        "_jdb_session": "video-session",
        "over18": "1",
    }
    save_json(config_path, config)

    service = video_service_module.VideoAppService()
    headers = service._build_preview_video_headers("https://javdb.com/movies/ttm3u8/preview/123/0/720p.m3u8")

    assert headers["Referer"] == "https://javdb.com/"
    assert "_jdb_session=video-session" in headers.get("Cookie", "")
    assert "over18=1" in headers.get("Cookie", "")


@pytest.mark.integration
def test_video_preview_headers_for_non_javdb_host_do_not_attach_cookie(third_party_client):
    """
    用例描述:
    - 用例目的: 看护预览请求头在非 JAVDB 域名下不应携带 JAVDB Cookie，避免跨域误带敏感头。
    - 测试步骤:
      1. 调用 VideoAppService._build_preview_video_headers，输入非 JAVDB URL。
      2. 校验 Referer 与 Cookie 字段。
    - 预期结果:
      1. Referer 按目标域名生成。
      2. 不包含 Cookie 头。
    - 历史变更:
      - 2026-03-23: 初始创建，覆盖非 JAVDB 请求头隔离契约。
    """
    video_service_module = third_party_client["video_service_module"]
    service = video_service_module.VideoAppService()

    headers = service._build_preview_video_headers("https://cdn.example.com/video/preview.m3u8")
    assert headers["Referer"] == "https://cdn.example.com/"
    assert "Cookie" not in headers
