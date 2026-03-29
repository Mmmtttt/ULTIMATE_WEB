from __future__ import annotations

import base64
import json
import shutil
import zipfile
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


def _write_zip_with_png(zip_path: Path, members: list[str]) -> None:
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for member in members:
            zf.writestr(member, PNG_1X1)


def _find_parent_id_by_name(node_map: dict, name: str) -> str:
    for node in node_map.values():
        if node["real_name"] == name:
            parent_id = node["parent_id"]
            if parent_id is None:
                raise AssertionError(f"node {name} has no parent")
            return parent_id
    raise AssertionError(f"node not found: {name}")


def _cleanup_imported_comics(base_url: str, titles: list[str]) -> None:
    list_resp = requests.get(f"{base_url}/api/v1/comic/list", timeout=10)
    if list_resp.status_code != 200:
        return
    payload = list_resp.json()
    if payload.get("code") != 200:
        return

    title_set = set(titles)
    for item in payload.get("data") or []:
        if item.get("title") not in title_set:
            continue
        comic_id = item.get("id")
        if not comic_id:
            continue
        requests.put(
            f"{base_url}/api/v1/comic/trash/move",
            json={"comic_id": comic_id},
            timeout=10,
        )
        requests.delete(
            f"{base_url}/api/v1/comic/trash/delete",
            json={"comic_id": comic_id},
            timeout=10,
        )


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _find_comic_by_title(comics_data: dict, title: str) -> dict:
    for item in comics_data.get("comics") or []:
        if item.get("title") == title:
            return item
    raise AssertionError(f"comic not found by title: {title}")


def _resolve_comic_tag_names(meta_dir: Path, title: str) -> set[str]:
    comics_data = _load_json(meta_dir / "comics_database.json")
    tags_data = _load_json(meta_dir / "tags_database.json")

    comic = _find_comic_by_title(comics_data, title)
    comic_tag_ids = set(comic.get("tag_ids") or [])

    tag_names: set[str] = set()
    for tag in tags_data.get("tags") or []:
        if tag.get("id") in comic_tag_ids:
            tag_names.add(str(tag.get("name") or ""))
    return tag_names


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

    try:
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
    finally:
        _cleanup_imported_comics(base_url, ["作品一", "作品二"])


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

    try:
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
    finally:
        _cleanup_imported_comics(base_url, ["作品甲", "作品乙"])


@pytest.mark.integration
def test_local_import_move_mode_extracts_nested_archives_and_moves_work_dirs(integration_runtime):
    base_url = integration_runtime["base_url"]
    runtime_root: Path = integration_runtime["runtime_root"]

    source_dir = runtime_root / "local_import_case_move_mode"
    if source_dir.exists():
        shutil.rmtree(source_dir, ignore_errors=True)

    _write_png(source_dir / "作者丙" / "作品一" / "001.png")
    _write_zip_with_png(
        source_dir / "作者丙" / "作品二.zip",
        ["第1话/001.png", "第2话/001.png"],
    )

    try:
        parse_resp = requests.post(
            f"{base_url}/api/v1/comic/batch-upload/session/from-path",
            json={"source_path": str(source_dir), "import_mode": "move_huge"},
            timeout=60,
        )
        assert parse_resp.status_code == 200
        parse_payload = parse_resp.json()
        assert parse_payload["code"] == 200
        data = parse_payload["data"]
        session_id = data["session_id"]
        node_map = _build_node_map(data["tree"])

        # 嵌套压缩包应已在源目录原地解压并删除压缩包文件
        assert not (source_dir / "作者丙" / "作品二.zip").exists()
        assert any(node["real_name"] == "作品二" for node in node_map.values())

        assignments = {
            _find_parent_id_by_name(node_map, "作者丙"): "author",
            _find_parent_id_by_name(node_map, "作品一"): "work",
        }

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
        assert result["status"] == "completed"
        assert result["imported_count"] >= 2
        assert result["session_removed"] is True

        # move 模式导入后，源目录作品会被移动走
        assert not (source_dir / "作者丙" / "作品一").exists()
        assert not (source_dir / "作者丙" / "作品二").exists()

        list_resp = requests.get(f"{base_url}/api/v1/comic/list", timeout=10)
        assert list_resp.status_code == 200
        titles = {item.get("title") for item in (list_resp.json().get("data") or [])}
        assert "作品一" in titles
        assert "作品二" in titles
    finally:
        _cleanup_imported_comics(base_url, ["作品一", "作品二"])


