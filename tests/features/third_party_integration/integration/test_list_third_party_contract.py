from __future__ import annotations

import importlib
from types import SimpleNamespace

import pytest

from tests.shared.runtime_data import load_json, save_json


def _ok_result(data=None, message="ok"):
    return SimpleNamespace(success=True, data=data, message=message)


@pytest.mark.integration
def test_list_platform_lists_jm_returns_virtual_favorites(third_party_client):
    """
    用例描述:
    - 用例目的: 看护漫画平台(JM/PK)“用户清单列表”契约，确保返回虚拟收藏夹清单而不依赖远程真实清单接口。
    - 测试步骤:
      1. 调用 GET /api/v1/list/platform/lists?platform=JM。
      2. 校验返回清单列表结构和 favorites 固定清单。
    - 预期结果:
      1. HTTP 200 且业务 code=200。
      2. 返回至少一个 list，且包含 list_id=favorites。
    - 历史变更:
      - 2026-03-23: 初始创建，覆盖平台清单列表虚拟收藏夹分支。
    """
    client = third_party_client["client"]

    response = client.get("/api/v1/list/platform/lists", query_string={"platform": "JM"})
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["code"] == 200
    assert payload["data"]["lists"][0]["list_id"] == "favorites"


@pytest.mark.integration
def test_list_platform_lists_javdb_forwards_protocol_collection_list_contract(third_party_client, monkeypatch):
    """
    用例描述:
    - 用例目的: 看护视频平台(JAVDB)用户清单列表改走协议能力 `collection.list`，防止宿主继续依赖 PlatformService/平台枚举。
    - 测试步骤:
      1. mock list_service._execute_platform_capability，记录 plugin/capability。
      2. 调用 GET /api/v1/list/platform/lists?platform=JAVDB。
      3. 校验调用参数与返回结构。
    - 预期结果:
      1. HTTP 200 且业务 code=200。
      2. 宿主调用 `video.javdb` 插件的 `collection.list` 能力。
    - 历史变更:
      - 2026-03-23: 初始创建，覆盖 JAVDB 清单列表第三方调用契约。
    """
    client = third_party_client["client"]
    list_api = third_party_client["list_api"]
    calls = {}

    def fake_execute(manifest, capability, params=None):
        calls["plugin_id"] = manifest.plugin_id
        calls["capability"] = capability
        calls["params"] = params or {}
        return {"lists": [{"list_id": "L-1", "list_name": "Remote List", "total": 12}]}

    monkeypatch.setattr(list_api.list_service, "_execute_platform_capability", fake_execute)

    response = client.get("/api/v1/list/platform/lists", query_string={"platform": "JAVDB"})
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["code"] == 200
    assert calls["plugin_id"] == "video.javdb"
    assert calls["capability"] == "collection.list"
    assert calls["params"] == {}
    assert payload["data"]["lists"][0]["list_id"] == "L-1"


@pytest.mark.integration
def test_list_platform_favorites_detail_maps_album_fields(third_party_client, monkeypatch):
    """
    用例描述:
    - 用例目的: 看护 JM/PK favorites 详情接口对 get_favorites_basic 的字段映射契约，防止 album_id/comic_id/title 映射回归。
    - 测试步骤:
      1. mock get_favorites_basic 返回一条 album。
      2. 调用 GET /api/v1/list/platform/list/detail?platform=JM&list_id=favorites。
      3. 校验 works 中字段映射和 total。
    - 预期结果:
      1. HTTP 200 且业务 code=200。
      2. works[0] 同时包含 album_id 与 comic_id，且 total 与 works 数量一致。
    - 历史变更:
      - 2026-03-23: 初始创建，覆盖收藏夹详情字段映射契约。
    """
    client = third_party_client["client"]
    list_api = third_party_client["list_api"]

    def fake_execute(manifest, capability, params=None):
        assert manifest.plugin_id == "comic.jmcomic"
        assert capability == "collection.favorites_basic"
        return {
            "albums": [
                {
                    "album_id": "88001",
                    "title": "Fav Album",
                    "author": "Author X",
                    "cover_url": "https://img.example/88001.jpg",
                    "tags": ["A", "B"],
                }
            ]
        }

    monkeypatch.setattr(list_api.list_service, "_execute_platform_capability", fake_execute)

    response = client.get(
        "/api/v1/list/platform/list/detail",
        query_string={"platform": "JM", "list_id": "favorites"},
    )
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["code"] == 200
    assert payload["data"]["total"] == 1
    assert payload["data"]["works"][0]["album_id"] == "88001"
    assert payload["data"]["works"][0]["comic_id"] == "88001"
    assert payload["data"]["works"][0]["title"] == "Fav Album"
    assert payload["data"]["works"][0]["plugin_id"] == "comic.jmcomic"


