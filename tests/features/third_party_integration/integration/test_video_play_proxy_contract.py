from __future__ import annotations

from types import SimpleNamespace

import pytest

from tests.shared.runtime_data import load_json, save_json


def _ok_result(data=None, message="ok"):
    return SimpleNamespace(success=True, data=data, message=message)


@pytest.mark.integration
def test_video_javdb_tags_returns_empty_when_cookie_not_configured(third_party_client):
    """
    用例描述:
    - 用例目的: 看护 JAVDB 标签接口 cookie 前置校验，确保缺少 _jdb_session 时不会触发标签源读取。
    - 测试步骤:
      1. 将隔离 third_party_config.json 写为不含 _jdb_session 的 cookies。
      2. 调用 GET /api/v1/video/third-party/javdb/tags。
      3. 校验 cookie_configured/source_ready/tag_search_available 与 tags 为空。
    - 预期结果:
      1. HTTP 200 且业务 code=200。
      2. cookie_configured=false，tags=[]。
    - 历史变更:
      - 2026-03-23: 初始创建，覆盖 JAVDB 标签前置 cookie 校验契约。
    """
    client = third_party_client["client"]
    config_path = third_party_client["third_party_config_path"]

    config = load_json(config_path)
    config.setdefault("adapters", {}).setdefault("javdb", {})["cookies"] = {"over18": "1"}
    save_json(config_path, config)

    response = client.get("/api/v1/video/third-party/javdb/tags")
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["code"] == 200
    assert payload["data"]["cookie_configured"] is False
    assert payload["data"]["source_ready"] is False
    assert payload["data"]["tag_search_available"] is False
    assert payload["data"]["tags"] == []


@pytest.mark.integration
def test_video_javdb_tags_filters_keyword_and_category(third_party_client, monkeypatch):
    """
    用例描述:
    - 用例目的: 看护 JAVDB 标签接口对 keyword/category 的过滤与分类计数契约，防止标签筛选逻辑回归。
    - 测试步骤:
      1. 写入有效 javdb cookie（含 _jdb_session）。
      2. mock get_video_adapter.api.tag_manager 返回多分类标签。
      3. 调用 GET /api/v1/video/third-party/javdb/tags?category=c1&keyword=act。
      4. 校验只返回匹配标签、分类计数和排序字段。
    - 预期结果:
      1. HTTP 200 且业务 code=200。
      2. 仅返回 c1 分类下匹配关键词的标签。
    - 历史变更:
      - 2026-03-23: 初始创建，覆盖标签过滤契约。
    """
    client = third_party_client["client"]
    video_api = third_party_client["video_api"]
    config_path = third_party_client["third_party_config_path"]

    config = load_json(config_path)
    config.setdefault("adapters", {}).setdefault("javdb", {})["cookies"] = {
        "_jdb_session": "sess-x",
        "over18": "1",
    }
    save_json(config_path, config)

    class FakeTagManager:
        def get_all_tags(self):
            return {
                "c1=1": {"name": "Action Star", "category": "c1", "category_name": "C1", "tag_id": "1", "value": "1"},
                "c1=2": {"name": "Drama", "category": "c1", "category_name": "C1", "tag_id": "2", "value": "2"},
                "c2=3": {"name": "Action Else", "category": "c2", "category_name": "C2", "tag_id": "3", "value": "3"},
            }

        def get_categories(self):
            return {"c1": "C1", "c2": "C2"}

    class FakeAdapter:
        def __init__(self):
            self.api = SimpleNamespace(tag_manager=FakeTagManager())

    monkeypatch.setattr(video_api, "get_video_adapter", lambda *a, **k: FakeAdapter())
    monkeypatch.setattr(video_api, "_is_javdb_tag_search_available", lambda *_a, **_k: True)

    response = client.get(
        "/api/v1/video/third-party/javdb/tags",
        query_string={"category": "c1", "keyword": "act"},
    )
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["code"] == 200
    assert payload["data"]["cookie_configured"] is True
    assert payload["data"]["source_ready"] is True
    assert payload["data"]["tag_search_available"] is True
    assert len(payload["data"]["tags"]) == 1
    assert payload["data"]["tags"][0]["id"] == "c1=1"
    assert payload["data"]["categories"][0]["key"] == "c1"
    assert payload["data"]["categories"][0]["count"] == 1


