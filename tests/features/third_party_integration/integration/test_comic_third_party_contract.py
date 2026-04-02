from __future__ import annotations

import importlib
from pathlib import Path

import pytest

from tests.shared.runtime_data import find_by_id, load_json, save_json


@pytest.mark.integration
def test_comic_third_party_config_save_parses_cookie_string_and_persists(third_party_client):
    """
    用例描述:
    - 用例目的: 看护漫画第三方配置接口在保存 JAVDB cookie_string 时的入参与落盘契约，避免路径/字段变更导致配置未生效。
    - 测试步骤:
      1. 调用 POST /api/v1/comic/third-party/config，提交 javdb.adapter 的 cookie_string。
      2. 读取隔离 third_party_config.json，检查 cookies 字段已被解析为字典并写入隔离路径。
      3. 调用 GET /api/v1/comic/third-party/config，检查回读内容包含 cookie_string。
    - 预期结果:
      1. 接口返回 HTTP 200 且业务 code=200。
      2. 配置写入 tests/.runtime/integration_third_party 下的隔离配置文件。
      3. _jdb_session 与 over18 均被正确持久化并可回读。
    - 历史变更:
      - 2026-03-23: 初始创建，覆盖第三方配置保存/读取核心契约。
    """
    client = third_party_client["client"]
    config_path = third_party_client["third_party_config_path"]

    response = client.post(
        "/api/v1/comic/third-party/config",
        json={
            "adapter": "javdb",
            "config": {
                "enabled": True,
                "domain_index": 3,
                "cookie_string": "_jdb_session=session-token; over18=1",
            },
        },
    )
    payload = response.get_json()
    assert response.status_code == 200
    assert payload["code"] == 200
    assert payload["data"]["updated_adapters"] == ["javdb"]

    persisted = load_json(config_path)
    cookies = ((persisted.get("adapters") or {}).get("javdb") or {}).get("cookies") or {}
    assert cookies.get("_jdb_session") == "session-token"
    assert cookies.get("over18") == "1"

    read_back = client.get("/api/v1/comic/third-party/config")
    read_payload = read_back.get_json()
    assert read_back.status_code == 200
    assert read_payload["code"] == 200
    returned_cookie_string = (((read_payload["data"] or {}).get("adapters") or {}).get("javdb") or {}).get("cookie_string", "")
    # 新契约：前端只展示 _jdb_session 的值；兼容旧实现（完整 cookie 字符串回读）。
    assert (
        returned_cookie_string == "session-token"
        or "_jdb_session=session-token" in returned_cookie_string
    )


@pytest.mark.integration
def test_comic_third_party_config_rejects_unknown_adapter(third_party_client):
    """
    用例描述:
    - 用例目的: 看护漫画第三方配置接口的适配器白名单校验，避免错误 adapter 入参被静默接受。
    - 测试步骤:
      1. 调用 POST /api/v1/comic/third-party/config，传入不存在的 adapter。
      2. 校验接口返回业务错误码。
    - 预期结果:
      1. HTTP 200，业务 code=400。
      2. 错误信息明确提示不支持的适配器。
    - 历史变更:
      - 2026-03-23: 初始创建，覆盖第三方配置入参防御。
    """
    client = third_party_client["client"]
    response = client.post(
        "/api/v1/comic/third-party/config",
        json={"adapter": "unknown_adapter", "config": {"enabled": True}},
    )
    payload = response.get_json()
    assert response.status_code == 200
    assert payload["code"] == 400
    assert "unknown_adapter" in str(payload["msg"])