@pytest.mark.integration
def test_list_import_platform_list_javdb_creates_tracking_and_imports(third_party_client, monkeypatch):
    """
    用例描述:
    - 用例目的: 看护“导入平台清单(JAVDB)”主链路，确保会创建/更新本地跟踪清单并把 works 透传到通用视频导入器。
    - 测试步骤:
      1. mock get_list_detail 返回远程 works。
      2. mock _import_platform_videos 记录入参。
      3. 调用 POST /api/v1/list/import。
      4. 校验返回 list_id 和隔离 lists_database.json 中跟踪清单字段。
    - 预期结果:
      1. HTTP 200 且业务 code=200。
      2. 通用视频导入器收到远程 works 与创建的目标 list_id。
      3. 跟踪清单落盘并包含 platform/platform_list_id/import_source。
    - 历史变更:
      - 2026-03-23: 初始创建，覆盖平台清单导入契约。
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
        return "task-list-javdb-001"

    monkeypatch.setattr(task_manager_module.task_manager, "create_task", fake_create_task)

    response = client.post(
        "/api/v1/list/import",
        json={
            "platform": "JAVDB",
            "platform_list_id": "remote-list-7",
            "platform_list_name": "My Remote",
            "source": "local",
        },
    )
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["code"] == 200
    assert payload["data"]["task_id"] == "task-list-javdb-001"
    assert payload["data"]["content_type"] == "video"
    assert captured["platform"] == "JAVDB"
    assert captured["import_type"] == "by_platform_list"
    assert captured["target"] == "recommendation"
    assert captured["comic_id"] == "remote-list-7"
    assert captured["keyword"] == "My Remote"
    assert captured["comic_ids"] is None
    assert captured["content_type"] == "video"
    assert captured["extra_data"] == {
        "platform_list_id": "remote-list-7",
        "platform_list_name": "My Remote",
        "source": "preview",
    }


@pytest.mark.integration
def test_list_sync_platform_list_javdb_imports_only_new_codes(third_party_client, monkeypatch):
    """
    用例描述:
    - 用例目的: 看护 JAVDB 清单同步去重逻辑，确保仅把“远程新增 code”传给通用视频导入器，防止重复导入。
    - 测试步骤:
      1. 在隔离库中创建一个远程跟踪清单，并让本地已存在视频绑定该清单。
      2. mock get_list_detail 返回“一个已存在 code + 一个新 code”。
      3. mock _import_platform_videos 记录收到的 works。
      4. 调用 POST /api/v1/list/sync。
    - 预期结果:
      1. 通用视频导入器仅收到新增 code 对应的 works。
      2. 接口返回业务成功并回传 list_id。
    - 历史变更:
      - 2026-03-23: 初始创建，覆盖同步去重核心契约。
    """
    client = third_party_client["client"]
    list_api = third_party_client["list_api"]
    meta_dir = third_party_client["meta_dir"]
    list_id = "list_remote_javdb_sync"
    captured = {}

    lists_payload = load_json(meta_dir / "lists_database.json")
    lists_payload.setdefault("lists", []).append(
        {
            "id": list_id,
            "name": "Remote JAVDB Sync List",
            "desc": "remote sync",
            "content_type": "video",
            "is_default": False,
            "create_time": "2026-03-23T10:00:00",
            "platform": "JAVDB",
            "platform_list_id": "remote-sync-88",
            "import_source": "local",
            "last_sync_time": "",
        }
    )
    save_json(meta_dir / "lists_database.json", lists_payload)

    videos_payload = load_json(meta_dir / "videos_database.json")
    for item in videos_payload.get("videos", []):
        if item.get("id") == "JAVDB900001":
            item["list_ids"] = sorted(set((item.get("list_ids") or []) + [list_id]))
    save_json(meta_dir / "videos_database.json", videos_payload)

    def fake_load(manifest, remote_list_id):
        captured["plugin_id"] = manifest.plugin_id
        captured["remote_list_id"] = remote_list_id
        return {
            "works": [
                {"video_id": "900001", "code": "TEST-900001", "title": "Existing"},
                {"video_id": "900099", "code": "TEST-900099", "title": "New One"},
            ]
        }

    def fake_import(works, target_list_id, source, platform_str="JAVDB"):
        captured["works"] = works
        captured["target_list_id"] = target_list_id
        captured["source"] = source
        captured["platform_str"] = platform_str
        return _ok_result({"imported_count": len(works), "skipped_count": 0, "total_count": len(works)})

    monkeypatch.setattr(list_api.list_service, "_load_platform_list_payload", fake_load)
    monkeypatch.setattr(list_api.list_service, "_import_platform_videos", fake_import)

    response = client.post("/api/v1/list/sync", json={"list_id": list_id})
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["code"] == 200
    assert captured["plugin_id"] == "video.javdb"
    assert captured["remote_list_id"] == "remote-sync-88"
    assert captured["target_list_id"] == list_id
    assert captured["source"] == "local"
    assert captured["platform_str"] == "JAVDB"
    assert len(captured["works"]) == 1
    assert captured["works"][0]["code"] == "TEST-900099"
    assert payload["data"]["list_id"] == list_id


@pytest.mark.integration
def test_list_favorites_routes_forward_platform_and_validate_input(third_party_client, monkeypatch):
    """
    用例描述:
    - 用例目的: 看护“导入收藏夹/同步收藏夹”路由契约，确保平台参数校验与服务层调用参数一致。
    - 测试步骤:
      1. mock import_platform_favorites/sync_platform_favorites 记录参数。
      2. 调用 POST /api/v1/list/import/favorites 与 /api/v1/list/sync/favorites。
      3. 再调用一次非法平台验证错误分支。
    - 预期结果:
      1. 合法请求返回 code=200，且服务层收到平台大写和值 source。
      2. 非法平台返回业务 code=400。
    - 历史变更:
      - 2026-03-23: 初始创建，覆盖收藏夹导入/同步路由契约。
    """
    client = third_party_client["client"]
    list_api = third_party_client["list_api"]
    calls = {"import": [], "sync": []}

    monkeypatch.setattr(
        list_api.list_service,
        "import_platform_favorites",
        lambda platform, source="local": calls["import"].append((platform, source))
        or _ok_result({"imported_count": 2, "skipped_count": 0, "total_count": 2}),
    )
    monkeypatch.setattr(
        list_api.list_service,
        "sync_platform_favorites",
        lambda platform, source="local": calls["sync"].append((platform, source))
        or _ok_result({"imported_count": 1, "skipped_count": 0, "total_count": 3}),
    )

    import_resp = client.post("/api/v1/list/import/favorites", json={"platform": "jm", "source": "preview"})
    import_payload = import_resp.get_json()
    assert import_resp.status_code == 200
    assert import_payload["code"] == 200
    assert calls["import"] == [("JM", "preview")]

    sync_resp = client.post("/api/v1/list/sync/favorites", json={"platform": "PK", "source": "local"})
    sync_payload = sync_resp.get_json()
    assert sync_resp.status_code == 200
    assert sync_payload["code"] == 200
    assert calls["sync"] == [("PK", "local")]

    invalid_resp = client.post("/api/v1/list/import/favorites", json={"platform": "JAVBUS"})
    invalid_payload = invalid_resp.get_json()
    assert invalid_resp.status_code == 200
    assert invalid_payload["code"] == 400


@pytest.mark.integration
def test_list_import_favorites_jm_uses_platform_favorites_and_creates_tracking_list(third_party_client, monkeypatch):
    """
    Case Description:
    - Purpose: Guard JM favorites import chain beyond route forwarding: favorites fetch mapping + tracking list creation.
    - Steps:
      1. Mock platform service `get_favorites_basic` to return two albums.
      2. Keep real `import_platform_favorites -> import_platform_list` chain, mock only `_import_comics`.
      3. Call `POST /api/v1/list/import/favorites`.
      4. Verify mapped works, platform argument, and persisted tracking list fields.
    - Expected:
      1. HTTP 200 with business `code=200`.
      2. `_import_comics` receives mapped favorites works and protocol platform string `JM`.
      3. `lists_database.json` includes tracking list with `platform=JM` and `platform_list_id=favorites`.
    - History:
      - 2026-03-23: Added strong guard for comic favorites import chain.
    """
    client = third_party_client["client"]
    list_api = third_party_client["list_api"]
    meta_dir = third_party_client["meta_dir"]
    captured = {}

    def fake_execute(manifest, capability, params=None):
        assert manifest.plugin_id == "comic.jmcomic"
        assert capability == "collection.favorites_basic"
        return {
            "albums": [
                {"album_id": "100001", "title": "Fav-A", "author": "A", "cover_url": "u1", "tags": ["t1"]},
                {"comic_id": "100777", "title": "Fav-B", "author": "B", "cover_url": "u2", "tags": ["t2"]},
            ]
        }

    def fake_import_comics(works, target_list_id, source, platform, platform_str=""):
        captured["works"] = works
        captured["target_list_id"] = target_list_id
        captured["source"] = source
        captured["platform"] = platform
        captured["platform_is_string"] = isinstance(platform, str)
        captured["platform_str"] = platform_str
        return _ok_result({"imported_count": len(works), "skipped_count": 0, "total_count": len(works)})

    monkeypatch.setattr(list_api.list_service, "_execute_platform_capability", fake_execute)
    monkeypatch.setattr(list_api.list_service, "_import_comics", fake_import_comics)

    response = client.post("/api/v1/list/import/favorites", json={"platform": "JM", "source": "local"})
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["code"] == 200
    assert captured["platform"] == "JM"
    assert captured["platform_is_string"] is True
    assert captured["platform_str"] == "JM"
    assert captured["source"] == "local"
    assert len(captured["works"]) == 2
    assert captured["works"][0]["album_id"] == "100001"
    assert captured["works"][1]["comic_id"] == "100777"
    assert captured["works"][0]["plugin_id"] == "comic.jmcomic"

    lists = load_json(meta_dir / "lists_database.json").get("lists", [])
    created = next((item for item in lists if item.get("id") == captured["target_list_id"]), None)
    assert created is not None
    assert created["platform"] == "JM"
    assert created["platform_list_id"] == "favorites"
    assert created["import_source"] == "local"


@pytest.mark.integration
def test_list_sync_favorites_jm_imports_only_new_comics(third_party_client, monkeypatch):
    """
    Case Description:
    - Purpose: Guard JM favorites sync de-dup logic so only newly discovered comics are passed to importer.
    - Steps:
      1. Create JM favorites tracking list via real import chain (mock importer only).
      2. Bind existing comic to that list in isolated metadata.
      3. Mock favorites source to return one existing + one new album.
      4. Call `POST /api/v1/list/sync/favorites` and verify importer input.
    - Expected:
      1. HTTP 200 with business `code=200`.
      2. Importer receives only the new album.
      3. Target list id remains the existing JM favorites tracking list.
    - History:
      - 2026-03-23: Added comic favorites sync de-dup guard.
    """
    client = third_party_client["client"]
    list_api = third_party_client["list_api"]
    meta_dir = third_party_client["meta_dir"]
    import_captured = {}
    sync_captured = {}

    def fake_execute_import(manifest, capability, params=None):
        assert manifest.plugin_id == "comic.jmcomic"
        assert capability == "collection.favorites_basic"
        return {"albums": [{"album_id": "100001", "title": "Existing", "author": "A", "cover_url": "u1", "tags": []}]}

    def fake_import_comics_for_create(works, target_list_id, source, platform, platform_str=""):
        import_captured["target_list_id"] = target_list_id
        import_captured["source"] = source
        import_captured["platform"] = platform
        import_captured["platform_is_string"] = isinstance(platform, str)
        import_captured["platform_str"] = platform_str
        return _ok_result({"imported_count": len(works), "skipped_count": 0, "total_count": len(works)})

    monkeypatch.setattr(list_api.list_service, "_execute_platform_capability", fake_execute_import)
    monkeypatch.setattr(list_api.list_service, "_import_comics", fake_import_comics_for_create)

    create_resp = client.post("/api/v1/list/import/favorites", json={"platform": "JM", "source": "local"})
    create_payload = create_resp.get_json()
    assert create_resp.status_code == 200
    assert create_payload["code"] == 200
    favorites_list_id = import_captured["target_list_id"]

    comics_payload = load_json(meta_dir / "comics_database.json")
    for item in comics_payload.get("comics", []):
        if item.get("id") == "JM100001":
            item["list_ids"] = sorted(set((item.get("list_ids") or []) + [favorites_list_id]))
    save_json(meta_dir / "comics_database.json", comics_payload)

    def fake_execute_sync(manifest, capability, params=None):
        assert manifest.plugin_id == "comic.jmcomic"
        assert capability == "collection.favorites_basic"
        return {
            "albums": [
                {"album_id": "100001", "title": "Existing", "author": "A", "cover_url": "u1", "tags": []},
                {"album_id": "100889", "title": "New Favorite", "author": "B", "cover_url": "u2", "tags": []},
            ]
        }

    def fake_import_comics_for_sync(works, target_list_id, source, platform, platform_str=""):
        sync_captured["works"] = works
        sync_captured["target_list_id"] = target_list_id
        sync_captured["source"] = source
        sync_captured["platform"] = platform
        sync_captured["platform_is_string"] = isinstance(platform, str)
        sync_captured["platform_str"] = platform_str
        return _ok_result({"imported_count": len(works), "skipped_count": 0, "total_count": 2})

    monkeypatch.setattr(list_api.list_service, "_execute_platform_capability", fake_execute_sync)
    monkeypatch.setattr(list_api.list_service, "_import_comics", fake_import_comics_for_sync)

    sync_resp = client.post("/api/v1/list/sync/favorites", json={"platform": "JM", "source": "local"})
    sync_payload = sync_resp.get_json()

    assert sync_resp.status_code == 200
    assert sync_payload["code"] == 200
    assert sync_captured["target_list_id"] == favorites_list_id
    assert sync_captured["platform"] == "JM"
    assert sync_captured["platform_is_string"] is True
    assert sync_captured["platform_str"] == "JM"
    assert sync_captured["source"] == "local"
    assert len(sync_captured["works"]) == 1
    assert sync_captured["works"][0]["album_id"] == "100889"


@pytest.mark.integration
def test_list_platform_list_detail_javdb_forwards_get_list_detail_contract(third_party_client, monkeypatch):
    """
    Case Description:
    - Purpose: Guard `/api/v1/list/platform/list/detail` non-favorites branch for JAVDB:
      route/service must forward `list_id` into protocol `collection.detail`.
    - Steps:
      1. Mock `list_service._execute_platform_capability` and record plugin/capability/list_id.
      2. Call `GET /api/v1/list/platform/list/detail?platform=JAVDB&list_id=remote-l-11`.
      3. Assert forwarded arguments and response payload.
    - Expected:
      1. HTTP 200 with business `code=200`.
      2. Third-party call receives `video.javdb / collection.detail / remote-l-11`.
      3. Response data contains mocked works list.
    - History:
      - 2026-03-23: Added non-favorites list-detail third-party contract guard.
    """
    client = third_party_client["client"]
    list_api = third_party_client["list_api"]
    captured = {}

    def fake_execute(manifest, capability, params=None):
        captured["plugin_id"] = manifest.plugin_id
        captured["capability"] = capability
        captured["list_id"] = (params or {}).get("list_id")
        return {
            "list_id": (params or {}).get("list_id"),
            "list_name": "Remote List 11",
            "total": 2,
            "works": [
                {"video_id": "9911", "code": "TP-9911", "title": "Remote-1"},
                {"video_id": "9912", "code": "TP-9912", "title": "Remote-2"},
            ],
        }

    monkeypatch.setattr(list_api.list_service, "_execute_platform_capability", fake_execute)

    response = client.get(
        "/api/v1/list/platform/list/detail",
        query_string={"platform": "JAVDB", "list_id": "remote-l-11"},
    )
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["code"] == 200
    assert captured == {
        "plugin_id": "video.javdb",
        "capability": "collection.detail",
        "list_id": "remote-l-11",
    }
    assert payload["data"]["works"][0]["code"] == "TP-9911"
    assert payload["data"]["total"] == 2
    assert payload["data"]["works"][0]["plugin_id"] == "video.javdb"


@pytest.mark.integration
def test_list_import_platform_list_jm_favorites_branch_forwards_import_comics_contract(third_party_client, monkeypatch):
    """
    Case Description:
    - Purpose: Guard `/api/v1/list/import` comic favorites branch (`platform=JM`, `platform_list_id=favorites`):
      favorites fetch mapping and importer invocation contract.
    - Steps:
      1. Mock platform service `get_favorites_basic`.
      2. Mock `list_service._import_comics` to capture args.
      3. Call `POST /api/v1/list/import` for JM favorites.
      4. Assert mapped works, platform/source args, and tracking-list persistence.
    - Expected:
      1. HTTP 200 with business `code=200`.
      2. `_import_comics` receives mapped favorites works and protocol platform string `JM`.
      3. Persisted tracking list includes `platform=JM`, `platform_list_id=favorites`, `import_source=preview`.
    - History:
      - 2026-03-23: Added JM favorites branch contract guard for platform list import API.
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
        return "task-list-jm-favorites-001"

    monkeypatch.setattr(task_manager_module.task_manager, "create_task", fake_create_task)

    response = client.post(
        "/api/v1/list/import",
        json={
            "platform": "JM",
            "platform_list_id": "favorites",
            "platform_list_name": "MyFav",
            "source": "preview",
        },
    )
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["code"] == 200
    assert payload["data"]["task_id"] == "task-list-jm-favorites-001"
    assert payload["data"]["content_type"] == "comic"
    assert captured["platform"] == "JM"
    assert captured["import_type"] == "by_platform_list"
    assert captured["target"] == "recommendation"
    assert captured["comic_id"] == "favorites"
    assert captured["keyword"] == "MyFav"
    assert captured["comic_ids"] is None
    assert captured["content_type"] == "comic"
    assert captured["extra_data"] == {
        "platform_list_id": "favorites",
        "platform_list_name": "MyFav",
        "source": "preview",
    }


