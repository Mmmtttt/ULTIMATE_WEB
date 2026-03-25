from __future__ import annotations

import base64
import shutil
from pathlib import Path

import pytest
import requests

PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/w8AAgMBgN6QHdwAAAAASUVORK5CYII="
)


def _write_png(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(PNG_1X1)


def _build_node_map(tree: dict) -> dict:
    node_map = {}

    def walk(node: dict, parent_id: str | None = None) -> None:
        node_id = node["id"]
        node_map[node_id] = {
            "id": node_id,
            "real_name": node.get("real_name", ""),
            "parent_id": parent_id,
            "children": [child["id"] for child in node.get("children", [])],
        }
        for child in node.get("children", []):
            walk(child, node_id)

    walk(tree)
    return node_map


def _find_parent_id_by_name(node_map: dict, name: str) -> str:
    for node in node_map.values():
        if node["real_name"] == name:
            parent_id = node["parent_id"]
            if parent_id is None:
                raise AssertionError(f"node {name} has no parent")
            return parent_id
    raise AssertionError(f"node not found: {name}")


@pytest.mark.integration
def test_local_import_parse_export_commit_success(integration_runtime):
    base_url = integration_runtime["base_url"]
    runtime_root: Path = integration_runtime["runtime_root"]
    data_dir: Path = integration_runtime["data_dir"]

    source_dir = runtime_root / "local_import_case_success"
    if source_dir.exists():
        shutil.rmtree(source_dir, ignore_errors=True)

    _write_png(source_dir / "作者甲" / "作品一" / "001.png")
    _write_png(source_dir / "作者甲" / "作品二" / "001.png")

    parse_resp = requests.post(
        f"{base_url}/api/v1/comic/batch-upload/session/from-path",
        json={"source_path": str(source_dir)},
        timeout=30,
    )
    assert parse_resp.status_code == 200
    parse_payload = parse_resp.json()
    assert parse_payload["code"] == 200

    data = parse_payload["data"]
    session_id = data["session_id"]
    node_map = _build_node_map(data["tree"])

    assignments = {
        _find_parent_id_by_name(node_map, "作者甲"): "author",
        _find_parent_id_by_name(node_map, "作品一"): "work",
    }

    export_resp = requests.post(
        f"{base_url}/api/v1/comic/batch-upload/session/export",
        json={"session_id": session_id, "assignments": assignments},
        timeout=30,
    )
    assert export_resp.status_code == 200
    export_payload = export_resp.json()
    assert export_payload["code"] == 200
    assert export_payload["data"]["count"] == 2

    commit_resp = requests.post(
        f"{base_url}/api/v1/comic/batch-upload/session/commit",
        json={"session_id": session_id, "assignments": assignments},
        timeout=60,
    )
    assert commit_resp.status_code == 200
    commit_payload = commit_resp.json()
    assert commit_payload["code"] == 200
    result = commit_payload["data"]
    assert result["failed_count"] == 0
    assert result["imported_count"] == 2
    assert result["session_removed"] is True

    session_dir = data_dir / "cache" / "comic_local_import_workspace" / session_id
    assert not session_dir.exists()

    list_resp = requests.get(f"{base_url}/api/v1/comic/list", timeout=10)
    assert list_resp.status_code == 200
    list_payload = list_resp.json()
    assert list_payload["code"] == 200
    titles = {item.get("title") for item in (list_payload.get("data") or [])}
    assert "作品一" in titles
    assert "作品二" in titles


@pytest.mark.integration
def test_local_import_commit_can_resume_after_partial_failure(integration_runtime):
    base_url = integration_runtime["base_url"]
    runtime_root: Path = integration_runtime["runtime_root"]
    data_dir: Path = integration_runtime["data_dir"]

    source_dir = runtime_root / "local_import_case_resume"
    if source_dir.exists():
        shutil.rmtree(source_dir, ignore_errors=True)

    _write_png(source_dir / "作者乙" / "作品甲" / "001.png")
    _write_png(source_dir / "作者乙" / "作品乙" / "001.png")

    parse_resp = requests.post(
        f"{base_url}/api/v1/comic/batch-upload/session/from-path",
        json={"source_path": str(source_dir)},
        timeout=30,
    )
    assert parse_resp.status_code == 200
    data = parse_resp.json()["data"]
    session_id = data["session_id"]
    node_map = _build_node_map(data["tree"])

    assignments = {
        _find_parent_id_by_name(node_map, "作者乙"): "author",
        _find_parent_id_by_name(node_map, "作品甲"): "work",
    }

    export_resp = requests.post(
        f"{base_url}/api/v1/comic/batch-upload/session/export",
        json={"session_id": session_id, "assignments": assignments},
        timeout=30,
    )
    assert export_resp.status_code == 200
    export_items = export_resp.json()["data"]["items"]
    assert len(export_items) == 2

    removed_work_dir = Path(export_items[1]["作品文件地址"])
    for image_file in removed_work_dir.rglob("*.png"):
        image_file.unlink(missing_ok=True)

    first_commit_resp = requests.post(
        f"{base_url}/api/v1/comic/batch-upload/session/commit",
        json={"session_id": session_id, "assignments": assignments},
        timeout=60,
    )
    assert first_commit_resp.status_code == 200
    first_commit_payload = first_commit_resp.json()
    assert first_commit_payload["code"] == 200
    first_result = first_commit_payload["data"]
    assert first_result["failed_count"] == 1
    assert first_result["status"] == "failed"
    assert first_result["session_removed"] is False

    _write_png(removed_work_dir / "001.png")

    second_commit_resp = requests.post(
        f"{base_url}/api/v1/comic/batch-upload/session/commit",
        json={"session_id": session_id, "assignments": assignments},
        timeout=60,
    )
    assert second_commit_resp.status_code == 200
    second_commit_payload = second_commit_resp.json()
    assert second_commit_payload["code"] == 200
    second_result = second_commit_payload["data"]
    assert second_result["failed_count"] == 0
    assert second_result["status"] == "completed"
    assert second_result["session_removed"] is True
    assert second_result["imported_count"] >= 2

    session_dir = data_dir / "cache" / "comic_local_import_workspace" / session_id
    assert not session_dir.exists()

    list_resp = requests.get(f"{base_url}/api/v1/comic/list", timeout=10)
    assert list_resp.status_code == 200
    titles = {item.get("title") for item in (list_resp.json().get("data") or [])}
    assert "作品甲" in titles
    assert "作品乙" in titles