@pytest.mark.integration
def test_comic_search_third_party_all_forwards_adapter_contract(third_party_client, monkeypatch):
    """
    用例描述:
    - 用例目的: 看护漫画远程搜索接口对第三方库 search_albums 的调用契约，防止关键词/分页/适配器参数回归。
    - 测试步骤:
      1. mock third_party.external_api.search_albums 记录入参。
      2. 调用 GET /api/v1/comic/search-third-party?platform=all&page=2。
      3. 断言 JM/PK 两个平台都被调用，且参数正确映射。
    - 预期结果:
      1. HTTP 200 且业务 code=200。
      2. search_albums 被调用两次，adapter_name 分别为 jmcomic/picacomic。
      3. page=2、max_pages=1、fast_mode=True 被正确透传。
    - 历史变更:
      - 2026-03-23: 初始创建，覆盖第三方搜索参数映射契约。
    """
    client = third_party_client["client"]
    external_api = importlib.import_module("third_party.external_api")
    calls = []

    def fake_search_albums(keyword, page=1, max_pages=1, adapter_name=None, fast_mode=False):
        calls.append(
            {
                "keyword": keyword,
                "page": page,
                "max_pages": max_pages,
                "adapter_name": adapter_name,
                "fast_mode": fast_mode,
            }
        )
        return {
            "albums": [{"album_id": f"{adapter_name}-id", "title": f"title-{adapter_name}", "tags": []}],
            "page": page,
            "total_pages": 4,
            "has_next": adapter_name == "jmcomic",
        }

    monkeypatch.setattr(external_api, "search_albums", fake_search_albums)

    response = client.get(
        "/api/v1/comic/search-third-party",
        query_string={"keyword": "test-keyword", "platform": "all", "page": 2, "limit": 40},
    )
    payload = response.get_json()
    assert response.status_code == 200
    assert payload["code"] == 200
    data = payload["data"]
    assert len(data["results"]) == 2

    called_adapters = {item["adapter_name"] for item in calls}
    assert called_adapters == {"jmcomic", "picacomic"}
    assert all(item["keyword"] == "test-keyword" for item in calls)
    assert all(item["page"] == 2 for item in calls)
    assert all(item["max_pages"] == 1 for item in calls)
    assert all(item["fast_mode"] is True for item in calls)


@pytest.mark.integration
def test_comic_search_third_party_rejects_invalid_platform(third_party_client):
    """
    用例描述:
    - 用例目的: 看护漫画远程搜索的平台参数校验，防止无效平台误入第三方调用。
    - 测试步骤:
      1. 调用 GET /api/v1/comic/search-third-party 并传入 video 平台名 javdb。
      2. 检查返回错误码与提示信息。
    - 预期结果:
      1. HTTP 200，业务 code=400。
      2. 响应明确告知不支持的漫画平台。
    - 历史变更:
      - 2026-03-23: 初始创建，覆盖平台参数非法分支。
    """
    client = third_party_client["client"]
    response = client.get(
        "/api/v1/comic/search-third-party",
        query_string={"keyword": "abc", "platform": "javdb"},
    )
    payload = response.get_json()
    assert response.status_code == 200
    assert payload["code"] == 400
    assert "javdb" in str(payload["msg"]).lower()


@pytest.mark.integration
def test_comic_search_third_party_all_skips_unconfigured_platforms(third_party_client, monkeypatch):
    client = third_party_client["client"]
    config_path = third_party_client["third_party_config_path"]
    external_api = importlib.import_module("third_party.external_api")
    original_config = load_json(config_path)

    config = load_json(config_path)
    config.setdefault("adapters", {}).setdefault("jmcomic", {}).update(
        {"enabled": True, "username": "jm-user", "password": "jm-pass"}
    )
    config.setdefault("adapters", {}).setdefault("picacomic", {}).update(
        {"enabled": True, "account": "", "password": ""}
    )
    save_json(config_path, config)

    calls = []

    def fake_search_albums(keyword, page=1, max_pages=1, adapter_name=None, fast_mode=False):
        calls.append(str(adapter_name))
        return {
            "albums": [{"album_id": "jm-id", "title": "jm-title", "tags": []}],
            "page": page,
            "total_pages": 1,
            "has_next": False,
        }

    monkeypatch.setattr(external_api, "search_albums", fake_search_albums)

    try:
        response = client.get(
            "/api/v1/comic/search-third-party",
            query_string={"keyword": "test", "platform": "all", "page": 1},
        )
        payload = response.get_json()
        assert response.status_code == 200
        assert payload["code"] == 200
        assert calls == ["jmcomic"]
        assert len((payload["data"] or {}).get("results") or []) == 1
        platform_errors = (payload["data"] or {}).get("platform_errors") or {}
        assert "PK" in platform_errors
        assert "未配置账号或密码" in str(platform_errors.get("PK", ""))
    finally:
        save_json(config_path, original_config)


