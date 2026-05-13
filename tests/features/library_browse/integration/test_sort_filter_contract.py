from __future__ import annotations

from pathlib import Path

import pytest
import requests

from tests.shared.runtime_data import load_json, save_json


@pytest.mark.integration
def test_comic_list_sort_by_score_matches_seed_file_order(integration_runtime):
    """
    用例描述:
    - 用例目的: 强看护漫画列表 `sort_type=score` 的排序契约，确保后端返回顺序与文件系统种子数据评分降序一致。
    - 测试步骤:
      1. 读取 `comics_database.json`，按 `score` 计算期望降序 ID 列表。
      2. 调用 `GET /api/v1/comic/list?sort_type=score`。
      3. 比较接口返回 ID 顺序与文件计算结果。
    - 预期结果:
      1. HTTP 状态码为 200，业务 `code=200`。
      2. 接口返回前 N 项 ID 顺序与种子文件按评分降序计算结果完全一致。
    - 历史变更:
      - 2026-03-23: 初始创建，覆盖漫画评分排序强看护。
    """
    base_url = integration_runtime["base_url"]
    meta_dir = integration_runtime["meta_dir"]

    comics = load_json(meta_dir / "comics_database.json").get("comics", [])
    active = [item for item in comics if not item.get("is_deleted", False)]
    expected_ids = [
        item["id"]
        for item in sorted(active, key=lambda item: item.get("score") or 0, reverse=True)
    ]

    response = requests.get(
        f"{base_url}/api/v1/comic/list",
        params={"sort_type": "score"},
        timeout=5,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 200

    actual_ids = [item["id"] for item in payload["data"]]
    assert actual_ids == expected_ids


@pytest.mark.integration
def test_comic_list_sort_by_score_honors_ascending_order(integration_runtime):
    """
    用例描述:
    - 用例目的: 强看护漫画列表 `sort_type=score&sort_order=asc` 契约，确保升序排序稳定生效。
    - 测试步骤:
      1. 读取 `comics_database.json` 并按 `score` 计算升序期望 ID 列表。
      2. 调用 `GET /api/v1/comic/list?sort_type=score&sort_order=asc`。
      3. 对比接口返回顺序与期望顺序。
    - 预期结果:
      1. HTTP 状态码 200，业务 `code=200`。
      2. 返回 ID 顺序严格匹配文件计算出的评分升序结果。
    - 历史变更:
      - 2026-05-14: 新增，补充排序方向门禁。
    """
    base_url = integration_runtime["base_url"]
    meta_dir = integration_runtime["meta_dir"]

    comics = load_json(meta_dir / "comics_database.json").get("comics", [])
    active = [item for item in comics if not item.get("is_deleted", False)]
    expected_ids = [
        item["id"]
        for item in sorted(active, key=lambda item: item.get("score") or 0)
    ]

    response = requests.get(
        f"{base_url}/api/v1/comic/list",
        params={"sort_type": "score", "sort_order": "asc"},
        timeout=5,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 200

    actual_ids = [item["id"] for item in payload["data"]]
    assert actual_ids == expected_ids


@pytest.mark.integration
def test_comic_list_min_max_score_filters_match_seed_file(integration_runtime):
    """
    用例描述:
    - 用例目的: 强看护漫画列表评分区间过滤，确保后端按 `min_score/max_score` 与文件数据一致过滤。
    - 测试步骤:
      1. 读取 `comics_database.json` 并在测试侧计算分数区间期望集合。
      2. 调用 `GET /api/v1/comic/list?min_score=6.5&max_score=9.0`。
      3. 对比接口返回集合与测试侧计算结果。
    - 预期结果:
      1. HTTP 状态码 200，业务 `code=200`。
      2. 返回集合与种子文件计算结果完全一致，且每项评分都落在区间内。
    - 历史变更:
      - 2026-03-23: 初始创建，覆盖漫画评分区间过滤强看护。
    """
    base_url = integration_runtime["base_url"]
    meta_dir = integration_runtime["meta_dir"]

    min_score = 6.5
    max_score = 9.0

    comics = load_json(meta_dir / "comics_database.json").get("comics", [])
    active = [item for item in comics if not item.get("is_deleted", False)]
    expected_ids = {
        item["id"]
        for item in active
        if item.get("score") is not None and min_score <= float(item["score"]) <= max_score
    }

    response = requests.get(
        f"{base_url}/api/v1/comic/list",
        params={"min_score": min_score, "max_score": max_score},
        timeout=5,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 200

    results = payload["data"]
    actual_ids = {item["id"] for item in results}
    assert actual_ids == expected_ids
    assert all(min_score <= float(item["score"]) <= max_score for item in results)


@pytest.mark.integration
def test_comic_filter_multi_include_exclude_author_list(integration_runtime):
    """
    用例描述:
    - 用例目的: 强看护漫画多条件筛选契约，验证“包含标签 + 排除标签 + 作者 + 清单”组合筛选结果正确。
    - 测试步骤:
      1. 读取 `comics_database.json` 并计算组合条件的期望 ID 集合。
      2. 调用 `GET /api/v1/comic/filter` 传入 include/exclude/authors/list_ids。
      3. 对比接口返回集合与期望集合。
    - 预期结果:
      1. HTTP 状态码 200，业务 `code=200`。
      2. 返回集合与组合条件期望集合完全一致。
    - 历史变更:
      - 2026-03-23: 初始创建，覆盖漫画组合筛选强看护。
    """
    base_url = integration_runtime["base_url"]
    meta_dir = integration_runtime["meta_dir"]

    include_tag = "tag_action"
    exclude_tag = "tag_story"
    author = "Tester C"
    list_id = "list_curated_comic"

    comics = load_json(meta_dir / "comics_database.json").get("comics", [])
    active = [item for item in comics if not item.get("is_deleted", False)]
    expected_ids = {
        item["id"]
        for item in active
        if include_tag in (item.get("tag_ids") or [])
        and exclude_tag not in (item.get("tag_ids") or [])
        and item.get("author") == author
        and list_id in (item.get("list_ids") or [])
    }

    response = requests.get(
        f"{base_url}/api/v1/comic/filter",
        params=[
            ("include_tag_ids", include_tag),
            ("exclude_tag_ids", exclude_tag),
            ("authors", author),
            ("list_ids", list_id),
        ],
        timeout=5,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 200

    results = payload["data"]
    actual_ids = {item["id"] for item in results}
    assert actual_ids == expected_ids


@pytest.mark.integration
def test_video_list_sort_by_score_matches_seed_file_order(integration_runtime):
    """
    用例描述:
    - 用例目的: 强看护视频列表 `sort_type=score` 排序契约，确保返回顺序与视频种子文件评分降序一致。
    - 测试步骤:
      1. 读取 `videos_database.json` 并计算评分降序期望 ID 列表。
      2. 调用 `GET /api/v1/video/list?sort_type=score`。
      3. 对比接口返回顺序与期望顺序。
    - 预期结果:
      1. HTTP 状态码 200，业务 `code=200`。
      2. 返回 ID 顺序严格匹配文件计算结果。
    - 历史变更:
      - 2026-03-23: 初始创建，覆盖视频评分排序强看护。
    """
    base_url = integration_runtime["base_url"]
    meta_dir = integration_runtime["meta_dir"]

    videos = load_json(meta_dir / "videos_database.json").get("videos", [])
    active = [item for item in videos if not item.get("is_deleted", False)]
    expected_ids = [
        item["id"]
        for item in sorted(active, key=lambda item: item.get("score") or 0, reverse=True)
    ]

    response = requests.get(
        f"{base_url}/api/v1/video/list",
        params={"sort_type": "score"},
        timeout=5,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 200

    actual_ids = [item["id"] for item in payload["data"]]
    assert actual_ids == expected_ids
    assert {item.get("plugin_id") for item in payload["data"]} == {"video.javdb"}
    assert all(
        ((((item.get("display") or {}).get("cover") or {}).get("aspect_ratio")) == "16 / 9")
        for item in payload["data"]
    )


@pytest.mark.integration
def test_video_list_sort_by_score_honors_ascending_order(integration_runtime):
    """
    用例描述:
    - 用例目的: 强看护视频列表 `sort_type=score&sort_order=asc` 契约，确保升序排序稳定生效。
    - 测试步骤:
      1. 读取 `videos_database.json` 并按 `score` 计算升序期望 ID 列表。
      2. 调用 `GET /api/v1/video/list?sort_type=score&sort_order=asc`。
      3. 对比接口返回顺序与期望顺序。
    - 预期结果:
      1. HTTP 状态码 200，业务 `code=200`。
      2. 返回 ID 顺序严格匹配文件计算出的评分升序结果。
    - 历史变更:
      - 2026-05-14: 新增，补充排序方向门禁。
    """
    base_url = integration_runtime["base_url"]
    meta_dir = integration_runtime["meta_dir"]

    videos = load_json(meta_dir / "videos_database.json").get("videos", [])
    active = [item for item in videos if not item.get("is_deleted", False)]
    expected_ids = [
        item["id"]
        for item in sorted(active, key=lambda item: item.get("score") or 0)
    ]

    response = requests.get(
        f"{base_url}/api/v1/video/list",
        params={"sort_type": "score", "sort_order": "asc"},
        timeout=5,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 200

    actual_ids = [item["id"] for item in payload["data"]]
    assert actual_ids == expected_ids


@pytest.mark.integration
def test_video_list_sort_by_publish_date_honors_asc_and_desc(integration_runtime):
    """
    用例描述:
    - 用例目的: 强看护视频列表 `sort_type=date` 语义，确保“最新发布/最早发布”基于发布日期而非导入顺序。
    - 测试步骤:
      1. 重写 `videos_database.json` 中三个视频的 `date/create_time` 为不同值。
      2. 分别调用 `GET /api/v1/video/list?sort_type=date&sort_order=asc|desc`。
      3. 对比接口返回顺序与测试构造的发布日期顺序。
    - 预期结果:
      1. 升序返回最早发布日期在前，降序返回最新发布日期在前。
      2. 排序依据与 `create_time` 无关，仅由 `date` 决定。
    - 历史变更:
      - 2026-05-14: 新增，明确“最新发布”语义和排序方向。
    """
    base_url = integration_runtime["base_url"]
    meta_dir: Path = integration_runtime["meta_dir"]
    videos_path = meta_dir / "videos_database.json"

    original = load_json(videos_path)
    mutated = load_json(videos_path)
    videos = mutated.get("videos") or []
    assert len(videos) >= 3

    videos[0]["date"] = "2024-06-20"
    videos[0]["create_time"] = "2026-05-10T12:00:00"
    videos[1]["date"] = "2023-01-05"
    videos[1]["create_time"] = "2026-05-12T12:00:00"
    videos[2]["date"] = "2025-03-11"
    videos[2]["create_time"] = "2026-05-11T12:00:00"

    try:
        save_json(videos_path, mutated)

        asc_resp = requests.get(
            f"{base_url}/api/v1/video/list",
            params={"sort_type": "date", "sort_order": "asc"},
            timeout=5,
        )
        assert asc_resp.status_code == 200
        asc_payload = asc_resp.json()
        assert asc_payload["code"] == 200
        assert [item["id"] for item in asc_payload["data"]] == [
            videos[1]["id"],
            videos[0]["id"] if videos[0]["date"] < videos[2]["date"] else videos[2]["id"],
            videos[2]["id"] if videos[0]["date"] < videos[2]["date"] else videos[0]["id"],
        ]

        desc_resp = requests.get(
            f"{base_url}/api/v1/video/list",
            params={"sort_type": "date", "sort_order": "desc"},
            timeout=5,
        )
        assert desc_resp.status_code == 200
        desc_payload = desc_resp.json()
        assert desc_payload["code"] == 200
        assert [item["id"] for item in desc_payload["data"]] == [
            videos[2]["id"] if videos[2]["date"] > videos[0]["date"] else videos[0]["id"],
            videos[0]["id"] if videos[2]["date"] > videos[0]["date"] else videos[2]["id"],
            videos[1]["id"],
        ]
    finally:
        save_json(videos_path, original)


@pytest.mark.integration
def test_video_list_min_max_score_filters_match_seed_file(integration_runtime):
    """
    用例描述:
    - 用例目的: 强看护视频列表评分区间过滤，确保 `min_score/max_score` 契约按种子数据正确生效。
    - 测试步骤:
      1. 读取 `videos_database.json` 并计算分数区间期望集合。
      2. 调用 `GET /api/v1/video/list?min_score=7.5&max_score=9.5`。
      3. 对比接口返回集合与期望集合。
    - 预期结果:
      1. HTTP 状态码 200，业务 `code=200`。
      2. 返回集合与测试侧计算一致且评分均在区间内。
    - 历史变更:
      - 2026-03-23: 初始创建，覆盖视频评分区间过滤强看护。
    """
    base_url = integration_runtime["base_url"]
    meta_dir = integration_runtime["meta_dir"]

    min_score = 7.5
    max_score = 9.5

    videos = load_json(meta_dir / "videos_database.json").get("videos", [])
    active = [item for item in videos if not item.get("is_deleted", False)]
    expected_ids = {
        item["id"]
        for item in active
        if item.get("score") is not None and min_score <= float(item["score"]) <= max_score
    }

    response = requests.get(
        f"{base_url}/api/v1/video/list",
        params={"min_score": min_score, "max_score": max_score},
        timeout=5,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 200

    results = payload["data"]
    actual_ids = {item["id"] for item in results}
    assert actual_ids == expected_ids
    assert all(min_score <= float(item["score"]) <= max_score for item in results)


@pytest.mark.integration
def test_video_filter_multi_include_exclude_author_list(integration_runtime):
    """
    用例描述:
    - 用例目的: 强看护视频多条件筛选契约，验证“包含标签 + 排除标签 + 作者 + 清单”组合筛选结果。
    - 测试步骤:
      1. 读取 `videos_database.json` 并计算组合条件期望集合。
      2. 调用 `GET /api/v1/video/filter` 传入 include/exclude/authors/list_ids。
      3. 对比接口返回集合与期望集合。
    - 预期结果:
      1. HTTP 状态码 200，业务 `code=200`。
      2. 返回集合与组合条件计算结果一致。
    - 历史变更:
      - 2026-03-23: 初始创建，覆盖视频组合筛选强看护。
    """
    base_url = integration_runtime["base_url"]
    meta_dir = integration_runtime["meta_dir"]

    include_tag = "tag_video"
    exclude_tag = "tag_video_story"
    author = "Video Creator B"
    list_id = "list_curated_video"

    videos = load_json(meta_dir / "videos_database.json").get("videos", [])
    active = [item for item in videos if not item.get("is_deleted", False)]
    expected_ids = {
        item["id"]
        for item in active
        if include_tag in (item.get("tag_ids") or [])
        and exclude_tag not in (item.get("tag_ids") or [])
        and item.get("creator") == author
        and list_id in (item.get("list_ids") or [])
    }

    response = requests.get(
        f"{base_url}/api/v1/video/filter",
        params=[
            ("include_tag_ids", include_tag),
            ("exclude_tag_ids", exclude_tag),
            ("authors", author),
            ("list_ids", list_id),
        ],
        timeout=5,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 200

    results = payload["data"]
    actual_ids = {item["id"] for item in results}
    assert actual_ids == expected_ids


@pytest.mark.integration
def test_recommendation_list_sort_by_score_honors_ascending_order(integration_runtime):
    """
    用例描述:
    - 用例目的: 强看护推荐漫画列表 `sort_type=score&sort_order=asc` 契约。
    - 测试步骤:
      1. 构造三个不同分数的推荐漫画记录。
      2. 调用 `GET /api/v1/recommendation/list?sort_type=score&sort_order=asc`。
      3. 对比接口返回顺序与测试构造的评分升序顺序。
    - 预期结果:
      1. HTTP 状态码 200，业务 `code=200`。
      2. 返回 ID 顺序严格匹配评分升序结果。
    - 历史变更:
      - 2026-05-14: 新增，覆盖预览库排序方向门禁。
    """
    base_url = integration_runtime["base_url"]
    meta_dir: Path = integration_runtime["meta_dir"]
    rec_path = meta_dir / "recommendations_database.json"

    original = load_json(rec_path)
    payload = {
        "collection_name": "Test Comic Recommendations",
        "user": "test-user",
        "total_recommendations": 3,
        "last_updated": "2026-05-14",
        "recommendations": [
            {"id": "JMREC001", "title": "推荐漫画 A", "score": 9.2, "create_time": "2026-05-01T10:00:00", "is_deleted": False},
            {"id": "JMREC002", "title": "推荐漫画 B", "score": 4.8, "create_time": "2026-05-02T10:00:00", "is_deleted": False},
            {"id": "JMREC003", "title": "推荐漫画 C", "score": 7.1, "create_time": "2026-05-03T10:00:00", "is_deleted": False},
        ],
    }

    try:
        save_json(rec_path, payload)

        response = requests.get(
            f"{base_url}/api/v1/recommendation/list",
            params={"sort_type": "score", "sort_order": "asc"},
            timeout=5,
        )

        assert response.status_code == 200
        body = response.json()
        assert body["code"] == 200
        assert [item["id"] for item in body["data"]] == ["JMREC002", "JMREC003", "JMREC001"]
    finally:
        save_json(rec_path, original)


@pytest.mark.integration
def test_video_recommendation_list_sort_by_publish_date_honors_ascending_order(integration_runtime):
    """
    用例描述:
    - 用例目的: 强看护推荐视频列表 `sort_type=date&sort_order=asc` 契约。
    - 测试步骤:
      1. 构造三个不同发布日期的推荐视频记录。
      2. 调用 `GET /api/v1/video/recommendation/list?sort_type=date&sort_order=asc`。
      3. 对比接口返回顺序与测试构造的发布日期升序顺序。
    - 预期结果:
      1. HTTP 状态码 200，业务 `code=200`。
      2. 返回 ID 顺序严格匹配发布日期升序结果。
    - 历史变更:
      - 2026-05-14: 新增，覆盖推荐视频“最早发布”排序门禁。
    """
    base_url = integration_runtime["base_url"]
    meta_dir: Path = integration_runtime["meta_dir"]
    rec_path = meta_dir / "video_recommendations_database.json"

    original = load_json(rec_path)
    payload = {
        "collection_name": "Test Video Recommendations",
        "user": "test-user",
        "total_video_recommendations": 3,
        "last_updated": "2026-05-14",
        "video_recommendations": [
            {"id": "JAVDBREC001", "title": "推荐视频 A", "code": "REC-001", "date": "2024-09-01", "create_time": "2026-05-03T10:00:00", "score": 7.2, "tag_ids": [], "list_ids": [], "is_deleted": False},
            {"id": "JAVDBREC002", "title": "推荐视频 B", "code": "REC-002", "date": "2022-02-14", "create_time": "2026-05-01T10:00:00", "score": 8.5, "tag_ids": [], "list_ids": [], "is_deleted": False},
            {"id": "JAVDBREC003", "title": "推荐视频 C", "code": "REC-003", "date": "2023-07-20", "create_time": "2026-05-02T10:00:00", "score": 6.8, "tag_ids": [], "list_ids": [], "is_deleted": False},
        ],
    }

    try:
        save_json(rec_path, payload)

        response = requests.get(
            f"{base_url}/api/v1/video/recommendation/list",
            params={"sort_type": "date", "sort_order": "asc"},
            timeout=5,
        )

        assert response.status_code == 200
        body = response.json()
        assert body["code"] == 200
        assert [item["id"] for item in body["data"]] == ["JAVDBREC002", "JAVDBREC003", "JAVDBREC001"]
    finally:
        save_json(rec_path, original)
