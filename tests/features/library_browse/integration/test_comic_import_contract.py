from __future__ import annotations

from uuid import uuid4

import pytest
import requests

from tests.shared.runtime_data import find_by_id, load_json


@pytest.mark.integration
def test_comic_init_rejects_missing_comic_dir(integration_runtime):
    """
    用例描述:
    - 用例目的: 验证漫画初始化接口校验漫画目录是否存在。
    - 测试步骤:
      1. 使用不存在的 comic_id 调用 POST /api/v1/comic/init。
      2. 检查接口返回错误码。
    - 预期结果:
      1. HTTP 200，业务 code=404。
      2. 错误信息提示漫画目录不存在。
    - 历史变更:
      - 2026-03-25: 初始创建，覆盖漫画目录不存在防御。
    """
    base_url = integration_runtime["base_url"]

    comic_suffix = uuid4().hex[:8].upper()
    comic_id = f"NONEXISTENT{comic_suffix}"
    title = f"Test Comic {comic_suffix}"

    response = requests.post(
        f"{base_url}/api/v1/comic/init",
        json={"comic_id": comic_id, "title": title},
        timeout=5,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 404


@pytest.mark.integration
def test_comic_init_rejects_duplicate_comic_id(integration_runtime):
    """
    用例描述:
    - 用例目的: 验证漫画初始化接口拒绝重复的 comic_id。
    - 测试步骤:
      1. 使用已存在的 comic_id 调用 POST /api/v1/comic/init。
      2. 检查接口返回错误码。
    - 预期结果:
      1. HTTP 200，业务 code=400。
      2. 错误信息提示漫画已存在。
    - 历史变更:
      - 2026-03-25: 初始创建，覆盖漫画重复创建防御。
    """
    base_url = integration_runtime["base_url"]

    from tests.shared.test_constants import PRIMARY_COMIC_ID

    response = requests.post(
        f"{base_url}/api/v1/comic/init",
        json={"comic_id": PRIMARY_COMIC_ID, "title": "Duplicate Comic"},
        timeout=5,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 400
    assert "已存在" in payload["msg"]


@pytest.mark.integration
def test_comic_init_rejects_missing_comic_id(integration_runtime):
    """
    用例描述:
    - 用例目的: 验证漫画初始化接口校验必要参数。
    - 测试步骤:
      1. 调用 POST /api/v1/comic/init 不传 comic_id。
      2. 检查接口返回错误码。
    - 预期结果:
      1. HTTP 200，业务 code=400。
      2. 错误信息提示缺少参数。
    - 历史变更:
      - 2026-03-25: 初始创建，覆盖参数校验。
    """
    base_url = integration_runtime["base_url"]

    response = requests.post(
        f"{base_url}/api/v1/comic/init",
        json={"title": "No ID Comic"},
        timeout=5,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 400


@pytest.mark.integration
def test_comic_edit_updates_metadata_and_persists(integration_runtime):
    """
    用例描述:
    - 用例目的: 验证漫画编辑接口能正确更新元数据并持久化。
    - 测试步骤:
      1. 调用 PUT /api/v1/comic/edit 更新漫画标题和作者。
      2. 检查接口返回状态。
      3. 验证文件中数据已更新。
    - 预期结果:
      1. HTTP 200，业务 code=200。
      2. 返回数据包含更新后的字段。
      3. 文件中对应记录已更新。
    - 历史变更:
      - 2026-03-25: 初始创建，覆盖漫画编辑主链路。
    """
    base_url = integration_runtime["base_url"]
    meta_dir = integration_runtime["meta_dir"]
    comics_path = meta_dir / "comics_database.json"

    from tests.shared.test_constants import PRIMARY_COMIC_ID

    new_title = "Updated Comic Title"
    new_author = "Updated Author"

    response = requests.put(
        f"{base_url}/api/v1/comic/edit",
        json={"comic_id": PRIMARY_COMIC_ID, "title": new_title, "author": new_author},
        timeout=5,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 200
    assert payload["data"]["title"] == new_title
    assert payload["data"]["author"] == new_author

    comics_data = load_json(comics_path)
    comics = comics_data.get("comics", [])
    updated = find_by_id(comics, PRIMARY_COMIC_ID)
    assert updated is not None
    assert updated["title"] == new_title
    assert updated["author"] == new_author


@pytest.mark.integration
def test_comic_edit_rejects_nonexistent_comic(integration_runtime):
    """
    用例描述:
    - 用例目的: 验证漫画编辑接口拒绝不存在的 comic_id。
    - 测试步骤:
      1. 使用不存在的 comic_id 调用 PUT /api/v1/comic/edit。
      2. 检查接口返回错误码。
    - 预期结果:
      1. HTTP 200，业务 code=400。
      2. 错误信息提示漫画不存在。
    - 历史变更:
      - 2026-03-25: 初始创建，覆盖编辑不存在漫画防御。
    """
    base_url = integration_runtime["base_url"]

    response = requests.put(
        f"{base_url}/api/v1/comic/edit",
        json={"comic_id": "NONEXISTENT_COMIC_999", "title": "New Title"},
        timeout=5,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 400


@pytest.mark.integration
def test_comic_search_returns_matching_results(integration_runtime):
    """
    用例描述:
    - 用例目的: 验证漫画搜索接口能正确返回匹配结果。
    - 测试步骤:
      1. 调用 GET /api/v1/comic/search?keyword=E2E。
      2. 检查返回结果包含匹配的漫画。
    - 预期结果:
      1. HTTP 200，业务 code=200。
      2. 返回结果包含标题含有关键词的漫画。
    - 历史变更:
      - 2026-03-25: 初始创建，覆盖漫画搜索主链路。
    """
    base_url = integration_runtime["base_url"]

    response = requests.get(
        f"{base_url}/api/v1/comic/search",
        params={"keyword": "E2E"},
        timeout=5,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 200
    results = payload["data"]
    assert len(results) >= 1
    assert any("E2E" in item["title"] for item in results)


@pytest.mark.integration
def test_comic_search_returns_empty_for_no_match(integration_runtime):
    """
    用例描述:
    - 用例目的: 验证漫画搜索接口在无匹配时返回空列表。
    - 测试步骤:
      1. 调用 GET /api/v1/comic/search?keyword=ZZZZNONEXIST。
      2. 检查返回结果为空。
    - 预期结果:
      1. HTTP 200，业务 code=200。
      2. 返回空列表。
    - 历史变更:
      - 2026-03-25: 初始创建，覆盖搜索无结果分支。
    """
    base_url = integration_runtime["base_url"]

    response = requests.get(
        f"{base_url}/api/v1/comic/search",
        params={"keyword": "ZZZZNONEXIST12345"},
        timeout=5,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 200
    assert payload["data"] == []


@pytest.mark.integration
def test_comic_search_rejects_missing_keyword(integration_runtime):
    """
    用例描述:
    - 用例目的: 验证漫画搜索接口校验必要参数。
    - 测试步骤:
      1. 调用 GET /api/v1/comic/search 不传 keyword。
      2. 检查接口返回错误码。
    - 预期结果:
      1. HTTP 200，业务 code=400。
    - 历史变更:
      - 2026-03-25: 初始创建，覆盖搜索参数校验。
    """
    base_url = integration_runtime["base_url"]

    response = requests.get(
        f"{base_url}/api/v1/comic/search",
        timeout=5,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 400


@pytest.mark.integration
def test_comic_detail_returns_full_info(integration_runtime):
    """
    用例描述:
    - 用例目的: 验证漫画详情接口返回完整的漫画信息。
    - 测试步骤:
      1. 调用 GET /api/v1/comic/detail?comic_id=JM100001。
      2. 检查返回数据完整性。
    - 预期结果:
      1. HTTP 200，业务 code=200。
      2. 返回数据包含 id、title、author、score、tags 等字段。
    - 历史变更:
      - 2026-03-25: 初始创建，覆盖漫画详情主链路。
    """
    base_url = integration_runtime["base_url"]

    from tests.shared.test_constants import PRIMARY_COMIC_ID

    response = requests.get(
        f"{base_url}/api/v1/comic/detail",
        params={"comic_id": PRIMARY_COMIC_ID},
        timeout=5,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 200
    data = payload["data"]
    assert data["id"] == PRIMARY_COMIC_ID
    assert "title" in data
    assert "author" in data
    assert "score" in data
    assert "tags" in data or "tag_ids" in data


@pytest.mark.integration
def test_comic_detail_rejects_nonexistent_comic(integration_runtime):
    """
    用例描述:
    - 用例目的: 验证漫画详情接口对不存在漫画返回正确错误。
    - 测试步骤:
      1. 调用 GET /api/v1/comic/detail?comic_id=NONEXISTENT。
      2. 检查返回错误码。
    - 预期结果:
      1. HTTP 200，业务 code=404。
    - 历史变更:
      - 2026-03-25: 初始创建，覆盖详情不存在分支。
    """
    base_url = integration_runtime["base_url"]

    response = requests.get(
        f"{base_url}/api/v1/comic/detail",
        params={"comic_id": "NONEXISTENT_COMIC_999"},
        timeout=5,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 404


@pytest.mark.integration
def test_comic_score_update_persists(integration_runtime):
    """
    用例描述:
    - 用例目的: 验证漫画评分更新接口能正确持久化评分。
    - 测试步骤:
      1. 调用 PUT /api/v1/comic/score 更新评分。
      2. 验证接口返回和文件持久化。
    - 预期结果:
      1. HTTP 200，业务 code=200。
      2. 文件中对应记录的 score 已更新。
    - 历史变更:
      - 2026-03-25: 初始创建，覆盖评分更新主链路。
    """
    base_url = integration_runtime["base_url"]
    meta_dir = integration_runtime["meta_dir"]
    comics_path = meta_dir / "comics_database.json"

    from tests.shared.test_constants import PRIMARY_COMIC_ID

    new_score = 9.5

    response = requests.put(
        f"{base_url}/api/v1/comic/score",
        json={"comic_id": PRIMARY_COMIC_ID, "score": new_score},
        timeout=5,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 200
    assert payload["data"]["score"] == new_score

    comics_data = load_json(comics_path)
    comics = comics_data.get("comics", [])
    updated = find_by_id(comics, PRIMARY_COMIC_ID)
    assert updated is not None
    assert updated["score"] == new_score


@pytest.mark.integration
def test_comic_score_rejects_missing_params(integration_runtime):
    """
    用例描述:
    - 用例目的: 验证漫画评分更新接口校验必要参数。
    - 测试步骤:
      1. 调用 PUT /api/v1/comic/score 不传 score。
      2. 检查返回错误码。
    - 预期结果:
      1. HTTP 200，业务 code=400。
    - 历史变更:
      - 2026-03-25: 初始创建，覆盖评分参数校验。
    """
    base_url = integration_runtime["base_url"]

    from tests.shared.test_constants import PRIMARY_COMIC_ID

    response = requests.put(
        f"{base_url}/api/v1/comic/score",
        json={"comic_id": PRIMARY_COMIC_ID},
        timeout=5,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 400