@pytest.mark.integration
def test_comic_search_third_party_specific_platform_requires_credentials(third_party_client):
    client = third_party_client["client"]
    config_path = third_party_client["third_party_config_path"]
    original_config = load_json(config_path)

    config = load_json(config_path)
    config.setdefault("adapters", {}).setdefault("picacomic", {}).update(
        {"enabled": True, "account": "", "password": ""}
    )
    save_json(config_path, config)

    try:
        response = client.get(
            "/api/v1/comic/search-third-party",
            query_string={"keyword": "need-pk", "platform": "PK", "page": 1},
        )
        payload = response.get_json()
        assert response.status_code == 200
        assert payload["code"] == 400
        assert "PK" in str(payload["msg"])
        assert "未配置账号或密码" in str(payload["msg"])
    finally:
        save_json(config_path, original_config)


@pytest.mark.integration
def test_comic_import_online_by_id_forwards_platform_service_contract(third_party_client, monkeypatch):
    """
    用例描述:
    - 用例目的: 看护漫画在线导入(by_id)到第三方下载服务的调用契约，防止平台参数、original_id、下载目录传递错误。
    - 测试步骤:
      1. mock get_album_by_id 返回单条漫画元数据。
      2. mock get_platform_service().download_album 记录调用参数并返回下载成功。
      3. 调用 POST /api/v1/comic/import/online(import_type=by_id,target=home,platform=JM)。
      4. 校验调用参数、导入响应以及隔离元数据落盘。
    - 预期结果:
      1. HTTP 200 且业务 code=200。
      2. download_album 收到正确的 platform/original_id/download_dir/show_progress。
      3. comics_database.json 新增记录且 total_page 被下载返回值覆盖。
    - 历史变更:
      - 2026-03-23: 初始创建，覆盖在线导入关键契约。
    """
    client = third_party_client["client"]
    meta_dir = third_party_client["meta_dir"]
    external_api = importlib.import_module("third_party.external_api")
    platform_service_module = importlib.import_module("third_party.platform_service")

    monkeypatch.setattr(
        external_api,
        "get_album_by_id",
        lambda comic_id, adapter_name: {
            "albums": [{"album_id": str(comic_id), "title": "Remote Album", "author": "A", "pages": 12, "tags": []}]
        },
    )

    download_calls = []

    class FakePlatformService:
        def download_album(self, platform, original_id, download_dir=None, show_progress=True):
            download_calls.append(
                {
                    "platform": getattr(platform, "value", str(platform)),
                    "original_id": str(original_id),
                    "download_dir": str(download_dir or ""),
                    "show_progress": show_progress,
                }
            )
            return {"local_pages": 7}, True

    monkeypatch.setattr(platform_service_module, "get_platform_service", lambda: FakePlatformService())

    response = client.post(
        "/api/v1/comic/import/online",
        json={
            "import_type": "by_id",
            "target": "home",
            "platform": "JM",
            "comic_id": "112233",
        },
    )
    payload = response.get_json()
    assert response.status_code == 200
    assert payload["code"] == 200
    assert payload["data"]["imported_count"] == 1
    assert payload["data"]["downloaded_count"] == 1

    assert len(download_calls) == 1
    assert download_calls[0]["platform"] == "JM"
    assert download_calls[0]["original_id"] == "112233"
    assert download_calls[0]["show_progress"] is False
    assert "/comic/JM" in download_calls[0]["download_dir"].replace("\\", "/")

    comics = load_json(meta_dir / "comics_database.json").get("comics", [])
    imported = find_by_id(comics, "JM112233")
    assert imported is not None
    assert int(imported["total_page"]) == 7