@pytest.mark.integration
def test_video_third_party_import_recommendation_persists_and_schedules_cache(third_party_client, monkeypatch):
    """
    用例描述:
    - 用例目的: 看护视频第三方导入 recommendation 分支契约，确保写入预览库并调度资源缓存，且 JAVBUS 不下载预览视频。
    - 测试步骤:
      1. mock get_video_adapter.get_video_detail 返回含 tags/封面/缩略图/预览视频的详情。
      2. mock TagAppService、apply_recent_import_tags、_schedule_video_asset_cache。
      3. 调用 POST /api/v1/video/third-party/import(target=recommendation, video_id=JAVBUS_ABP123)。
      4. 校验推荐库落盘字段与缓存调度参数。
    - 预期结果:
      1. HTTP 200 且业务 code=200。
      2. 预览库新增 JAVBUSABP123。
      3. 资源调度 source=preview 且 allow_preview_video=False。
    - 历史变更:
      - 2026-03-23: 初始创建，覆盖 recommendation 导入分支。
    """
    client = third_party_client["client"]
    video_api = third_party_client["video_api"]
    meta_dir = third_party_client["meta_dir"]
    tag_service_module = __import__("application.tag_app_service", fromlist=["TagAppService"])
    captured = {"schedule": [], "recent_tags": []}

    class FakeAdapter:
        def get_video_detail(self, video_id):
            return {
                "video_id": video_id,
                "title": "Bus Title",
                "code": "ABP-123",
                "date": "2025-01-01",
                "series": "S1",
                "actors": ["Actor-Z"],
                "tags": ["TagA", "TagB"],
                "cover_url": "https://assets.example/bus-cover.jpg",
                "thumbnail_images": ["https://assets.example/bus-t1.jpg"],
                "preview_video": "https://assets.example/bus-preview.m3u8",
                "magnets": [],
            }

    class FakeTagService:
        def get_tag_list(self, *_args, **_kwargs):
            return _ok_result([{"id": "tag_1", "name": "TagA"}])

        def create_tag(self, tag_name, *_args, **_kwargs):
            return _ok_result({"id": f"created_{tag_name}"})

    monkeypatch.setattr(video_api, "get_video_adapter", lambda *args, **kwargs: FakeAdapter())
    monkeypatch.setattr(tag_service_module, "TagAppService", FakeTagService)
    monkeypatch.setattr(
        video_api.video_service,
        "apply_recent_import_tags",
        lambda ids, source="preview", clear_previous=True: captured["recent_tags"].append(
            {"ids": ids, "source": source, "clear_previous": clear_previous}
        )
        or _ok_result({"ok": True}),
    )
    monkeypatch.setattr(
        video_api,
        "_schedule_video_asset_cache",
        lambda **kwargs: captured["schedule"].append(kwargs),
    )

    response = client.post(
        "/api/v1/video/third-party/import",
        json={"video_id": "JAVBUS_ABP123", "target": "recommendation", "platform": "javdb"},
    )
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["code"] == 200
    assert payload["data"]["id"] == "JAVBUSABP123"
    assert payload["data"]["code"] == "ABP-123"

    recommendations = load_json(meta_dir / "video_recommendations_database.json").get("video_recommendations", [])
    imported = next((item for item in recommendations if item.get("id") == "JAVBUSABP123"), None)
    assert imported is not None
    assert imported["code"] == "ABP-123"
    assert imported["tag_ids"] == ["tag_1", "created_TagB"]

    assert len(captured["schedule"]) == 1
    assert captured["schedule"][0]["video_id"] == "JAVBUSABP123"
    assert captured["schedule"][0]["source"] == "preview"
    assert captured["schedule"][0]["allow_preview_video"] is False
    assert captured["recent_tags"][0]["source"] == "preview"


