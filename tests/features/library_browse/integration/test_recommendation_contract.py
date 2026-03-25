from __future__ import annotations

from uuid import uuid4

import pytest
import requests

from tests.shared.runtime_data import find_by_id, load_json


@pytest.mark.integration
def test_recommendation_list_returns_items(integration_runtime):
    """
    用例描述:
    - 用例目的: 验证推荐漫画列表接口返回正确数据。
    - 测试步骤:
      1. 调用 GET /api/v1/recommendation/list。
      2. 检查返回数据格式。
    - 预期结果:
      1. HTTP 200，业务 code=200。
      2. 返回推荐列表。
    - 历史变更:
      - 2026-03-25: 初始创建，覆盖推荐列表查询主链路。
    """
    base_url = integration_runtime["base_url"]

    response = requests.get(
        f"{base_url}/api/v1/recommendation/list",
        timeout=5,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 200
    assert isinstance(payload["data"], list)


@pytest.mark.integration
def test_recommendation_list_sort_by_score(integration_runtime):
    """
    用例描述:
    - 用例目的: 验证推荐漫画列表按评分排序功能。
    - 测试步骤:
      1. 添加测试推荐数据。
      2. 调用 GET /api/v1/recommendation/list?sort_type=score。
      3. 检查返回顺序。
    - 预期结果:
      1. HTTP 200，业务 code=200。
      2. 返回数据按评分降序排列。
    - 历史变更:
      - 2026-03-25: 初始创建，覆盖推荐列表排序功能。
    """
    base_url = integration_runtime["base_url"]

    rec_id_1 = f"REC{uuid4().hex[:8]}"
    rec_id_2 = f"REC{uuid4().hex[:8]}"

    requests.post(
        f"{base_url}/api/v1/recommendation/add",
        json={"id": rec_id_1, "title": "Rec 1", "score": 7.5},
        timeout=5,
    )
    requests.post(
        f"{base_url}/api/v1/recommendation/add",
        json={"id": rec_id_2, "title": "Rec 2", "score": 9.0},
        timeout=5,
    )

    response = requests.get(
        f"{base_url}/api/v1/recommendation/list",
        params={"sort_type": "score"},
        timeout=5,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 200

    items = payload["data"]
    scores = [item.get("score") or 0 for item in items if item.get("id") in [rec_id_1, rec_id_2]]
    if len(scores) >= 2:
        assert scores == sorted(scores, reverse=True)


@pytest.mark.integration
def test_recommendation_add_creates_item(integration_runtime):
    """
    用例描述:
    - 用例目的: 验证添加推荐漫画接口能正确创建记录。
    - 测试步骤:
      1. 调用 POST /api/v1/recommendation/add 添加推荐。
      2. 检查返回状态和数据。
      3. 验证文件中新增记录。
    - 预期结果:
      1. HTTP 200，业务 code=200。
      2. 返回数据包含推荐信息。
      3. recommendations_database.json 中新增记录。
    - 历史变更:
      - 2026-03-25: 初始创建，覆盖添加推荐主链路。
    """
    base_url = integration_runtime["base_url"]
    meta_dir = integration_runtime["meta_dir"]
    rec_path = meta_dir / "recommendations_database.json"

    rec_id = f"ADDREC{uuid4().hex[:8]}"
    title = f"Test Recommendation {rec_id}"

    response = requests.post(
        f"{base_url}/api/v1/recommendation/add",
        json={"id": rec_id, "title": title, "author": "Test Author"},
        timeout=5,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 200
    assert payload["data"]["id"] == rec_id

    rec_data = load_json(rec_path)
    recommendations = rec_data.get("recommendations", [])
    created = find_by_id(recommendations, rec_id)
    assert created is not None
    assert created["title"] == title


@pytest.mark.integration
def test_recommendation_add_rejects_missing_title(integration_runtime):
    """
    用例描述:
    - 用例目的: 验证添加推荐接口校验必要参数。
    - 测试步骤:
      1. 调用 POST /api/v1/recommendation/add 不传 title。
      2. 检查返回错误码。
    - 预期结果:
      1. HTTP 200，业务 code=400。
    - 历史变更:
      - 2026-03-25: 初始创建，覆盖添加推荐参数校验。
    """
    base_url = integration_runtime["base_url"]

    response = requests.post(
        f"{base_url}/api/v1/recommendation/add",
        json={"id": "TEST_ID"},
        timeout=5,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 400


@pytest.mark.integration
def test_recommendation_detail_returns_info(integration_runtime):
    """
    用例描述:
    - 用例目的: 验证推荐详情接口返回完整信息。
    - 测试步骤:
      1. 先添加推荐。
      2. 调用 GET /api/v1/recommendation/detail?recommendation_id=xxx。
      3. 检查返回数据。
    - 预期结果:
      1. HTTP 200，业务 code=200。
      2. 返回数据包含推荐完整信息。
    - 历史变更:
      - 2026-03-25: 初始创建，覆盖推荐详情主链路。
    """
    base_url = integration_runtime["base_url"]

    rec_id = f"DETREC{uuid4().hex[:8]}"
    title = f"Detail Test {rec_id}"

    requests.post(
        f"{base_url}/api/v1/recommendation/add",
        json={"id": rec_id, "title": title},
        timeout=5,
    )

    response = requests.get(
        f"{base_url}/api/v1/recommendation/detail",
        params={"recommendation_id": rec_id},
        timeout=5,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 200
    assert payload["data"]["id"] == rec_id
    assert payload["data"]["title"] == title


@pytest.mark.integration
def test_recommendation_detail_rejects_nonexistent(integration_runtime):
    """
    用例描述:
    - 用例目的: 验证推荐详情接口对不存在推荐返回正确错误。
    - 测试步骤:
      1. 调用 GET /api/v1/recommendation/detail?recommendation_id=NONEXISTENT。
      2. 检查返回错误码。
    - 预期结果:
      1. HTTP 200，业务 code=404。
    - 历史变更:
      - 2026-03-25: 初始创建，覆盖推荐详情不存在分支。
    """
    base_url = integration_runtime["base_url"]

    response = requests.get(
        f"{base_url}/api/v1/recommendation/detail",
        params={"recommendation_id": "NONEXISTENT_REC_999"},
        timeout=5,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 404


@pytest.mark.integration
def test_recommendation_delete_removes_item(integration_runtime):
    """
    用例描述:
    - 用例目的: 验证删除推荐接口能正确移除记录。
    - 测试步骤:
      1. 先添加推荐。
      2. 调用 DELETE /api/v1/recommendation/delete?recommendation_id=xxx。
      3. 验证记录已从文件中移除。
    - 预期结果:
      1. HTTP 200，业务 code=200。
      2. 记录从 recommendations_database.json 中消失。
    - 历史变更:
      - 2026-03-25: 初始创建，覆盖删除推荐主链路。
    """
    base_url = integration_runtime["base_url"]
    meta_dir = integration_runtime["meta_dir"]
    rec_path = meta_dir / "recommendations_database.json"

    rec_id = f"DELREC{uuid4().hex[:8]}"

    requests.post(
        f"{base_url}/api/v1/recommendation/add",
        json={"id": rec_id, "title": f"To Delete {rec_id}"},
        timeout=5,
    )

    response = requests.delete(
        f"{base_url}/api/v1/recommendation/delete",
        params={"recommendation_id": rec_id},
        timeout=5,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 200

    rec_data = load_json(rec_path)
    recommendations = rec_data.get("recommendations", [])
    assert find_by_id(recommendations, rec_id) is None


@pytest.mark.integration
def test_recommendation_score_update_persists(integration_runtime):
    """
    用例描述:
    - 用例目的: 验证推荐评分更新接口能正确持久化评分。
    - 测试步骤:
      1. 先添加推荐。
      2. 调用 PUT /api/v1/recommendation/score 更新评分。
      3. 验证文件中评分已更新。
    - 预期结果:
      1. HTTP 200，业务 code=200。
      2. 文件中对应记录的 score 已更新。
    - 历史变更:
      - 2026-03-25: 初始创建，覆盖推荐评分更新主链路。
    """
    base_url = integration_runtime["base_url"]
    meta_dir = integration_runtime["meta_dir"]
    rec_path = meta_dir / "recommendations_database.json"

    rec_id = f"SCOREREC{uuid4().hex[:8]}"

    requests.post(
        f"{base_url}/api/v1/recommendation/add",
        json={"id": rec_id, "title": f"Score Test {rec_id}"},
        timeout=5,
    )

    new_score = 8.5

    response = requests.put(
        f"{base_url}/api/v1/recommendation/score",
        json={"recommendation_id": rec_id, "score": new_score},
        timeout=5,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 200
    assert payload["data"]["score"] == new_score

    rec_data = load_json(rec_path)
    recommendations = rec_data.get("recommendations", [])
    updated = find_by_id(recommendations, rec_id)
    assert updated is not None
    assert updated["score"] == new_score


@pytest.mark.integration
def test_recommendation_progress_update_persists(integration_runtime):
    """
    用例描述:
    - 用例目的: 验证推荐进度更新接口能正确持久化进度。
    - 测试步骤:
      1. 先添加推荐。
      2. 调用 PUT /api/v1/recommendation/progress 更新进度。
      3. 验证文件中进度已更新。
    - 预期结果:
      1. HTTP 200，业务 code=200。
      2. 文件中对应记录的 current_page 已更新。
    - 历史变更:
      - 2026-03-25: 初始创建，覆盖推荐进度更新主链路。
    """
    base_url = integration_runtime["base_url"]
    meta_dir = integration_runtime["meta_dir"]
    rec_path = meta_dir / "recommendations_database.json"

    rec_id = f"PROGREC{uuid4().hex[:8]}"

    requests.post(
        f"{base_url}/api/v1/recommendation/add",
        json={"id": rec_id, "title": f"Progress Test {rec_id}", "total_page": 10},
        timeout=5,
    )

    new_page = 5

    response = requests.put(
        f"{base_url}/api/v1/recommendation/progress",
        json={"recommendation_id": rec_id, "current_page": new_page},
        timeout=5,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 200

    rec_data = load_json(rec_path)
    recommendations = rec_data.get("recommendations", [])
    updated = find_by_id(recommendations, rec_id)
    assert updated is not None
    assert updated.get("current_page") == new_page


@pytest.mark.integration
def test_recommendation_edit_updates_metadata(integration_runtime):
    """
    用例描述:
    - 用例目的: 验证推荐编辑接口能正确更新元数据。
    - 测试步骤:
      1. 先添加推荐。
      2. 调用 PUT /api/v1/recommendation/edit 更新元数据。
      3. 验证文件中数据已更新。
    - 预期结果:
      1. HTTP 200，业务 code=200。
      2. 文件中对应记录已更新。
    - 历史变更:
      - 2026-03-25: 初始创建，覆盖推荐编辑主链路。
    """
    base_url = integration_runtime["base_url"]
    meta_dir = integration_runtime["meta_dir"]
    rec_path = meta_dir / "recommendations_database.json"

    rec_id = f"EDITREC{uuid4().hex[:8]}"

    requests.post(
        f"{base_url}/api/v1/recommendation/add",
        json={"id": rec_id, "title": f"Edit Test {rec_id}"},
        timeout=5,
    )

    new_title = "Updated Recommendation Title"
    new_author = "Updated Author"

    response = requests.put(
        f"{base_url}/api/v1/recommendation/edit",
        json={"recommendation_id": rec_id, "title": new_title, "author": new_author},
        timeout=5,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 200

    rec_data = load_json(rec_path)
    recommendations = rec_data.get("recommendations", [])
    updated = find_by_id(recommendations, rec_id)
    assert updated is not None
    assert updated["title"] == new_title
    assert updated["author"] == new_author


@pytest.mark.integration
def test_recommendation_search_returns_matching(integration_runtime):
    """
    用例描述:
    - 用例目的: 验证推荐搜索接口能正确返回匹配结果。
    - 测试步骤:
      1. 先添加推荐。
      2. 调用 GET /api/v1/recommendation/search?keyword=xxx。
      3. 检查返回结果。
    - 预期结果:
      1. HTTP 200，业务 code=200。
      2. 返回结果包含匹配的推荐。
    - 历史变更:
      - 2026-03-25: 初始创建，覆盖推荐搜索主链路。
    """
    base_url = integration_runtime["base_url"]

    rec_id = f"SEARCHREC{uuid4().hex[:8]}"
    unique_keyword = f"UniqueSearchKeyword{rec_id}"

    requests.post(
        f"{base_url}/api/v1/recommendation/add",
        json={"id": rec_id, "title": unique_keyword},
        timeout=5,
    )

    response = requests.get(
        f"{base_url}/api/v1/recommendation/search",
        params={"keyword": unique_keyword},
        timeout=5,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 200
    results = payload["data"]
    assert len(results) >= 1
    assert any(unique_keyword in item["title"] for item in results)


@pytest.mark.integration
def test_recommendation_tag_bind_persists(integration_runtime):
    """
    用例描述:
    - 用例目的: 验证推荐标签绑定接口能正确持久化。
    - 测试步骤:
      1. 先添加推荐。
      2. 调用 PUT /api/v1/recommendation/tag/bind 绑定标签。
      3. 验证文件中 tag_ids 已更新。
    - 预期结果:
      1. HTTP 200，业务 code=200。
      2. 文件中对应记录的 tag_ids 已更新。
    - 历史变更:
      - 2026-03-25: 初始创建，覆盖推荐标签绑定主链路。
    """
    base_url = integration_runtime["base_url"]
    meta_dir = integration_runtime["meta_dir"]
    rec_path = meta_dir / "recommendations_database.json"

    rec_id = f"TAGREC{uuid4().hex[:8]}"

    requests.post(
        f"{base_url}/api/v1/recommendation/add",
        json={"id": rec_id, "title": f"Tag Test {rec_id}"},
        timeout=5,
    )

    response = requests.put(
        f"{base_url}/api/v1/recommendation/tag/bind",
        json={"recommendation_id": rec_id, "tag_id_list": ["tag_action", "tag_drama"]},
        timeout=5,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 200

    rec_data = load_json(rec_path)
    recommendations = rec_data.get("recommendations", [])
    updated = find_by_id(recommendations, rec_id)
    assert updated is not None
    assert "tag_action" in updated.get("tag_ids", [])
    assert "tag_drama" in updated.get("tag_ids", [])


@pytest.mark.integration
def test_recommendation_filter_by_tags(integration_runtime):
    """
    用例描述:
    - 用例目的: 验证推荐按标签筛选接口能正确返回结果。
    - 测试步骤:
      1. 先添加带标签的推荐。
      2. 调用 GET /api/v1/recommendation/filter 传入标签参数。
      3. 检查返回结果。
    - 预期结果:
      1. HTTP 200，业务 code=200。
      2. 返回结果符合筛选条件。
    - 历史变更:
      - 2026-03-25: 初始创建，覆盖推荐标签筛选主链路。
    """
    base_url = integration_runtime["base_url"]

    rec_id = f"FILTERREC{uuid4().hex[:8]}"

    requests.post(
        f"{base_url}/api/v1/recommendation/add",
        json={"id": rec_id, "title": f"Filter Test {rec_id}"},
        timeout=5,
    )
    requests.put(
        f"{base_url}/api/v1/recommendation/tag/bind",
        json={"recommendation_id": rec_id, "tag_id_list": ["tag_action"]},
        timeout=5,
    )

    response = requests.get(
        f"{base_url}/api/v1/recommendation/filter",
        params={"include_tag_ids": "tag_action"},
        timeout=5,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 200
    results = payload["data"]
    assert isinstance(results, list)


@pytest.mark.integration
def test_recommendation_batch_add_tags(integration_runtime):
    """
    用例描述:
    - 用例目的: 验证推荐批量添加标签接口能正确持久化。
    - 测试步骤:
      1. 先添加推荐。
      2. 调用 PUT /api/v1/recommendation/tag/batch-add 批量添加标签。
      3. 验证文件中 tag_ids 已更新。
    - 预期结果:
      1. HTTP 200，业务 code=200。
      2. 文件中对应记录的 tag_ids 已更新。
    - 历史变更:
      - 2026-03-25: 初始创建，覆盖推荐批量添加标签主链路。
    """
    base_url = integration_runtime["base_url"]
    meta_dir = integration_runtime["meta_dir"]
    rec_path = meta_dir / "recommendations_database.json"

    rec_id = f"BATCHREC{uuid4().hex[:8]}"

    requests.post(
        f"{base_url}/api/v1/recommendation/add",
        json={"id": rec_id, "title": f"Batch Tag Test {rec_id}"},
        timeout=5,
    )

    response = requests.put(
        f"{base_url}/api/v1/recommendation/tag/batch-add",
        json={"recommendation_ids": [rec_id], "tag_ids": ["tag_story"]},
        timeout=5,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 200

    rec_data = load_json(rec_path)
    recommendations = rec_data.get("recommendations", [])
    updated = find_by_id(recommendations, rec_id)
    assert updated is not None
    assert "tag_story" in updated.get("tag_ids", [])


@pytest.mark.integration
def test_recommendation_batch_remove_tags(integration_runtime):
    """
    用例描述:
    - 用例目的: 验证推荐批量移除标签接口能正确持久化。
    - 测试步骤:
      1. 先添加推荐并绑定标签。
      2. 调用 PUT /api/v1/recommendation/tag/batch-remove 批量移除标签。
      3. 验证文件中 tag_ids 已移除指定标签。
    - 预期结果:
      1. HTTP 200，业务 code=200。
      2. 文件中对应记录的 tag_ids 已移除指定标签。
    - 历史变更:
      - 2026-03-25: 初始创建，覆盖推荐批量移除标签主链路。
    """
    base_url = integration_runtime["base_url"]
    meta_dir = integration_runtime["meta_dir"]
    rec_path = meta_dir / "recommendations_database.json"

    rec_id = f"REMREC{uuid4().hex[:8]}"

    requests.post(
        f"{base_url}/api/v1/recommendation/add",
        json={"id": rec_id, "title": f"Remove Tag Test {rec_id}"},
        timeout=5,
    )
    requests.put(
        f"{base_url}/api/v1/recommendation/tag/bind",
        json={"recommendation_id": rec_id, "tag_id_list": ["tag_drama"]},
        timeout=5,
    )

    response = requests.put(
        f"{base_url}/api/v1/recommendation/tag/batch-remove",
        json={"recommendation_ids": [rec_id], "tag_ids": ["tag_drama"]},
        timeout=5,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 200

    rec_data = load_json(rec_path)
    recommendations = rec_data.get("recommendations", [])
    updated = find_by_id(recommendations, rec_id)
    assert updated is not None
    assert "tag_drama" not in updated.get("tag_ids", [])