@pytest.mark.integration
def test_local_import_move_mode_can_resume_after_move_then_failed_indexing(integration_runtime):
    base_url = integration_runtime["base_url"]
    runtime_root: Path = integration_runtime["runtime_root"]
    data_dir: Path = integration_runtime["data_dir"]

    source_dir = runtime_root / "local_import_case_move_resume"
    if source_dir.exists():
        shutil.rmtree(source_dir, ignore_errors=True)

    _write_png(source_dir / "作者丁" / "作品正常" / "001.png")
    (source_dir / "作者丁" / "作品异常").mkdir(parents=True, exist_ok=True)
    (source_dir / "作者丁" / "作品异常" / "note.txt").write_text("no images", encoding="utf-8")

    try:
        parse_resp = requests.post(
            f"{base_url}/api/v1/comic/batch-upload/session/from-path",
            json={"source_path": str(source_dir), "import_mode": "move_huge"},
            timeout=60,
        )
        assert parse_resp.status_code == 200
        parse_payload = parse_resp.json()
        assert parse_payload["code"] == 200
        data = parse_payload["data"]
        session_id = data["session_id"]
        node_map = _build_node_map(data["tree"])

        assignments = {
            _find_parent_id_by_name(node_map, "作者丁"): "author",
            _find_parent_id_by_name(node_map, "作品正常"): "work",
        }

        first_commit_resp = requests.post(
            f"{base_url}/api/v1/comic/batch-upload/session/commit",
            json={"session_id": session_id, "assignments": assignments},
            timeout=60,
        )
        assert first_commit_resp.status_code == 200
        first_result = first_commit_resp.json()["data"]
        assert first_result["status"] == "failed"
        assert first_result["failed_count"] == 1
        assert first_result["session_removed"] is False

        recover_resp = requests.get(
            f"{base_url}/api/v1/comic/batch-upload/session/recoverable",
            timeout=10,
        )
        assert recover_resp.status_code == 200
        sessions = (recover_resp.json().get("data") or {}).get("sessions") or []
        assert any(item.get("session_id") == session_id for item in sessions)

        resume_resp = requests.post(
            f"{base_url}/api/v1/comic/batch-upload/session/resume",
            json={"session_id": session_id},
            timeout=30,
        )
        assert resume_resp.status_code == 200
        resume_payload = resume_resp.json()
        assert resume_payload["code"] == 200
        assert resume_payload["data"]["session_id"] == session_id

        state_path = data_dir / "cache" / "comic_local_import_workspace" / session_id / "import_state.json"
        state_data = json.loads(state_path.read_text(encoding="utf-8"))
        failed_record = None
        for record in (state_data.get("records") or {}).values():
            if str(record.get("status", "")).lower() == "failed":
                failed_record = record
                break
        assert failed_record is not None

        comic_id = str(failed_record.get("comic_id", "")).strip()
        assert comic_id
        original_id = comic_id[len("JM"):] if comic_id.startswith("JM") else comic_id
        repaired_dir = data_dir / "comic" / "local" / original_id
        assert repaired_dir.exists()
        _write_png(repaired_dir / "001.png")

        second_commit_resp = requests.post(
            f"{base_url}/api/v1/comic/batch-upload/session/commit",
            json={"session_id": session_id},
            timeout=60,
        )
        assert second_commit_resp.status_code == 200
        second_result = second_commit_resp.json()["data"]
        assert second_result["failed_count"] == 0
        assert second_result["status"] == "completed"
        assert second_result["session_removed"] is True

        recover_resp_after = requests.get(
            f"{base_url}/api/v1/comic/batch-upload/session/recoverable",
            timeout=10,
        )
        assert recover_resp_after.status_code == 200
        sessions_after = (recover_resp_after.json().get("data") or {}).get("sessions") or []
        assert not any(item.get("session_id") == session_id for item in sessions_after)
    finally:
        _cleanup_imported_comics(base_url, ["作品正常", "作品异常"])