@pytest.mark.integration
@pytest.mark.parametrize(
    ("platform", "expected_content_type"),
    [
        ("JM", "comic"),
        ("PK", "comic"),
        ("JAVDB", "video"),
        ("JAVBUS", "video"),
    ],
)
def test_list_import_route_async_task_matrix_by_platform(third_party_client, monkeypatch, platform, expected_content_type):
    """
    Case Description:
    - Purpose: Guard platform-list import async contract across comic/video platforms.
    - Steps:
      1. Mock `task_manager.create_task`.
      2. Call `POST /api/v1/list/import` with platform list payload.
      3. Assert normalized async payload contract.
    - Expected:
      1. Route always creates async task (`by_platform_list`).
      2. Route always enforces `target=recommendation` and `extra_data.source=preview`.
      3. `content_type` maps by platform (`JM/PK=comic`, `JAVDB/JAVBUS=video`).
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
        return "task-list-matrix-001"

    monkeypatch.setattr(task_manager_module.task_manager, "create_task", fake_create_task)

    response = client.post(
        "/api/v1/list/import",
        json={
            "platform": platform,
            "platform_list_id": f"{platform}-remote-list-1",
            "platform_list_name": f"{platform} Remote List",
            "source": "local",
        },
    )
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["code"] == 200
    assert payload["data"]["task_id"] == "task-list-matrix-001"
    assert payload["data"]["content_type"] == expected_content_type
    assert captured["platform"] == platform
    assert captured["import_type"] == "by_platform_list"
    assert captured["target"] == "recommendation"
    assert captured["comic_id"] == f"{platform}-remote-list-1"
    assert captured["keyword"] == f"{platform} Remote List"
    assert captured["comic_ids"] is None
    assert captured["content_type"] == expected_content_type
    assert captured["extra_data"] == {
        "platform_list_id": f"{platform}-remote-list-1",
        "platform_list_name": f"{platform} Remote List",
        "source": "preview",
    }
