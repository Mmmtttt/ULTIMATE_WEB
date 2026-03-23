from __future__ import annotations

from types import SimpleNamespace

import pytest


def _ok_result(data=None, message="ok"):
    return SimpleNamespace(success=True, data=data, message=message)


@pytest.mark.integration
def test_author_service_search_works_forwards_platform_adapter_contract(third_party_client, monkeypatch):
    """
    用例描述:
    - 用例目的: 看护作者服务 _search_works 对 third_party.external_api.search_albums 的调用契约，防止平台映射/参数透传错误。
    - 测试步骤:
      1. mock author_service._get_external_api.search_albums 记录参数并返回 JM/PK 各一条作品。
      2. 调用 author_service._search_works("Alice", page=1, max_pages=2)。
      3. 校验 adapter_name/max_pages/fast_mode 参数和返回平台字段。
    - 预期结果:
      1. search_albums 分别以 jmcomic/picacomic 被调用。
      2. max_pages=2、fast_mode=True 被正确传递。
      3. 返回 works 同时包含 JM、PK 平台。
    - 历史变更:
      - 2026-03-23: 初始创建，覆盖作者第三方搜索契约。
    """
    author_api = third_party_client["author_api"]
    service = author_api.author_service
    calls = []

    class FakeExternalApi:
        def search_albums(self, keyword, max_pages=1, adapter_name=None, fast_mode=False):
            calls.append(
                {
                    "keyword": keyword,
                    "max_pages": max_pages,
                    "adapter_name": adapter_name,
                    "fast_mode": fast_mode,
                }
            )
            if adapter_name == "jmcomic":
                return {"albums": [{"album_id": "1001", "title": "JM Work", "cover_url": "u1", "pages": 5}]}
            return {"albums": [{"album_id": "2001", "title": "PK Work", "cover_url": "u2", "pages": 6}]}

    monkeypatch.setattr(service, "_get_external_api", lambda: FakeExternalApi())

    result = service._search_works("Alice", page=1, max_pages=2)
    works = result.get("works", [])

    assert len(calls) == 2
    assert {item["adapter_name"] for item in calls} == {"jmcomic", "picacomic"}
    assert all(item["keyword"] == "Alice" for item in calls)
    assert all(int(item["max_pages"]) == 2 for item in calls)
    assert all(item["fast_mode"] is True for item in calls)
    assert {item["platform"] for item in works} == {"JM", "PK"}


@pytest.mark.integration
def test_author_batch_detail_calls_get_album_by_id_and_preserves_id_order(third_party_client, monkeypatch):
    """
    用例描述:
    - 用例目的: 看护作者批量详情接口对 get_album_by_id 的调用契约与返回顺序，防止并发回调导致顺序错乱。
    - 测试步骤:
      1. mock external_api.get_album_by_id 按 id 生成详情并记录调用。
      2. 调用 author_service.get_works_batch_detail(["3002","3001"])。
      3. 校验调用集合和返回 works 顺序。
    - 预期结果:
      1. 两个 id 均被调用。
      2. 返回顺序与入参顺序一致。
    - 历史变更:
      - 2026-03-23: 初始创建，覆盖批量详情并发顺序契约。
    """
    author_api = third_party_client["author_api"]
    service = author_api.author_service
    calls = []

    class FakeExternalApi:
        def get_album_by_id(self, work_id):
            calls.append(str(work_id))
            return {
                "albums": [
                    {
                        "album_id": str(work_id),
                        "title": f"title-{work_id}",
                        "author": f"author-{work_id}",
                        "cover_url": f"https://img/{work_id}.jpg",
                        "pages": 9,
                    }
                ]
            }

    monkeypatch.setattr(service, "_get_external_api", lambda: FakeExternalApi())

    result = service.get_works_batch_detail(["3002", "3001"])
    assert result.success is True
    works = result.data["works"]
    assert len(works) == 2
    assert set(calls) == {"3001", "3002"}
    assert [item["id"] for item in works] == ["3002", "3001"]
    assert works[0]["title"] == "title-3002"