@pytest.mark.integration
def test_preview_video_refresh_endpoint_calls_third_party_and_downloads_assets(third_party_client, monkeypatch):
    """
    Case Description:
    - Purpose: Guard end-to-end backend refresh flow from frontend request to third-party detail call and asset download scheduling.
    - Steps:
      1. Mock `get_video_adapter` to return refreshed preview/cover/thumbnail detail.
      2. Mock cache scheduling methods to record parameters.
      3. Call `POST /api/v1/video/preview-video/refresh`.
      4. Verify adapter lookup value and scheduled cache call parameters.
    - Expected:
      1. HTTP 200 with business `code=200`.
      2. Adapter receives normalized third-party lookup ID.
      3. Cover/thumbnail/preview cache methods are called with `source=local`.
    - History:
      - 2026-03-23: Added strong guard for preview refresh third-party interaction chain.
    """
    client = third_party_client["client"]
    video_api = third_party_client["video_api"]
    calls = {"detail": [], "cover": [], "thumbs": [], "preview": []}

    class FakeAdapter:
        def get_video_detail(self, lookup):
            calls["detail"].append(lookup)
            return {
                "video_id": lookup,
                "preview_video": "https://media.example/new-preview.m3u8",
                "cover_url": "https://media.example/new-cover.jpg",
                "thumbnail_images": [
                    "https://media.example/new-thumb-1.jpg",
                    "https://media.example/new-thumb-2.jpg",
                ],
            }

    monkeypatch.setattr(video_api, "get_video_adapter", lambda *_args, **_kwargs: FakeAdapter())
    monkeypatch.setattr(
        video_api.video_service,
        "cache_cover_to_static_async",
        lambda video_id, cover_url, source="local": calls["cover"].append(
            {"video_id": video_id, "cover_url": cover_url, "source": source}
        ),
    )
    monkeypatch.setattr(
        video_api.video_service,
        "cache_thumbnail_images_async",
        lambda video_id, images, source="local", force=False: calls["thumbs"].append(
            {"video_id": video_id, "count": len(images or []), "source": source, "force": force}
        ),
    )
    monkeypatch.setattr(
        video_api.video_service,
        "cache_preview_video_async",
        lambda video_id, preview_url, source="local", force=False: calls["preview"].append(
            {"video_id": video_id, "preview_url": preview_url, "source": source, "force": force}
        ),
    )

    response = client.post(
        "/api/v1/video/preview-video/refresh",
        json={"video_id": "JAVDB900001", "source": "local"},
    )
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["code"] == 200
    assert calls["detail"] == ["900001"]
    assert calls["cover"][0]["video_id"] == "JAVDB900001"
    assert calls["cover"][0]["source"] == "local"
    assert calls["thumbs"][0]["video_id"] == "JAVDB900001"
    assert calls["thumbs"][0]["count"] == 2
    assert calls["thumbs"][0]["force"] is True
    assert calls["preview"][0]["video_id"] == "JAVDB900001"
    assert calls["preview"][0]["source"] == "local"
    assert calls["preview"][0]["force"] is True


@pytest.mark.integration
def test_video_play_urls_routes_forward_code_to_missav_client(third_party_client, monkeypatch):
    """
    用例描述:
    - 用例目的: 看护本地库/推荐库 play-urls 接口与第三方播放器 build_sources 的调用契约，防止 code 传参错误导致在线播放失效。
    - 测试步骤:
      1. 向推荐库写入一条带 code 的测试视频。
      2. mock _get_missav_client.build_sources 记录入参。
      3. 分别调用 /api/v1/video/<id>/play-urls 和 /api/v1/video/recommendation/<id>/play-urls。
    - 预期结果:
      1. 两个接口均返回 code=200 与 sources。
      2. build_sources 分别收到本地/推荐记录对应的 code。
    - 历史变更:
      - 2026-03-23: 初始创建，覆盖在线播放链接构建契约。
    """
    client = third_party_client["client"]
    video_api = third_party_client["video_api"]
    meta_dir = third_party_client["meta_dir"]
    calls = []

    class FakeMissavClient:
        def build_sources(self, code):
            calls.append(code)
            return [{"platform": "missav", "url": f"https://play.example/{code}"}]

    recommendation_payload = load_json(meta_dir / "video_recommendations_database.json")
    recommendation_payload.setdefault("video_recommendations", []).append(
        {
            "id": "JAVDBREC001",
            "title": "Rec-1",
            "code": "REC-001",
            "actors": [],
            "tag_ids": [],
            "list_ids": [],
            "create_time": "2026-03-23T00:00:00",
            "last_access_time": "2026-03-23T00:00:00",
            "is_deleted": False,
        }
    )
    save_json(meta_dir / "video_recommendations_database.json", recommendation_payload)

    monkeypatch.setattr(video_api, "_get_missav_client", lambda: FakeMissavClient())

    local_resp = client.get("/api/v1/video/JAVDB900001/play-urls")
    local_payload = local_resp.get_json()
    assert local_resp.status_code == 200
    assert local_payload["code"] == 200
    assert local_payload["data"]["code"] == "TEST-900001"
    assert local_payload["data"]["sources"][0]["platform"] == "missav"

    rec_resp = client.get("/api/v1/video/recommendation/JAVDBREC001/play-urls")
    rec_payload = rec_resp.get_json()
    assert rec_resp.status_code == 200
    assert rec_payload["code"] == 200
    assert rec_payload["data"]["code"] == "REC-001"
    assert rec_payload["data"]["sources"][0]["platform"] == "missav"

    assert calls == ["TEST-900001", "REC-001"]


