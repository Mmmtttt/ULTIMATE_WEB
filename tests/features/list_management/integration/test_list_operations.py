from __future__ import annotations

from uuid import uuid4

import pytest
import requests

from tests.shared.runtime_data import find_by_id, load_json


@pytest.mark.integration
def test_list_create_persists(integration_runtime):
    """
    用例描述:
    - 用例目的: 验证清单创建接口能正确创建并持久化清单记录。
    - 测试步骤:
      1. 调用 POST /api/v1/list/add 创建清单。
      2. 检查返回状态和数据。
      3. 验证 lists_database.json 中新增记录。
    - 预期结果:
      1. HTTP 200，业务 code=200。
      2. 返回数据包含清单信息。
      3. lists_database.json 中新增记录。
    - 历史变更:
      - 2026-03-25: 初始创建，覆盖清单创建主链路。
    """
    base_url = integration_runtime["base_url"]
    meta_dir = integration_runtime["meta_dir"]
    lists_path = meta_dir / "lists_database.json"

    list_name = f"Test List {uuid4().hex[:8]}"

    response = requests.post(
        f"{base_url}/api/v1/list/add",
        json={"list_name": list_name, "desc": "Test list description", "content_type": "comic"},
        timeout=5,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 200
    assert payload["data"]["name"] == list_name

    lists_data = load_json(lists_path)
    lists = lists_data.get("lists", [])
    created = next((l for l in lists if l.get("name") == list_name), None)
    assert created is not None


@pytest.mark.integration
def test_list_create_rejects_missing_name(integration_runtime):
    """
    用例描述:
    - 用例目的: 验证清单创建接口校验必要参数。
    - 测试步骤:
      1. 调用 POST /api/v1/list/add 不传 list_name。
      2. 检查返回错误码。
    - 预期结果:
      1. HTTP 200，业务 code=400。
    - 历史变更:
      - 2026-03-25: 初始创建，覆盖清单创建参数校验。
    """
    base_url = integration_runtime["base_url"]

    response = requests.post(
        f"{base_url}/api/v1/list/add",
        json={"desc": "No name list"},
        timeout=5,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 400


@pytest.mark.integration
def test_list_edit_updates_metadata(integration_runtime):
    """
    用例描述:
    - 用例目的: 验证清单编辑接口能正确更新元数据。
    - 测试步骤:
      1. 先创建清单。
      2. 调用 PUT /api/v1/list/edit 更新清单。
      3. 验证文件中数据已更新。
    - 预期结果:
      1. HTTP 200，业务 code=200。
      2. 文件中对应记录已更新。
    - 历史变更:
      - 2026-03-25: 初始创建，覆盖清单编辑主链路。
    """
    base_url = integration_runtime["base_url"]
    meta_dir = integration_runtime["meta_dir"]
    lists_path = meta_dir / "lists_database.json"

    list_name = f"Edit Test List {uuid4().hex[:8]}"

    create_resp = requests.post(
        f"{base_url}/api/v1/list/add",
        json={"list_name": list_name, "content_type": "comic"},
        timeout=5,
    )
    list_id = create_resp.json()["data"]["id"]

    new_name = f"Updated List {uuid4().hex[:8]}"
    new_desc = "Updated description"

    response = requests.put(
        f"{base_url}/api/v1/list/edit",
        json={"list_id": list_id, "list_name": new_name, "desc": new_desc},
        timeout=5,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 200

    lists_data = load_json(lists_path)
    lists = lists_data.get("lists", [])
    updated = find_by_id(lists, list_id)
    assert updated is not None
    assert updated["name"] == new_name
    assert updated["desc"] == new_desc


@pytest.mark.integration
def test_list_delete_removes_record(integration_runtime):
    """
    用例描述:
    - 用例目的: 验证清单删除接口能正确移除记录。
    - 测试步骤:
      1. 先创建清单。
      2. 调用 DELETE /api/v1/list/delete 删除清单。
      3. 验证记录已从文件中移除。
    - 预期结果:
      1. HTTP 200，业务 code=200。
      2. 记录从 lists_database.json 中消失。
    - 历史变更:
      - 2026-03-25: 初始创建，覆盖清单删除主链路。
    """
    base_url = integration_runtime["base_url"]
    meta_dir = integration_runtime["meta_dir"]
    lists_path = meta_dir / "lists_database.json"

    list_name = f"Delete Test List {uuid4().hex[:8]}"

    create_resp = requests.post(
        f"{base_url}/api/v1/list/add",
        json={"list_name": list_name, "content_type": "comic"},
        timeout=5,
    )
    list_id = create_resp.json()["data"]["id"]

    response = requests.delete(
        f"{base_url}/api/v1/list/delete",
        params={"list_id": list_id},
        timeout=5,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 200

    lists_data = load_json(lists_path)
    lists = lists_data.get("lists", [])
    assert find_by_id(lists, list_id) is None


@pytest.mark.integration
def test_list_detail_returns_info(integration_runtime):
    """
    用例描述:
    - 用例目的: 验证清单详情接口返回完整信息。
    - 测试步骤:
      1. 调用 GET /api/v1/list/detail?list_id=list_favorites_comic。
      2. 检查返回数据。
    - 预期结果:
      1. HTTP 200，业务 code=200。
      2. 返回数据包含清单完整信息。
    - 历史变更:
      - 2026-03-25: 初始创建，覆盖清单详情主链路。
    """
    base_url = integration_runtime["base_url"]

    response = requests.get(
        f"{base_url}/api/v1/list/detail",
        params={"list_id": "list_favorites_comic"},
        timeout=5,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 200
    assert payload["data"]["id"] == "list_favorites_comic"
    assert "name" in payload["data"]


@pytest.mark.integration
def test_list_detail_rejects_nonexistent(integration_runtime):
    """
    用例描述:
    - 用例目的: 验证清单详情接口对不存在清单返回正确错误。
    - 测试步骤:
      1. 调用 GET /api/v1/list/detail?list_id=NONEXISTENT。
      2. 检查返回错误码。
    - 预期结果:
      1. HTTP 200，业务 code=404。
    - 历史变更:
      - 2026-03-25: 初始创建，覆盖清单详情不存在分支。
    """
    base_url = integration_runtime["base_url"]

    response = requests.get(
        f"{base_url}/api/v1/list/detail",
        params={"list_id": "NONEXISTENT_LIST_999"},
        timeout=5,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 404


@pytest.mark.integration
def test_list_all_returns_lists(integration_runtime):
    """
    用例描述:
    - 用例目的: 验证获取所有清单接口返回正确数据。
    - 测试步骤:
      1. 调用 GET /api/v1/list/list。
      2. 检查返回数据。
    - 预期结果:
      1. HTTP 200，业务 code=200。
      2. 返回清单列表。
    - 历史变更:
      - 2026-03-25: 初始创建，覆盖清单列表查询主链路。
    """
    base_url = integration_runtime["base_url"]

    response = requests.get(
        f"{base_url}/api/v1/list/list",
        timeout=5,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 200
    assert isinstance(payload["data"], list)
    assert len(payload["data"]) >= 1


@pytest.mark.integration
def test_list_bind_comics_persists(integration_runtime):
    """
    用例描述:
    - 用例目的: 验证漫画绑定到清单接口能正确持久化。
    - 测试步骤:
      1. 创建测试清单。
      2. 调用 PUT /api/v1/list/comic/bind 绑定漫画。
      3. 验证文件中漫画的 list_ids 已更新。
    - 预期结果:
      1. HTTP 200，业务 code=200。
      2. 文件中漫画的 list_ids 包含新清单 ID。
    - 历史变更:
      - 2026-03-25: 初始创建，覆盖漫画绑定清单主链路。
    """
    base_url = integration_runtime["base_url"]
    meta_dir = integration_runtime["meta_dir"]
    comics_path = meta_dir / "comics_database.json"

    list_name = f"Bind Test List {uuid4().hex[:8]}"
    create_resp = requests.post(
        f"{base_url}/api/v1/list/add",
        json={"list_name": list_name, "content_type": "comic"},
        timeout=5,
    )
    list_id = create_resp.json()["data"]["id"]

    from tests.shared.test_constants import PRIMARY_COMIC_ID

    response = requests.put(
        f"{base_url}/api/v1/list/comic/bind",
        json={"list_id": list_id, "comic_id_list": [PRIMARY_COMIC_ID]},
        timeout=5,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 200

    comics_data = load_json(comics_path)
    comics = comics_data.get("comics", [])
    comic = find_by_id(comics, PRIMARY_COMIC_ID)
    assert comic is not None
    assert list_id in comic.get("list_ids", [])


@pytest.mark.integration
def test_list_remove_comics_persists(integration_runtime):
    """
    用例描述:
    - 用例目的: 验证从清单移除漫画接口能正确持久化。
    - 测试步骤:
      1. 创建测试清单并绑定漫画。
      2. 调用 DELETE /api/v1/list/comic/remove 移除漫画。
      3. 验证文件中漫画的 list_ids 已移除清单 ID。
    - 预期结果:
      1. HTTP 200，业务 code=200。
      2. 文件中漫画的 list_ids 不包含该清单 ID。
    - 历史变更:
      - 2026-03-25: 初始创建，覆盖从清单移除漫画主链路。
    """
    base_url = integration_runtime["base_url"]
    meta_dir = integration_runtime["meta_dir"]
    comics_path = meta_dir / "comics_database.json"

    list_name = f"Remove Test List {uuid4().hex[:8]}"
    create_resp = requests.post(
        f"{base_url}/api/v1/list/add",
        json={"list_name": list_name, "content_type": "comic"},
        timeout=5,
    )
    list_id = create_resp.json()["data"]["id"]

    from tests.shared.test_constants import SECONDARY_COMIC_ID

    requests.put(
        f"{base_url}/api/v1/list/comic/bind",
        json={"list_id": list_id, "comic_id_list": [SECONDARY_COMIC_ID]},
        timeout=5,
    )

    response = requests.delete(
        f"{base_url}/api/v1/list/comic/remove",
        params={"list_id": list_id, "comic_id_list": SECONDARY_COMIC_ID},
        timeout=5,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 200

    comics_data = load_json(comics_path)
    comics = comics_data.get("comics", [])
    comic = find_by_id(comics, SECONDARY_COMIC_ID)
    assert comic is not None
    assert list_id not in comic.get("list_ids", [])


@pytest.mark.integration
def test_list_bind_videos_persists(integration_runtime):
    """
    用例描述:
    - 用例目的: 验证视频绑定到清单接口能正确持久化。
    - 测试步骤:
      1. 创建视频清单。
      2. 调用 PUT /api/v1/list/video/bind 绑定视频。
      3. 验证文件中视频的 list_ids 已更新。
    - 预期结果:
      1. HTTP 200，业务 code=200。
      2. 文件中视频的 list_ids 包含新清单 ID。
    - 历史变更:
      - 2026-03-25: 初始创建，覆盖视频绑定清单主链路。
    """
    base_url = integration_runtime["base_url"]
    meta_dir = integration_runtime["meta_dir"]
    videos_path = meta_dir / "videos_database.json"

    list_name = f"Video Bind Test List {uuid4().hex[:8]}"
    create_resp = requests.post(
        f"{base_url}/api/v1/list/add",
        json={"list_name": list_name, "content_type": "video"},
        timeout=5,
    )
    list_id = create_resp.json()["data"]["id"]

    from tests.shared.test_constants import PRIMARY_VIDEO_ID

    response = requests.put(
        f"{base_url}/api/v1/list/video/bind",
        json={"list_id": list_id, "video_id_list": [PRIMARY_VIDEO_ID]},
        timeout=5,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 200

    videos_data = load_json(videos_path)
    videos = videos_data.get("videos", [])
    video = find_by_id(videos, PRIMARY_VIDEO_ID)
    assert video is not None
    assert list_id in video.get("list_ids", [])


@pytest.mark.integration
def test_list_remove_videos_persists(integration_runtime):
    """
    用例描述:
    - 用例目的: 验证从清单移除视频接口能正确持久化。
    - 测试步骤:
      1. 创建视频清单并绑定视频。
      2. 调用 DELETE /api/v1/list/video/remove 移除视频。
      3. 验证文件中视频的 list_ids 已移除清单 ID。
    - 预期结果:
      1. HTTP 200，业务 code=200。
      2. 文件中视频的 list_ids 不包含该清单 ID。
    - 历史变更:
      - 2026-03-25: 初始创建，覆盖从清单移除视频主链路。
    """
    base_url = integration_runtime["base_url"]
    meta_dir = integration_runtime["meta_dir"]
    videos_path = meta_dir / "videos_database.json"

    list_name = f"Video Remove Test List {uuid4().hex[:8]}"
    create_resp = requests.post(
        f"{base_url}/api/v1/list/add",
        json={"list_name": list_name, "content_type": "video"},
        timeout=5,
    )
    list_id = create_resp.json()["data"]["id"]

    from tests.shared.test_constants import SECONDARY_VIDEO_ID

    requests.put(
        f"{base_url}/api/v1/list/video/bind",
        json={"list_id": list_id, "video_id_list": [SECONDARY_VIDEO_ID]},
        timeout=5,
    )

    response = requests.delete(
        f"{base_url}/api/v1/list/video/remove",
        params={"list_id": list_id, "video_id_list": SECONDARY_VIDEO_ID},
        timeout=5,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 200

    videos_data = load_json(videos_path)
    videos = videos_data.get("videos", [])
    video = find_by_id(videos, SECONDARY_VIDEO_ID)
    assert video is not None
    assert list_id not in video.get("list_ids", [])


@pytest.mark.integration
def test_list_favorite_toggle_comic(integration_runtime):
    """
    用例描述:
    - 用例目的: 验证漫画收藏切换接口能正确执行。
    - 测试步骤:
      1. 调用 PUT /api/v1/list/favorite/toggle 切换收藏状态。
      2. 验证返回状态和 is_favorited 字段。
    - 预期结果:
      1. HTTP 200，业务 code=200。
      2. 返回数据包含 is_favorited 字段。
    - 历史变更:
      - 2026-03-25: 初始创建，覆盖漫画收藏切换主链路。
    """
    base_url = integration_runtime["base_url"]

    from tests.shared.test_constants import PRIMARY_COMIC_ID

    response = requests.put(
        f"{base_url}/api/v1/list/favorite/toggle",
        json={"comic_id": PRIMARY_COMIC_ID},
        timeout=5,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 200
    assert "is_favorited" in payload["data"]


@pytest.mark.integration
def test_list_favorite_check_comic(integration_runtime):
    """
    用例描述:
    - 用例目的: 验证漫画收藏状态检查接口能正确返回状态。
    - 测试步骤:
      1. 调用 GET /api/v1/list/favorite/check?comic_id=xxx。
      2. 验证返回状态。
    - 预期结果:
      1. HTTP 200，业务 code=200。
      2. 返回数据包含 is_favorited 字段。
    - 历史变更:
      - 2026-03-25: 初始创建，覆盖漫画收藏状态检查主链路。
    """
    base_url = integration_runtime["base_url"]

    from tests.shared.test_constants import PRIMARY_COMIC_ID

    response = requests.get(
        f"{base_url}/api/v1/list/favorite/check",
        params={"comic_id": PRIMARY_COMIC_ID},
        timeout=5,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 200
    assert "is_favorited" in payload["data"]


@pytest.mark.integration
def test_list_favorite_toggle_video(integration_runtime):
    """
    用例描述:
    - 用例目的: 验证视频收藏切换接口能正确执行。
    - 测试步骤:
      1. 调用 PUT /api/v1/list/video/favorite/toggle 切换收藏状态。
      2. 验证返回状态和 is_favorited 字段。
    - 预期结果:
      1. HTTP 200，业务 code=200。
      2. 返回数据包含 is_favorited 字段。
    - 历史变更:
      - 2026-03-25: 初始创建，覆盖视频收藏切换主链路。
    """
    base_url = integration_runtime["base_url"]

    from tests.shared.test_constants import PRIMARY_VIDEO_ID

    response = requests.put(
        f"{base_url}/api/v1/list/video/favorite/toggle",
        json={"video_id": PRIMARY_VIDEO_ID},
        timeout=5,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 200
    assert "is_favorited" in payload["data"]


@pytest.mark.integration
def test_list_favorite_check_video(integration_runtime):
    """
    用例描述:
    - 用例目的: 验证视频收藏状态检查接口能正确返回状态。
    - 测试步骤:
      1. 调用 GET /api/v1/list/video/favorite/check?video_id=xxx。
      2. 验证返回状态。
    - 预期结果:
      1. HTTP 200，业务 code=200。
      2. 返回数据包含 is_favorited 字段。
    - 历史变更:
      - 2026-03-25: 初始创建，覆盖视频收藏状态检查主链路。
    """
    base_url = integration_runtime["base_url"]

    from tests.shared.test_constants import PRIMARY_VIDEO_ID

    response = requests.get(
        f"{base_url}/api/v1/list/video/favorite/check",
        params={"video_id": PRIMARY_VIDEO_ID},
        timeout=5,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 200
    assert "is_favorited" in payload["data"]
