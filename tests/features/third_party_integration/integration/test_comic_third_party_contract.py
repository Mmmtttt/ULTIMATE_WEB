from __future__ import annotations

import importlib

import pytest

from tests.shared.runtime_data import find_by_id, load_json


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
    assert "_jdb_session=session-token" in returned_cookie_string
    assert "over18=1" in returned_cookie_string


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
    external_api = importlib.import_module("third_party.external_api")
    platform_service_module = importlib.import_module("third_party.platform_service")

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