@pytest.mark.integration
def test_author_new_works_endpoint_enriches_results_via_external_detail(third_party_client, monkeypatch):
    """
    用例描述:
    - 用例目的: 看护作者“新作品”链路在第三方搜索后补全详情的调用契约，防止 get_album_by_id 丢失导致作品字段不完整。
    - 测试步骤:
      1. 先订阅一个作者，拿到 author_id。
      2. mock external_api.search_albums/get_album_by_id。
      3. 调用 GET /api/v1/author/new-works/<author_id>。
      4. 校验返回作品字段来自详情补全，且第三方函数被调用。
    - 预期结果:
      1. HTTP 200 且业务 code=200。
      2. new_works 至少包含一条并带 author/cover_url/pages。
      3. search_albums 与 get_album_by_id 均被触发。
    - 历史变更:
      - 2026-03-23: 初始创建，覆盖作者新作详情补全契约。
    """
    client = third_party_client["client"]
    author_api = third_party_client["author_api"]
    service = author_api.author_service
    calls = {"search": [], "detail": []}

    sub_resp = client.post("/api/v1/author/subscribe", json={"name": "Author-TP-A"})
    sub_payload = sub_resp.get_json()
    assert sub_resp.status_code == 200
    assert sub_payload["code"] == 200
    author_id = sub_payload["data"]["id"]

    class FakeExternalApi:
        def search_albums(self, keyword, max_pages=1, adapter_name=None, fast_mode=False):
            calls["search"].append(
                {
                    "keyword": keyword,
                    "max_pages": max_pages,
                    "adapter_name": adapter_name,
                    "fast_mode": fast_mode,
                }
            )
            if adapter_name == "jmcomic":
                return {"albums": [{"album_id": "91001", "title": "JM Raw", "cover_url": "u1", "pages": 4}]}
            return {"albums": [{"album_id": "92001", "title": "PK Raw", "cover_url": "u2", "pages": 5}]}

        def get_album_by_id(self, work_id):
            calls["detail"].append(str(work_id))
            return {
                "albums": [
                    {
                        "album_id": str(work_id),
                        "title": f"Detail-{work_id}",
                        "author": "Author-TP-A",
                        "cover_url": f"https://img/{work_id}.jpg",
                        "pages": 11,
                    }
                ]
            }

    monkeypatch.setattr(service, "_get_external_api", lambda: FakeExternalApi())

    response = client.get(f"/api/v1/author/new-works/{author_id}")
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["code"] == 200
    new_works = payload["data"]["new_works"]
    assert len(new_works) >= 1
    assert all(item.get("author") == "Author-TP-A" for item in new_works)
    assert all(str(item.get("cover_url", "")).startswith("https://img/") for item in new_works)
    assert len(calls["search"]) >= 2
    assert {"jmcomic", "picacomic"}.issubset({item["adapter_name"] for item in calls["search"]})
    assert len(calls["detail"]) >= 1


@pytest.mark.integration
def test_author_batch_detail_route_forwards_ids(third_party_client, monkeypatch):
    """
    用例描述:
    - 用例目的: 看护作者批量详情路由层参数透传契约，防止 ids 参数在 API 层被改写或丢失。
    - 测试步骤:
      1. mock author_service.get_works_batch_detail 记录 ids。
      2. 调用 POST /api/v1/author/works/batch-detail。
      3. 校验 ids 顺序和响应结构。
    - 预期结果:
      1. HTTP 200 且业务 code=200。
      2. 服务层收到的 ids 与请求保持一致。
    - 历史变更:
      - 2026-03-23: 初始创建，覆盖作者批量详情路由契约。
    """
    client = third_party_client["client"]
    author_api = third_party_client["author_api"]
    captured = {}

    def fake_batch_detail(ids):
        captured["ids"] = ids
        return _ok_result({"works": [{"id": item} for item in ids]})

    monkeypatch.setattr(
        author_api.author_service,
        "get_works_batch_detail",
        fake_batch_detail,
    )

    response = client.post("/api/v1/author/works/batch-detail", json={"ids": ["A1", "A2", "A3"]})
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["code"] == 200
    assert captured["ids"] == ["A1", "A2", "A3"]