@pytest.mark.integration
def test_comic_import_online_by_search_forwards_search_contract(third_party_client, monkeypatch):
    """
    用例描述:
    - 用例目的: 看护漫画在线导入(by_search)对 third_party.search_albums 的调用契约，防止关键词/页数/适配器映射错误。
    - 测试步骤:
      1. mock search_albums 记录 keyword/max_pages/adapter_name。
      2. mock download_album 返回成功，保证流程完整走通。
      3. 调用 POST /api/v1/comic/import/online(import_type=by_search,platform=PK,max_pages=3)。
      4. 断言第三方搜索调用参数及接口成功返回。
    - 预期结果:
      1. HTTP 200 且业务 code=200。
      2. search_albums 收到 keyword='idol'、max_pages=3、adapter_name='picacomic'。
    - 历史变更:
      - 2026-03-23: 初始创建，覆盖 by_search 参数映射契约。
    """
    client = third_party_client["client"]
    config_path = third_party_client["third_party_config_path"]
    external_api = importlib.import_module("third_party.external_api")
    platform_service_module = importlib.import_module("third_party.platform_service")
    config = load_json(config_path)
    config.setdefault("adapters", {}).setdefault("picacomic", {}).update(
        {"enabled": True, "account": "pk-user", "password": "pk-pass"}
    )
    save_json(config_path, config)

    captured = {}

    def fake_search(keyword, max_pages=1, adapter_name=None):
        captured["keyword"] = keyword
        captured["max_pages"] = max_pages
        captured["adapter_name"] = adapter_name
        return {"albums": [{"album_id": "556677", "title": "Search Album", "author": "B", "pages": 9, "tags": []}]}

    monkeypatch.setattr(external_api, "search_albums", fake_search)

    class FakePlatformService:
        def download_album(self, platform, original_id, download_dir=None, show_progress=True):
            return {"local_pages": 9}, True

    monkeypatch.setattr(platform_service_module, "get_platform_service", lambda: FakePlatformService())

    response = client.post(
        "/api/v1/comic/import/online",
        json={
            "import_type": "by_search",
            "target": "home",
            "platform": "PK",
            "keyword": "idol",
            "max_pages": 3,
        },
    )
    payload = response.get_json()
    assert response.status_code == 200
    assert payload["code"] == 200

    assert captured["keyword"] == "idol"
    assert int(captured["max_pages"]) == 3
    assert captured["adapter_name"] == "picacomic"


@pytest.mark.integration
def test_comic_import_online_by_favorite_forwards_get_favorites_contract(third_party_client, monkeypatch):
    """
    用例描述:
    - 用例目的: 看护漫画在线导入(by_favorite)对 third_party.get_favorites 的调用契约，防止平台适配器映射或收藏夹导入链路回归。
    - 测试步骤:
      1. mock external_api.get_favorites 记录 adapter_name 并返回收藏漫画。
      2. mock platform_service.download_album 返回下载成功。
      3. 调用 POST /api/v1/comic/import/online(import_type=by_favorite, platform=JM, target=home)。
      4. 校验调用参数与导入结果。
    - 预期结果:
      1. HTTP 200 且业务 code=200。
      2. get_favorites 收到 adapter_name='jmcomic'。
      3. comics_database.json 新增对应前缀化漫画 ID。
    - 历史变更:
      - 2026-03-23: 初始创建，覆盖收藏夹在线导入契约。
    """
    client = third_party_client["client"]
    meta_dir = third_party_client["meta_dir"]
    external_api = importlib.import_module("third_party.external_api")
    platform_service_module = importlib.import_module("third_party.platform_service")
    captured = {}

    def fake_get_favorites(adapter_name=None):
        captured["adapter_name"] = adapter_name
        return {
            "albums": [
                {"album_id": "778811", "title": "Favorite Album", "author": "Fav Author", "pages": 11, "tags": []}
            ]
        }

    class FakePlatformService:
        def download_album(self, platform, original_id, download_dir=None, show_progress=True):
            captured["download"] = {
                "platform": getattr(platform, "value", str(platform)),
                "original_id": str(original_id),
                "download_dir": str(download_dir or ""),
                "show_progress": show_progress,
            }
            return {"local_pages": 6}, True

    monkeypatch.setattr(external_api, "get_favorites", fake_get_favorites)
    monkeypatch.setattr(platform_service_module, "get_platform_service", lambda: FakePlatformService())

    response = client.post(
        "/api/v1/comic/import/online",
        json={
            "import_type": "by_favorite",
            "target": "home",
            "platform": "JM",
        },
    )
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["code"] == 200
    assert payload["data"]["imported_count"] == 1
    assert payload["data"]["downloaded_count"] == 1
    assert captured["adapter_name"] == "jmcomic"
    assert captured["download"]["platform"] == "JM"
    assert captured["download"]["original_id"] == "778811"

    comics = load_json(meta_dir / "comics_database.json").get("comics", [])
    imported = find_by_id(comics, "JM778811")
    assert imported is not None
    assert int(imported["total_page"]) == 6


