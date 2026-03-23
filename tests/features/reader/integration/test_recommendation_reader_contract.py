from __future__ import annotations

import base64
from datetime import datetime
from pathlib import Path

import pytest
import requests

from tests.shared.runtime_data import find_by_id, load_json, save_json


PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/w8AAgMBgN6QHdwAAAAASUVORK5CYII="
)


def _now_iso() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _upsert_recommendation(meta_dir: Path, recommendation_id: str, *, total_page: int, current_page: int = 1) -> None:
    recommendation_path = meta_dir / "recommendations_database.json"
    payload = load_json(recommendation_path)
    recommendations = payload.get("recommendations", [])

    row = find_by_id(recommendations, recommendation_id)
    if row is None:
        recommendations.append(
            {
                "id": recommendation_id,
                "title": f"Reader Contract {recommendation_id}",
                "title_jp": "",
                "author": "Reader Contract",
                "desc": "Seeded recommendation for reader contract tests.",
                "cover_path": "/static/cover/JM/100001.png",
                "total_page": total_page,
                "current_page": current_page,
                "score": 8.0,
                "tag_ids": [],
                "list_ids": [],
                "create_time": _now_iso(),
                "last_read_time": _now_iso(),
                "is_deleted": False,
                "preview_image_urls": [],
                "preview_pages": [],
            }
        )
    else:
        row.update(
            {
                "total_page": total_page,
                "current_page": current_page,
                "is_deleted": False,
            }
        )

    payload["recommendations"] = recommendations
    payload["total_recommendations"] = len(recommendations)
    payload["last_updated"] = _today()
    save_json(recommendation_path, payload)


def _seed_recommendation_cache(data_dir: Path, recommendation_id: str, page_count: int) -> None:
    original_id = recommendation_id.replace("JM", "", 1)
    cache_dir = data_dir / "recommendation_cache" / "comic" / "JM" / original_id
    cache_dir.mkdir(parents=True, exist_ok=True)

    for page in range(1, page_count + 1):
        target = cache_dir / f"{page:03d}.png"
        target.write_bytes(PNG_1X1)


@pytest.mark.integration
def test_recommendation_reader_cache_status_and_image_contract(integration_runtime):
    """
    用例描述:
    - 用例目的: 看护预览阅读页依赖的缓存查询/取图契约，确保命中缓存时可直接按页读取图片。
    - 测试步骤:
      1. 在 recommendations_database.json 中写入一个 JM 推荐条目。
      2. 在 recommendation_cache/comic/JM/<original_id> 写入多页真实图片文件。
      3. 调用 cache/status、cache/image、recommendation/detail 接口。
      4. 校验缓存状态、图片可读性与 detail 中 is_cached/预览图片 URL 结构。
    - 预期结果:
      1. cache/status 返回 is_cached=true 且 cached_pages 与落盘页数一致。
      2. cache/image 指定页返回 image/* 内容。
      3. detail 返回 is_cached=true 且 preview_image_urls 指向 cache/image 接口。
    - 历史变更:
      - 2026-03-24: 初始创建，覆盖预览阅读缓存命中主链路契约。
    """
    base_url = integration_runtime["base_url"]
    meta_dir: Path = integration_runtime["meta_dir"]
    data_dir: Path = integration_runtime["data_dir"]
    recommendation_id = "JM920101"

    _upsert_recommendation(meta_dir, recommendation_id, total_page=3, current_page=1)
    _seed_recommendation_cache(data_dir, recommendation_id, page_count=3)

    status_response = requests.get(
        f"{base_url}/api/v1/recommendation/cache/status",
        params={"recommendation_id": recommendation_id},
        timeout=5,
    )
    assert status_response.status_code == 200
    status_payload = status_response.json()
    assert status_payload["code"] == 200
    assert status_payload["data"]["is_cached"] is True
    assert status_payload["data"]["cached_pages"] == [1, 2, 3]
    assert status_payload["data"]["cached_count"] == 3

    image_response = requests.get(
        f"{base_url}/api/v1/recommendation/cache/image",
        params={"recommendation_id": recommendation_id, "page_num": 2},
        timeout=5,
    )
    assert image_response.status_code == 200
    assert image_response.headers.get("Content-Type", "").startswith("image/")
    assert len(image_response.content) > 0

    detail_response = requests.get(
        f"{base_url}/api/v1/recommendation/detail",
        params={"recommendation_id": recommendation_id},
        timeout=5,
    )
    assert detail_response.status_code == 200
    detail_payload = detail_response.json()
    assert detail_payload["code"] == 200
    assert detail_payload["data"]["id"] == recommendation_id
    assert detail_payload["data"]["is_cached"] is True

    preview_urls = detail_payload["data"].get("preview_image_urls", [])
    assert preview_urls, "preview_image_urls should not be empty when recommendation is cached"
    assert all(
        f"/api/v1/recommendation/cache/image?recommendation_id={recommendation_id}&page_num="
        in url
        for url in preview_urls
    )


@pytest.mark.integration
def test_recommendation_reader_progress_persistence_and_validation(integration_runtime):
    """
    用例描述:
    - 用例目的: 看护预览阅读页进度保存契约，确保合法页码落盘、非法页码被拒绝且不污染数据。
    - 测试步骤:
      1. 构造 total_page=4 的推荐漫画条目。
      2. 调用 PUT /api/v1/recommendation/progress 保存 current_page=3。
      3. 校验接口返回与 recommendations_database.json 落盘结果一致。
      4. 再调用非法页码 current_page=9，校验业务错误码与文件不变。
    - 预期结果:
      1. 合法写入返回 code=200，文件 current_page 更新为 3。
      2. 非法写入返回业务 code=400，文件 current_page 仍保持 3。
    - 历史变更:
      - 2026-03-24: 初始创建，补齐预览阅读进度保存与边界校验门禁。
    """
    base_url = integration_runtime["base_url"]
    meta_dir: Path = integration_runtime["meta_dir"]
    recommendation_id = "JM920102"

    _upsert_recommendation(meta_dir, recommendation_id, total_page=4, current_page=1)

    valid_response = requests.put(
        f"{base_url}/api/v1/recommendation/progress",
        json={"recommendation_id": recommendation_id, "current_page": 3},
        timeout=5,
    )
    assert valid_response.status_code == 200
    valid_payload = valid_response.json()
    assert valid_payload["code"] == 200
    assert valid_payload["data"]["current_page"] == 3

    recommendations_payload = load_json(meta_dir / "recommendations_database.json")
    target_after_valid = find_by_id(recommendations_payload.get("recommendations", []), recommendation_id)
    assert target_after_valid is not None
    assert target_after_valid["current_page"] == 3

    invalid_response = requests.put(
        f"{base_url}/api/v1/recommendation/progress",
        json={"recommendation_id": recommendation_id, "current_page": 9},
        timeout=5,
    )
    assert invalid_response.status_code == 200
    invalid_payload = invalid_response.json()
    assert invalid_payload["code"] == 400

    recommendations_after_invalid = load_json(meta_dir / "recommendations_database.json")
    target_after_invalid = find_by_id(
        recommendations_after_invalid.get("recommendations", []),
        recommendation_id,
    )
    assert target_after_invalid is not None
    assert target_after_invalid["current_page"] == 3