@pytest.mark.integration
def test_video_proxy_routes_forward_required_arguments_to_missav_client(third_party_client, monkeypatch):
    """
    用例描述:
    - 用例目的: 看护 /proxy 与 /proxy2 对第三方播放器代理层的参数透传契约，防止 query/body/header 漏传导致播放失败。
    - 测试步骤:
      1. mock _get_missav_client，提供 proxy_stream/proxy_url 记录入参。
      2. 调用 GET /api/v1/video/proxy/<domain>/<path> 与 POST /api/v1/video/proxy2。
      3. 校验 domain/path/query/referrer/body_url/incoming_headers。
    - 预期结果:
      1. 两个接口均按 mock 返回状态码和内容。
      2. missav 客户端收到完整透传参数。
    - 历史变更:
      - 2026-03-23: 初始创建，覆盖代理转发契约。
    """
    client = third_party_client["client"]
    video_api = third_party_client["video_api"]
    captured = {"stream": [], "proxy2": []}

    class FakeMissavClient:
        def proxy_stream(self, domain, path, query_string, incoming_referer):
            captured["stream"].append(
                {
                    "domain": domain,
                    "path": path,
                    "query_string": query_string,
                    "incoming_referer": incoming_referer,
                }
            )
            return SimpleNamespace(
                body=b"stream-ok",
                status_code=206,
                headers={"Content-Type": "video/mp2t"},
            )

        def proxy_url(self, method, query_string, body_url, incoming_referer, incoming_headers):
            captured["proxy2"].append(
                {
                    "method": method,
                    "query_string": query_string,
                    "body_url": body_url,
                    "incoming_referer": incoming_referer,
                    "incoming_headers": incoming_headers,
                }
            )
            return SimpleNamespace(
                content=b"proxy2-ok",
                status_code=200,
                headers=[("Content-Type", "application/vnd.apple.mpegurl"), ("X-Proxy", "1")],
            )

    monkeypatch.setattr(video_api, "_get_missav_client", lambda: FakeMissavClient())

    stream_resp = client.get(
        "/api/v1/video/proxy/javdb/videos/seg.ts?token=abc",
        headers={"Referer": "https://site.example/player"},
    )
    assert stream_resp.status_code == 206
    assert stream_resp.data == b"stream-ok"
    assert captured["stream"][0]["domain"] == "javdb"
    assert captured["stream"][0]["path"] == "videos/seg.ts"
    assert captured["stream"][0]["query_string"] == "token=abc"
    assert captured["stream"][0]["incoming_referer"] == "https://site.example/player"

    proxy2_resp = client.post(
        "/api/v1/video/proxy2?url=https%3A%2F%2Fmedia.example%2Findex.m3u8",
        json={"url": "https://media.example/post.m3u8"},
        headers={
            "Referer": "https://site.example/player2",
            "Range": "bytes=0-99",
            "Accept": "*/*",
            "Origin": "https://site.example",
            "User-Agent": "pytest-agent",
        },
    )
    assert proxy2_resp.status_code == 200
    assert proxy2_resp.data == b"proxy2-ok"
    assert captured["proxy2"][0]["method"] == "POST"
    assert captured["proxy2"][0]["query_string"] == "url=https%3A%2F%2Fmedia.example%2Findex.m3u8"
    assert captured["proxy2"][0]["body_url"] == "https://media.example/post.m3u8"
    assert captured["proxy2"][0]["incoming_referer"] == "https://site.example/player2"
    assert captured["proxy2"][0]["incoming_headers"]["Range"] == "bytes=0-99"