@pytest.mark.integration
def test_comic_import_online_recommendation_saves_cover_and_preview_contract(third_party_client, monkeypatch):
    """
    用例描述:
    - 用例目的: 看护漫画在线导入 recommendation 分支与第三方封面/预览图接口的交互契约，防止目标库导入后字段缺失。
    - 测试步骤:
      1. mock get_album_by_id 返回单条漫画详情。
      2. mock platform_service.download_cover/get_preview_image_urls。
      3. 调用 POST /api/v1/comic/import/online(import_type=by_id,target=recommendation,platform=PK)。
      4. 校验 recommendations_database.json 中 cover_path/preview_image_urls/preview_pages。
    - 预期结果:
      1. HTTP 200 且业务 code=200。
      2. recommendation 记录带有静态封面路径和预览图 URL。
    - 历史变更:
      - 2026-03-23: 初始创建，覆盖推荐库在线导入契约。
    """
    client = third_party_client["client"]
    config_path = third_party_client["third_party_config_path"]
    data_dir = third_party_client["data_dir"]
    meta_dir = third_party_client["meta_dir"]
    external_api = importlib.import_module("third_party.external_api")
    platform_service_module = importlib.import_module("third_party.platform_service")
    config = load_json(config_path)
    config.setdefault("adapters", {}).setdefault("picacomic", {}).update(
        {"enabled": True, "account": "pk-user", "password": "pk-pass"}
    )
    save_json(config_path, config)
    captured = {"cover": [], "preview": []}

    monkeypatch.setattr(
        external_api,
        "get_album_by_id",
        lambda comic_id, adapter_name: {
            "albums": [
                {
                    "album_id": str(comic_id),
                    "title": "Rec Album",
                    "author": "Rec Author",
                    "pages": 10,
                    "tags": ["Action"],
                }
            ]
        },
    )

    class FakePlatformService:
        def download_cover(self, platform, album_id, save_path, show_progress=False):
            captured["cover"].append(
                {
                    "platform": getattr(platform, "value", str(platform)),
                    "album_id": str(album_id),
                    "save_path": str(save_path),
                    "show_progress": show_progress,
                }
            )
            Path(save_path).parent.mkdir(parents=True, exist_ok=True)
            Path(save_path).write_bytes(b"\xff\xd8\xff\xd9")
            return {"ok": True}, True

        def get_preview_image_urls(self, platform, album_id, preview_pages):
            captured["preview"].append(
                {
                    "platform": getattr(platform, "value", str(platform)),
                    "album_id": str(album_id),
                    "preview_pages": list(preview_pages),
                }
            )
            return [f"https://preview.example/{album_id}/{page}.jpg" for page in preview_pages]

    monkeypatch.setattr(platform_service_module, "get_platform_service", lambda: FakePlatformService())

    response = client.post(
        "/api/v1/comic/import/online",
        json={
            "import_type": "by_id",
            "target": "recommendation",
            "platform": "PK",
            "comic_id": "990011",
        },
    )
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["code"] == 200
    assert payload["data"]["imported_count"] == 1

    recommendations = load_json(meta_dir / "recommendations_database.json").get("recommendations", [])
    imported = find_by_id(recommendations, "PK990011")
    assert imported is not None
    assert str(imported.get("cover_path", "")).startswith("/static/cover/PK/990011.jpg")
    assert imported.get("preview_image_urls")
    assert imported.get("preview_pages")
    assert captured["cover"][0]["platform"] == "PK"
    assert captured["preview"][0]["platform"] == "PK"
    assert (data_dir / "static" / "cover" / "PK" / "990011.jpg").exists()