@pytest.mark.integration
def test_local_import_commit_applies_single_level_parent_tag(integration_runtime):
    base_url = integration_runtime["base_url"]
    runtime_root: Path = integration_runtime["runtime_root"]
    meta_dir: Path = integration_runtime["meta_dir"]

    source_dir = runtime_root / "local_import_case_tag_single"
    if source_dir.exists():
        shutil.rmtree(source_dir, ignore_errors=True)

    tag_name = "标签单层分类"
    author_name = "作者标签甲"
    title = "作品标签单层"
    _write_png(source_dir / tag_name / author_name / title / "001.png")

    try:
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
            _find_parent_id_by_name(node_map, author_name): "author",
            _find_parent_id_by_name(node_map, title): "work",
        }
        tag_assignments = {
            _find_parent_id_by_name(node_map, tag_name): True,
        }

        export_resp = requests.post(
            f"{base_url}/api/v1/comic/batch-upload/session/export",
            json={
                "session_id": session_id,
                "assignments": assignments,
                "tag_assignments": tag_assignments,
            },
            timeout=30,
        )
        assert export_resp.status_code == 200
        export_payload = export_resp.json()
        assert export_payload["code"] == 200
        items = export_payload["data"]["items"]
        assert len(items) == 1
        assert items[0]["作品名称"] == title
        assert items[0]["标签名称列表"] == [tag_name]

        commit_resp = requests.post(
            f"{base_url}/api/v1/comic/batch-upload/session/commit",
            json={
                "session_id": session_id,
                "assignments": assignments,
                "tag_assignments": tag_assignments,
            },
            timeout=60,
        )
        assert commit_resp.status_code == 200
        commit_payload = commit_resp.json()
        assert commit_payload["code"] == 200
        result = commit_payload["data"]
        assert result["failed_count"] == 0
        assert result["imported_count"] == 1

        tag_names = _resolve_comic_tag_names(meta_dir, title)
        assert "本地" in tag_names
        assert tag_name in tag_names
    finally:
        _cleanup_imported_comics(base_url, [title])


@pytest.mark.integration
def test_local_import_commit_applies_multi_level_parent_tags(integration_runtime):
    base_url = integration_runtime["base_url"]
    runtime_root: Path = integration_runtime["runtime_root"]
    meta_dir: Path = integration_runtime["meta_dir"]

    source_dir = runtime_root / "local_import_case_tag_multi"
    if source_dir.exists():
        shutil.rmtree(source_dir, ignore_errors=True)

    tag_level_1 = "标签一级分类"
    tag_level_2 = "标签二级分类"
    author_name = "作者标签乙"
    title = "作品标签多级"
    _write_png(source_dir / tag_level_1 / tag_level_2 / author_name / title / "001.png")

    try:
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
            _find_parent_id_by_name(node_map, author_name): "author",
            _find_parent_id_by_name(node_map, title): "work",
        }
        tag_assignments = {
            _find_parent_id_by_name(node_map, tag_level_1): True,
            _find_parent_id_by_name(node_map, tag_level_2): True,
        }

        export_resp = requests.post(
            f"{base_url}/api/v1/comic/batch-upload/session/export",
            json={
                "session_id": session_id,
                "assignments": assignments,
                "tag_assignments": tag_assignments,
            },
            timeout=30,
        )
        assert export_resp.status_code == 200
        export_payload = export_resp.json()
        assert export_payload["code"] == 200
        items = export_payload["data"]["items"]
        assert len(items) == 1
        assert items[0]["作品名称"] == title
        assert items[0]["标签名称列表"] == [tag_level_1, tag_level_2]

        commit_resp = requests.post(
            f"{base_url}/api/v1/comic/batch-upload/session/commit",
            json={
                "session_id": session_id,
                "assignments": assignments,
                "tag_assignments": tag_assignments,
            },
            timeout=60,
        )
        assert commit_resp.status_code == 200
        commit_payload = commit_resp.json()
        assert commit_payload["code"] == 200
        result = commit_payload["data"]
        assert result["failed_count"] == 0
        assert result["imported_count"] == 1

        tag_names = _resolve_comic_tag_names(meta_dir, title)
        assert "本地" in tag_names
        assert tag_level_1 in tag_names
        assert tag_level_2 in tag_names
    finally:
        _cleanup_imported_comics(base_url, [title])