@pytest.mark.integration
def test_comic_update_check_and_download_forward_platform_contract(third_party_client, monkeypatch):
    """
    用例描述:
    - 用例目的: 看护漫画“在线更新检查/下载”与第三方平台服务交互契约，防止远程页数判断和下载调用参数回归。
    - 测试步骤:
      1. mock platform_service.get_album_by_id 返回 remote pages=5。
      2. mock download_album 在隔离漫画目录补齐新页文件。
      3. 调用 POST /api/v1/comic/update/check 与 /api/v1/comic/update/download。
      4. 校验 has_update、download 参数、落盘 total_page。
    - 预期结果:
      1. 更新检查返回 has_update=true。
      2. 下载调用包含正确 platform/original_id/download_dir。
      3. comics_database.json 对应 total_page 更新为 5。
    - 历史变更:
      - 2026-03-23: 初始创建，覆盖在线更新第三方调用契约。
    """
    client = third_party_client["client"]
    data_dir = third_party_client["data_dir"]
    meta_dir = third_party_client["meta_dir"]
    platform_service_module = importlib.import_module("third_party.platform_service")
    calls = {"meta": [], "download": []}

    class FakePlatformService:
        def get_album_by_id(self, platform, album_id):
            calls["meta"].append({"platform": getattr(platform, "value", str(platform)), "album_id": str(album_id)})
            return {"albums": [{"album_id": str(album_id), "pages": 5}]}

        def download_album(self, platform, album_id, download_dir=None, show_progress=False, **kwargs):
            calls["download"].append(
                {
                    "platform": getattr(platform, "value", str(platform)),
                    "album_id": str(album_id),
                    "download_dir": str(download_dir or ""),
                    "show_progress": show_progress,
                    "kwargs": kwargs,
                }
            )
            comic_dir = Path(data_dir) / "comic" / "JM" / str(album_id)
            comic_dir.mkdir(parents=True, exist_ok=True)
            # 补齐到 5 页，模拟第三方下载后本地文件变更
            for page in (4, 5):
                (comic_dir / f"{page:03d}.png").write_bytes(
                    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
                    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc`\x00\x00\x00\x02\x00\x01"
                    b"\xe2!\xbc3\x00\x00\x00\x00IEND\xaeB`\x82"
                )
            return {"local_pages": 5}, True

        def download_cover(self, platform, album_id, save_path, show_progress=False):
            Path(save_path).parent.mkdir(parents=True, exist_ok=True)
            Path(save_path).write_bytes(b"\xff\xd8\xff\xd9")
            return {"ok": True}, True

    monkeypatch.setattr(platform_service_module, "get_platform_service", lambda: FakePlatformService())

    check_resp = client.post("/api/v1/comic/update/check", json={"comic_id": "JM100001"})
    check_payload = check_resp.get_json()
    assert check_resp.status_code == 200
    assert check_payload["code"] == 200
    assert check_payload["data"]["has_update"] is True
    assert check_payload["data"]["remote_total_page"] == 5

    download_resp = client.post("/api/v1/comic/update/download", json={"comic_id": "JM100001"})
    download_payload = download_resp.get_json()
    assert download_resp.status_code == 200
    assert download_payload["code"] == 200
    assert download_payload["data"]["had_update"] is True
    assert download_payload["data"]["local_page_count"] == 5

    assert calls["meta"][0]["platform"] == "JM"
    assert calls["meta"][0]["album_id"] == "100001"
    assert calls["download"][0]["platform"] == "JM"
    assert calls["download"][0]["album_id"] == "100001"
    assert calls["download"][0]["show_progress"] is False
    assert calls["download"][0]["kwargs"].get("decode_images") is True

    comics = load_json(meta_dir / "comics_database.json").get("comics", [])
    updated = find_by_id(comics, "JM100001")
    assert updated is not None
    assert int(updated["total_page"]) == 5


@pytest.mark.integration
def test_comic_import_async_by_list_forwards_batch_payload_contract(third_party_client, monkeypatch):
    """
    用例描述:
    - 用例目的: 看护漫画异步批量导入(by_list)任务创建契约，防止批量 ID、平台、目标库参数透传错误。
    - 测试步骤:
      1. mock task_manager.create_task 记录参数并返回固定 task_id。
      2. 调用 POST /api/v1/comic/import/async(import_type=by_list)。
      3. 校验 create_task 收到 comic_ids/target/platform 等参数。
    - 预期结果:
      1. HTTP 200 且业务 code=200。
      2. 返回 task_id 与 mock 一致。
      3. create_task 参数与请求完全一致。
    - 历史变更:
      - 2026-03-23: 初始创建，覆盖异步批量导入任务契约。
    """
    client = third_party_client["client"]
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
        return "task-batch-001"

    monkeypatch.setattr(task_manager_module.task_manager, "create_task", fake_create_task)

    response = client.post(
        "/api/v1/comic/import/async",
        json={
            "import_type": "by_list",
            "target": "recommendation",
            "platform": "PK",
            "comic_ids": ["5566", "7788", "9911"],
        },
    )
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["code"] == 200
    assert payload["data"]["task_id"] == "task-batch-001"
    assert captured["platform"] == "PK"
    assert captured["import_type"] == "by_list"
    assert captured["target"] == "recommendation"
    assert captured["comic_ids"] == ["5566", "7788", "9911"]
    assert captured["content_type"] == "comic"
    assert captured["extra_data"] == {}


@pytest.mark.integration
@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        (
            {"import_type": "by_id", "target": "home", "platform": "JM", "comic_id": "M900101"},
            {"platform": "JM", "content_type": "comic", "comic_id": "M900101", "keyword": None, "comic_ids": None, "extra_data": {}},
        ),
        (
            {"import_type": "by_search", "target": "home", "platform": "PK", "keyword": "idol"},
            {"platform": "PK", "content_type": "comic", "comic_id": None, "keyword": "idol", "comic_ids": None, "extra_data": {}},
        ),
        (
            {"import_type": "by_list", "target": "recommendation", "platform": "PK", "comic_ids": ["5566", "7788"]},
            {"platform": "PK", "content_type": "comic", "comic_id": None, "keyword": None, "comic_ids": ["5566", "7788"], "extra_data": {}},
        ),
        (
            {"import_type": "by_id", "target": "home", "platform": "JAVDB", "comic_id": "JVID-101"},
            {"platform": "JAVDB", "content_type": "video", "comic_id": "JVID-101", "keyword": None, "comic_ids": None, "extra_data": {}},
        ),
        (
            {"import_type": "by_search", "target": "recommendation", "platform": "JAVBUS", "keyword": "mina"},
            {"platform": "JAVBUS", "content_type": "video", "comic_id": None, "keyword": "mina", "comic_ids": None, "extra_data": {}},
        ),
        (
            {"import_type": "by_list", "target": "home", "platform": "JAVDB", "comic_ids": ["JVID-1", "JVID-2"]},
            {"platform": "JAVDB", "content_type": "video", "comic_id": None, "keyword": None, "comic_ids": ["JVID-1", "JVID-2"], "extra_data": {}},
        ),
        (
            {
                "import_type": "by_platform_list",
                "target": "recommendation",
                "platform": "JM",
                "platform_list_id": "favorites",
                "platform_list_name": "MyFav",
                "source": "preview",
            },
            {
                "platform": "JM",
                "content_type": "comic",
                "comic_id": "favorites",
                "keyword": "MyFav",
                "comic_ids": None,
                "extra_data": {"platform_list_id": "favorites", "platform_list_name": "MyFav", "source": "preview"},
            },
        ),
        (
            {
                "import_type": "by_platform_list",
                "target": "recommendation",
                "platform": "JAVDB",
                "platform_list_id": "remote-list-88",
                "platform_list_name": "Remote 88",
                "source": "local",
            },
            {
                "platform": "JAVDB",
                "content_type": "video",
                "comic_id": "remote-list-88",
                "keyword": "Remote 88",
                "comic_ids": None,
                "extra_data": {"platform_list_id": "remote-list-88", "platform_list_name": "Remote 88", "source": "local"},
            },
        ),
    ],
)
def test_comic_import_async_matrix_covers_video_and_comic_flows(third_party_client, monkeypatch, payload, expected):
    """
    Case Description:
    - Purpose: Guard async-import task creation matrix across import types/platforms/content types.
    - Steps:
      1. Mock `task_manager.create_task`.
      2. Call `POST /api/v1/comic/import/async` with matrix payloads.
      3. Assert every flow creates task and forwards normalized payload contract.
    - Expected:
      1. HTTP 200 with business `code=200`.
      2. `create_task` receives normalized `platform/content_type` and corresponding params.
      3. `by_platform_list` maps list fields to `comic_id/keyword/extra_data`.
    """
    client = third_party_client["client"]
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
        captured.clear()
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
        return "task-matrix-001"

    monkeypatch.setattr(task_manager_module.task_manager, "create_task", fake_create_task)

    response = client.post("/api/v1/comic/import/async", json=payload)
    result = response.get_json()

    assert response.status_code == 200
    assert result["code"] == 200
    assert result["data"]["task_id"] == "task-matrix-001"
    assert captured["platform"] == expected["platform"]
    assert captured["import_type"] == payload["import_type"]
    assert captured["target"] == payload["target"]
    assert captured["content_type"] == expected["content_type"]
    assert captured["comic_id"] == expected["comic_id"]
    assert captured["keyword"] == expected["keyword"]
    assert captured["comic_ids"] == expected["comic_ids"]
    assert captured["extra_data"] == expected["extra_data"]


@pytest.mark.integration
def test_task_manager_execute_import_dispatches_by_content_type_and_import_type(third_party_client, monkeypatch):
    """
    Case Description:
    - Purpose: Guard task-manager dispatch routing so video tasks never enter comic import branch.
    - Steps:
      1. Mock `_execute_video_import/_execute_comic_import/_execute_platform_list_import/_execute_migrate_to_local`.
      2. Build representative video/comic/platform-list/migrate tasks.
      3. Call `_execute_import` and assert dispatch target.
    - Expected:
      1. `platform=JAVDB` with inferred video content goes to video executor.
      2. `platform=JM` with inferred comic content goes to comic executor.
      3. `import_type=by_platform_list` always goes to platform-list executor.
      4. `import_type=migrate_to_local` always goes to migrate executor.
    """
    task_manager_module = importlib.import_module("infrastructure.task_manager")
    manager = task_manager_module.task_manager
    ImportTask = task_manager_module.ImportTask
    TaskStatus = task_manager_module.TaskStatus

    calls = []

    monkeypatch.setattr(
        manager,
        "_execute_video_import",
        lambda task: calls.append(("video", task.platform, task.import_type)) or {"success": True, "content_type": "video"},
    )
    monkeypatch.setattr(
        manager,
        "_execute_comic_import",
        lambda task: calls.append(("comic", task.platform, task.import_type)) or {"success": True, "content_type": "comic"},
    )
    monkeypatch.setattr(
        manager,
        "_execute_platform_list_import",
        lambda task: calls.append(("platform_list", task.platform, task.import_type)) or {"success": True, "content_type": "video"},
    )
    monkeypatch.setattr(
        manager,
        "_execute_migrate_to_local",
        lambda task: calls.append(("migrate_to_local", task.platform, task.import_type)) or {"success": True, "content_type": task.content_type or "comic"},
    )

    def build_task(task_id, platform, import_type, content_type="", comic_id=None, keyword=None, comic_ids=None, extra_data=None):
        return ImportTask(
            task_id=task_id,
            status=TaskStatus.PENDING,
            platform=platform,
            import_type=import_type,
            target="home",
            comic_id=comic_id,
            keyword=keyword,
            comic_ids=comic_ids,
            title="t",
            progress=0,
            total_pages=0,
            downloaded_pages=0,
            message="m",
            create_time="2026-03-25T00:00:00",
            start_time=None,
            complete_time=None,
            error_msg=None,
            result=None,
            content_type=content_type,
            extra_data=extra_data or {},
        )

    video_task = build_task("task-v", "JAVDB", "by_id", content_type="", comic_id="JVID-7")
    comic_task = build_task("task-c", "JM", "by_search", content_type="", keyword="idol")
    list_task = build_task(
        "task-l",
        "JAVBUS",
        "by_platform_list",
        content_type="video",
        comic_id="fav",
        keyword="Fav",
        extra_data={"platform_list_id": "fav"},
    )
    migrate_task = build_task(
        "task-m",
        "JAVDB",
        "migrate_to_local",
        content_type="video",
        comic_ids=["JAVDB_AAA111", "JAVBUS_BBB222"],
    )

    video_result = manager._execute_import(video_task)
    comic_result = manager._execute_import(comic_task)
    list_result = manager._execute_import(list_task)
    migrate_result = manager._execute_import(migrate_task)

    assert video_result["content_type"] == "video"
    assert comic_result["content_type"] == "comic"
    assert list_result["content_type"] == "video"
    assert migrate_result["content_type"] == "video"
    assert calls == [
        ("video", "JAVDB", "by_id"),
        ("comic", "JM", "by_search"),
        ("platform_list", "JAVBUS", "by_platform_list"),
        ("migrate_to_local", "JAVDB", "migrate_to_local"),
    ]
