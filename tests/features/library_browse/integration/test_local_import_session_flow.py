from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import shutil
import time
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


def _find_comic_id_by_title(base_url: str, title: str) -> str:
    list_resp = requests.get(f"{base_url}/api/v1/comic/list", timeout=10)
    assert list_resp.status_code == 200
    payload = list_resp.json()
    assert payload.get("code") == 200
    for item in payload.get("data") or []:
        if str(item.get("title") or "") == title:
            comic_id = str(item.get("id") or "").strip()
            if comic_id:
                return comic_id
    raise AssertionError(f"comic not found by title: {title}")


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _save_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


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


def _decode_softref_locator(locator: str) -> dict:
    raw = str(locator or "").strip()
    if not raw.startswith("softref://"):
        return {}
    encoded = raw[len("softref://") :]
    if not encoded:
        return {}
    padding = "=" * ((4 - len(encoded) % 4) % 4)
    decoded = base64.urlsafe_b64decode((encoded + padding).encode("ascii")).decode("utf-8")
    payload = json.loads(decoded)
    return payload if isinstance(payload, dict) else {}


def _archive_fingerprint(top_archive_path: str, archive_chain: list[str]) -> str:
    top = os.path.normcase(os.path.abspath(str(top_archive_path or "")))
    chain = "|".join(str(item or "") for item in (archive_chain or []))
    return hashlib.sha1(f"{top}::{chain}".encode("utf-8")).hexdigest()


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
def test_local_import_hardlink_move_alias_matches_move_mode_behavior(integration_runtime):
    base_url = integration_runtime["base_url"]
    runtime_root: Path = integration_runtime["runtime_root"]

    source_dir = runtime_root / "local_import_case_hardlink_alias"
    if source_dir.exists():
        shutil.rmtree(source_dir, ignore_errors=True)

    _write_png(source_dir / "作者硬链" / "作品硬链" / "001.png")

    try:
        parse_resp = requests.post(
            f"{base_url}/api/v1/comic/batch-upload/session/from-path",
            json={"source_path": str(source_dir), "import_mode": "hardlink_move"},
            timeout=60,
        )
        assert parse_resp.status_code == 200
        parse_payload = parse_resp.json()
        assert parse_payload["code"] == 200
        data = parse_payload["data"]
        session_id = data["session_id"]
        assert data.get("import_mode") == "hardlink_move"
        assert data.get("effective_mode") == "move_huge"
        node_map = _build_node_map(data["tree"])

        assignments = {
            _find_parent_id_by_name(node_map, "作者硬链"): "author",
            _find_parent_id_by_name(node_map, "作品硬链"): "work",
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
        assert result["imported_count"] >= 1
        assert result["session_removed"] is True

        # 与 move_huge 行为一致：源目录中的作品被移动走
        assert not (source_dir / "作者硬链" / "作品硬链").exists()
    finally:
        _cleanup_imported_comics(base_url, ["作品硬链"])


@pytest.mark.integration
def test_local_import_copy_mode_supports_single_layer_archive_password(integration_runtime):
    base_url = integration_runtime["base_url"]
    runtime_root: Path = integration_runtime["runtime_root"]

    try:
        import py7zr  # type: ignore
    except Exception:
        pytest.skip("py7zr not available")

    source_dir = runtime_root / "local_import_case_copy_password"
    if source_dir.exists():
        shutil.rmtree(source_dir, ignore_errors=True)

    author_name = "作者复制密码"
    title = "作品加密copy"
    archive_password = "copy-pass-001"
    archive_path = source_dir / author_name / f"{title}.7z"
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    with py7zr.SevenZipFile(str(archive_path), "w", password=archive_password) as archive:
        archive.writestr(PNG_1X1, "001.png")

    try:
        parse_resp = requests.post(
            f"{base_url}/api/v1/comic/batch-upload/session/from-path",
            json={
                "source_path": str(source_dir),
                "import_mode": "copy_safe",
                "archive_password": archive_password,
            },
            timeout=60,
        )
        assert parse_resp.status_code == 200
        parse_payload = parse_resp.json()
        assert parse_payload["code"] == 200
        session_id = parse_payload["data"]["session_id"]
        node_map = _build_node_map(parse_payload["data"]["tree"])

        assignments = {
            _find_parent_id_by_name(node_map, author_name): "author",
            _find_parent_id_by_name(node_map, title): "work",
        }
        commit_resp = requests.post(
            f"{base_url}/api/v1/comic/batch-upload/session/commit",
            json={"session_id": session_id, "assignments": assignments},
            timeout=60,
        )
        assert commit_resp.status_code == 200
        commit_payload = commit_resp.json()
        assert commit_payload["code"] == 200
        assert commit_payload["data"]["failed_count"] == 0

        comic_id = _find_comic_id_by_title(base_url, title)
        images_resp = requests.get(
            f"{base_url}/api/v1/comic/images",
            params={"comic_id": comic_id},
            timeout=30,
        )
        assert images_resp.status_code == 200
        images_payload = images_resp.json()
        assert images_payload["code"] == 200
        assert len(images_payload["data"]) >= 1
    finally:
        _cleanup_imported_comics(base_url, [title])


@pytest.mark.integration
def test_local_import_move_mode_supports_single_layer_archive_password(integration_runtime):
    base_url = integration_runtime["base_url"]
    runtime_root: Path = integration_runtime["runtime_root"]

    try:
        import py7zr  # type: ignore
    except Exception:
        pytest.skip("py7zr not available")

    source_dir = runtime_root / "local_import_case_move_password"
    if source_dir.exists():
        shutil.rmtree(source_dir, ignore_errors=True)

    author_name = "作者移动密码"
    title = "作品加密move"
    archive_password = "move-pass-001"
    archive_path = source_dir / author_name / f"{title}.7z"
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    with py7zr.SevenZipFile(str(archive_path), "w", password=archive_password) as archive:
        archive.writestr(PNG_1X1, "001.png")

    try:
        parse_resp = requests.post(
            f"{base_url}/api/v1/comic/batch-upload/session/from-path",
            json={
                "source_path": str(source_dir),
                "import_mode": "move_huge",
                "archive_password": archive_password,
            },
            timeout=60,
        )
        assert parse_resp.status_code == 200
        parse_payload = parse_resp.json()
        assert parse_payload["code"] == 200
        session_id = parse_payload["data"]["session_id"]
        node_map = _build_node_map(parse_payload["data"]["tree"])

        assert not archive_path.exists()
        assert (source_dir / author_name / title).exists()

        assignments = {
            _find_parent_id_by_name(node_map, author_name): "author",
            _find_parent_id_by_name(node_map, title): "work",
        }
        commit_resp = requests.post(
            f"{base_url}/api/v1/comic/batch-upload/session/commit",
            json={"session_id": session_id, "assignments": assignments},
            timeout=60,
        )
        assert commit_resp.status_code == 200
        commit_payload = commit_resp.json()
        assert commit_payload["code"] == 200
        assert commit_payload["data"]["failed_count"] == 0
    finally:
        _cleanup_imported_comics(base_url, [title])


@pytest.mark.integration
def test_local_import_softlink_mode_skips_nested_archive_without_modifying_source(integration_runtime):
    base_url = integration_runtime["base_url"]
    runtime_root: Path = integration_runtime["runtime_root"]

    source_dir = runtime_root / "local_import_case_softlink_tree"
    if source_dir.exists():
        shutil.rmtree(source_dir, ignore_errors=True)

    _write_png(source_dir / "作者软链" / "作品目录" / "001.png")

    nested_zip_bytes = io.BytesIO()
    with zipfile.ZipFile(nested_zip_bytes, "w", compression=zipfile.ZIP_DEFLATED) as nested_zip:
        nested_zip.writestr("作品压缩内/001.png", PNG_1X1)

    outer_zip = source_dir / "作者软链" / "作品压缩.zip"
    with zipfile.ZipFile(outer_zip, "w", compression=zipfile.ZIP_DEFLATED) as outer:
        outer.writestr("作品压缩/外层001.png", PNG_1X1)
        outer.writestr("作品压缩/内层.zip", nested_zip_bytes.getvalue())
    size_before = outer_zip.stat().st_size

    parse_resp = requests.post(
        f"{base_url}/api/v1/comic/batch-upload/session/from-path",
        json={"source_path": str(source_dir), "import_mode": "softlink_ref"},
        timeout=30,
    )
    assert parse_resp.status_code == 200
    payload = parse_resp.json()
    assert payload["code"] == 200
    data = payload["data"]
    assert data.get("effective_mode") == "softlink_ref"
    warnings = list(data.get("warnings") or [])

    node_map = _build_node_map(data["tree"])
    all_names = {str(node.get("real_name") or "") for node in node_map.values()}
    assert "作者软链" in all_names
    assert "作品目录" in all_names
    assert "作品压缩" in all_names
    assert "内层" not in all_names
    assert any("内层压缩包" in item for item in warnings)

    # 源目录和压缩包不可被改动/删除
    assert (source_dir / "作者软链" / "作品目录").exists()
    assert outer_zip.exists()
    assert outer_zip.stat().st_size == size_before


@pytest.mark.integration
def test_local_import_softlink_mode_commit_creates_soft_ref_records(integration_runtime):
    base_url = integration_runtime["base_url"]
    runtime_root: Path = integration_runtime["runtime_root"]
    meta_dir: Path = integration_runtime["meta_dir"]

    source_dir = runtime_root / "local_import_case_softlink_commit"
    if source_dir.exists():
        shutil.rmtree(source_dir, ignore_errors=True)

    _write_png(source_dir / "作者软链" / "作品目录" / "001.png")
    _write_zip_with_png(source_dir / "作者软链" / "作品压缩.zip", ["作品压缩/001.png"])
    zip_size_before = (source_dir / "作者软链" / "作品压缩.zip").stat().st_size

    try:
        parse_resp = requests.post(
            f"{base_url}/api/v1/comic/batch-upload/session/from-path",
            json={"source_path": str(source_dir), "import_mode": "softlink_ref"},
            timeout=30,
        )
        assert parse_resp.status_code == 200
        parse_payload = parse_resp.json()
        assert parse_payload["code"] == 200
        data = parse_payload["data"]
        session_id = data["session_id"]
        assert data.get("effective_mode") == "softlink_ref"

        node_map = _build_node_map(data["tree"])
        assignments = {
            _find_parent_id_by_name(node_map, "作者软链"): "author",
            _find_parent_id_by_name(node_map, "作品目录"): "work",
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
        assert result["status"] == "completed"
        assert result["failed_count"] == 0
        assert result["imported_count"] >= 2

        comics_data = _load_json(meta_dir / "comics_database.json")
        comic_a = _find_comic_by_title(comics_data, "作品目录")
        comic_b = _find_comic_by_title(comics_data, "作品压缩")

        for comic in (comic_a, comic_b):
            assert comic.get("storage_mode") == "soft_ref"
            assert str(comic.get("import_source") or "").strip()
            assert int(comic.get("total_page") or 0) >= 1
            cover_path = str(comic.get("cover_path") or "")
            assert (
                cover_path.startswith("/api/v1/comic/image?comic_id=")
                or cover_path.startswith("/static/cover/")
            )

        # 软连接压缩包作品可直接走阅读接口按页读取
        archive_comic_id = str(comic_b.get("id") or "")
        archive_images_resp = requests.get(
            f"{base_url}/api/v1/comic/images",
            params={"comic_id": archive_comic_id},
            timeout=30,
        )
        assert archive_images_resp.status_code == 200
        archive_images_payload = archive_images_resp.json()
        assert archive_images_payload["code"] == 200
        archive_image_urls = archive_images_payload["data"]
        assert isinstance(archive_image_urls, list)
        assert len(archive_image_urls) >= 1

        archive_first_image_resp = requests.get(f"{base_url}{archive_image_urls[0]}", timeout=30)
        assert archive_first_image_resp.status_code == 200
        assert archive_first_image_resp.headers.get("Content-Type", "").startswith("image/")
        assert len(archive_first_image_resp.content) > 0

        # 提交后源文件仍保持原位
        assert (source_dir / "作者软链" / "作品目录").exists()
        assert (source_dir / "作者软链" / "作品压缩.zip").exists()
        assert (source_dir / "作者软链" / "作品压缩.zip").stat().st_size == zip_size_before
    finally:
        _cleanup_imported_comics(base_url, ["作品目录", "作品压缩"])


@pytest.mark.integration
def test_local_import_softlink_mode_commit_generates_static_cover_async(integration_runtime):
    base_url = integration_runtime["base_url"]
    runtime_root: Path = integration_runtime["runtime_root"]
    data_dir: Path = integration_runtime["data_dir"]
    meta_dir: Path = integration_runtime["meta_dir"]

    source_dir = runtime_root / "local_import_case_softlink_async_cover"
    if source_dir.exists():
        shutil.rmtree(source_dir, ignore_errors=True)

    author_name = "作者异步封面"
    title = "作品异步封面"
    _write_png(source_dir / author_name / title / "001.png")

    try:
        parse_resp = requests.post(
            f"{base_url}/api/v1/comic/batch-upload/session/from-path",
            json={"source_path": str(source_dir), "import_mode": "softlink_ref"},
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

        commit_resp = requests.post(
            f"{base_url}/api/v1/comic/batch-upload/session/commit",
            json={"session_id": session_id, "assignments": assignments},
            timeout=60,
        )
        assert commit_resp.status_code == 200
        commit_payload = commit_resp.json()
        assert commit_payload["code"] == 200
        assert commit_payload["data"]["failed_count"] == 0

        cover_ok = False
        deadline = time.time() + 15
        while time.time() < deadline:
            comics_data = _load_json(meta_dir / "comics_database.json")
            comic = _find_comic_by_title(comics_data, title)
            cover_path = str(comic.get("cover_path") or "").strip()
            if cover_path.startswith("/static/cover/"):
                rel = cover_path[len("/static/cover/") :].replace("/", os.sep)
                cover_abs = data_dir / "static" / "cover" / rel
                if cover_abs.exists():
                    cover_ok = True
                    break
            time.sleep(0.25)

        assert cover_ok, "软连接导入后未在预期时间内异步生成 static 封面"
    finally:
        _cleanup_imported_comics(base_url, [title])


@pytest.mark.integration
def test_local_import_softlink_mode_reader_can_stream_images_from_directory_source(integration_runtime):
    base_url = integration_runtime["base_url"]
    runtime_root: Path = integration_runtime["runtime_root"]
    meta_dir: Path = integration_runtime["meta_dir"]

    source_dir = runtime_root / "local_import_case_softlink_reader_dir"
    if source_dir.exists():
        shutil.rmtree(source_dir, ignore_errors=True)

    author_name = "作者读图"
    title = "作品读图目录"
    _write_png(source_dir / author_name / title / "001.png")
    _write_png(source_dir / author_name / title / "002.png")

    try:
        parse_resp = requests.post(
            f"{base_url}/api/v1/comic/batch-upload/session/from-path",
            json={"source_path": str(source_dir), "import_mode": "softlink_ref"},
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

        commit_resp = requests.post(
            f"{base_url}/api/v1/comic/batch-upload/session/commit",
            json={"session_id": session_id, "assignments": assignments},
            timeout=60,
        )
        assert commit_resp.status_code == 200
        commit_payload = commit_resp.json()
        assert commit_payload["code"] == 200
        assert commit_payload["data"]["failed_count"] == 0

        comics_data = _load_json(meta_dir / "comics_database.json")
        comic = _find_comic_by_title(comics_data, title)
        comic_id = str(comic.get("id") or "")
        assert comic.get("storage_mode") == "soft_ref"
        assert comic_id

        images_resp = requests.get(
            f"{base_url}/api/v1/comic/images",
            params={"comic_id": comic_id},
            timeout=30,
        )
        assert images_resp.status_code == 200
        images_payload = images_resp.json()
        assert images_payload["code"] == 200
        image_urls = images_payload["data"]
        assert isinstance(image_urls, list)
        assert len(image_urls) == 2

        first_image_resp = requests.get(f"{base_url}{image_urls[0]}", timeout=30)
        assert first_image_resp.status_code == 200
        assert first_image_resp.headers.get("Content-Type", "").startswith("image/")
        assert first_image_resp.content[:8] == PNG_1X1[:8]
    finally:
        _cleanup_imported_comics(base_url, [title])


@pytest.mark.integration
def test_local_import_softlink_mode_reader_returns_missing_source_error_after_source_removed(integration_runtime):
    base_url = integration_runtime["base_url"]
    runtime_root: Path = integration_runtime["runtime_root"]

    source_dir = runtime_root / "local_import_case_softlink_missing_source"
    if source_dir.exists():
        shutil.rmtree(source_dir, ignore_errors=True)

    author_name = "作者丢失"
    title = "作品源丢失"
    work_dir = source_dir / author_name / title
    _write_png(work_dir / "001.png")

    try:
        parse_resp = requests.post(
            f"{base_url}/api/v1/comic/batch-upload/session/from-path",
            json={"source_path": str(source_dir), "import_mode": "softlink_ref"},
            timeout=30,
        )
        assert parse_resp.status_code == 200
        parse_payload = parse_resp.json()
        assert parse_payload["code"] == 200
        session_id = parse_payload["data"]["session_id"]
        node_map = _build_node_map(parse_payload["data"]["tree"])

        assignments = {
            _find_parent_id_by_name(node_map, author_name): "author",
            _find_parent_id_by_name(node_map, title): "work",
        }
        commit_resp = requests.post(
            f"{base_url}/api/v1/comic/batch-upload/session/commit",
            json={"session_id": session_id, "assignments": assignments},
            timeout=60,
        )
        assert commit_resp.status_code == 200
        assert commit_resp.json()["code"] == 200

        comic_id = _find_comic_id_by_title(base_url, title)

        for _ in range(50):
            shutil.rmtree(work_dir, ignore_errors=True)
            if not work_dir.exists():
                break
            time.sleep(0.1)
        assert not work_dir.exists()

        images_resp = requests.get(
            f"{base_url}/api/v1/comic/images",
            params={"comic_id": comic_id},
            timeout=30,
        )
        assert images_resp.status_code == 200
        images_payload = images_resp.json()
        assert images_payload["code"] == 404
    finally:
        _cleanup_imported_comics(base_url, [title])


@pytest.mark.integration
def test_organize_database_backfills_soft_ref_cover_from_default_placeholder(integration_runtime):
    base_url = integration_runtime["base_url"]
    runtime_root: Path = integration_runtime["runtime_root"]
    meta_dir: Path = integration_runtime["meta_dir"]

    source_dir = runtime_root / "local_import_case_softlink_cover_backfill"
    if source_dir.exists():
        shutil.rmtree(source_dir, ignore_errors=True)

    author_name = "作者封面修复"
    title = "作品封面修复"
    _write_png(source_dir / author_name / title / "001.png")

    try:
        parse_resp = requests.post(
            f"{base_url}/api/v1/comic/batch-upload/session/from-path",
            json={"source_path": str(source_dir), "import_mode": "softlink_ref"},
            timeout=30,
        )
        assert parse_resp.status_code == 200
        parse_payload = parse_resp.json()
        assert parse_payload["code"] == 200
        session_id = parse_payload["data"]["session_id"]
        node_map = _build_node_map(parse_payload["data"]["tree"])

        assignments = {
            _find_parent_id_by_name(node_map, author_name): "author",
            _find_parent_id_by_name(node_map, title): "work",
        }
        commit_resp = requests.post(
            f"{base_url}/api/v1/comic/batch-upload/session/commit",
            json={"session_id": session_id, "assignments": assignments},
            timeout=60,
        )
        assert commit_resp.status_code == 200
        assert commit_resp.json()["code"] == 200

        comics_db = meta_dir / "comics_database.json"
        comics_data = _load_json(comics_db)
        comic = _find_comic_by_title(comics_data, title)
        comic["cover_path"] = f"/api/v1/comic/image?comic_id={comic.get('id')}&page_num=1"
        _save_json(comics_db, comics_data)

        organize_resp = requests.post(f"{base_url}/api/v1/comic/organize", timeout=60)
        assert organize_resp.status_code == 200
        organize_payload = organize_resp.json()
        assert organize_payload["code"] == 200

        refreshed_data = _load_json(comics_db)
        refreshed = _find_comic_by_title(refreshed_data, title)
        repaired_cover = str(refreshed.get("cover_path") or "").strip()
        assert repaired_cover
        assert repaired_cover.startswith("/static/cover/JM/")
        cover_rel = repaired_cover[len("/static/cover/") :].replace("/", os.sep)
        cover_abs = (integration_runtime["data_dir"] / "static" / "cover" / cover_rel)
        assert cover_abs.exists()
    finally:
        _cleanup_imported_comics(base_url, [title])


@pytest.mark.integration
def test_local_import_softlink_mode_reader_uses_import_password_for_encrypted_7z(integration_runtime):
    base_url = integration_runtime["base_url"]
    runtime_root: Path = integration_runtime["runtime_root"]
    data_dir: Path = integration_runtime["data_dir"]

    try:
        import py7zr  # type: ignore
    except Exception:
        pytest.skip("py7zr not available")

    source_dir = runtime_root / "local_import_case_softlink_password_flow"
    if source_dir.exists():
        shutil.rmtree(source_dir, ignore_errors=True)

    author_name = "作者密码"
    title = "作品加密7z"
    archive_password = "stage3-softref-pass"
    archive_path = source_dir / author_name / f"{title}.7z"
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    with py7zr.SevenZipFile(str(archive_path), "w", password=archive_password) as archive:
        archive.writestr(PNG_1X1, f"{title}/001.png")
        archive.writestr(PNG_1X1, f"{title}/002.png")

    try:
        parse_resp = requests.post(
            f"{base_url}/api/v1/comic/batch-upload/session/from-path",
            json={
                "source_path": str(source_dir),
                "import_mode": "softlink_ref",
                "archive_password": archive_password,
            },
            timeout=60,
        )
        assert parse_resp.status_code == 200
        parse_payload = parse_resp.json()
        assert parse_payload["code"] == 200
        session_id = parse_payload["data"]["session_id"]
        node_map = _build_node_map(parse_payload["data"]["tree"])

        assignments = {
            _find_parent_id_by_name(node_map, author_name): "author",
            _find_parent_id_by_name(node_map, title): "work",
        }
        commit_resp = requests.post(
            f"{base_url}/api/v1/comic/batch-upload/session/commit",
            json={"session_id": session_id, "assignments": assignments},
            timeout=60,
        )
        assert commit_resp.status_code == 200
        commit_payload = commit_resp.json()
        assert commit_payload["code"] == 200
        assert commit_payload["data"]["failed_count"] == 0

        comic_id = _find_comic_id_by_title(base_url, title)

        images_resp = requests.get(
            f"{base_url}/api/v1/comic/images",
            params={"comic_id": comic_id},
            timeout=30,
        )
        assert images_resp.status_code == 200
        images_payload = images_resp.json()
        assert images_payload["code"] == 200
        image_urls = images_payload["data"]
        assert isinstance(image_urls, list)
        assert len(image_urls) >= 2

        comics_data = _load_json(data_dir / "meta_data" / "comics_database.json")
        comic_entry = _find_comic_by_title(comics_data, title)
        locator = str(comic_entry.get("soft_ref_locator") or comic_entry.get("import_source") or "")
        locator_payload = _decode_softref_locator(locator)
        archive_fingerprint = _archive_fingerprint(
            str(locator_payload.get("top_archive_path") or ""),
            list(locator_payload.get("archive_chain") or []),
        )
        assert archive_fingerprint

        password_store = data_dir / "cache" / "comic_softref_passwords.json"
        assert password_store.exists()
        store_payload = json.loads(password_store.read_text(encoding="utf-8"))
        assert store_payload["archives"][archive_fingerprint]["password"] == archive_password

        image_resp = requests.get(f"{base_url}{image_urls[0]}", timeout=30)
        assert image_resp.status_code == 200
        assert image_resp.headers.get("Content-Type", "").startswith("image/")
        assert image_resp.content[:8] == PNG_1X1[:8]
    finally:
        _cleanup_imported_comics(base_url, [title])


@pytest.mark.integration
def test_local_import_softlink_mode_external_encrypted_rar_smoke_if_available(integration_runtime):
    base_url = integration_runtime["base_url"]
    rar_path = Path(r"D:\uohsoaixgnaixgnawab.rar")
    if not rar_path.exists():
        pytest.skip("external encrypted rar not provided in this environment")

    size_before = rar_path.stat().st_size
    parse_resp = requests.post(
        f"{base_url}/api/v1/comic/batch-upload/session/from-path",
        json={
            "source_path": str(rar_path),
            "import_mode": "softlink_ref",
            "archive_password": "uohsoaixgnaixgnawab",
        },
        timeout=120,
    )
    assert parse_resp.status_code == 200
    payload = parse_resp.json()
    assert payload["code"] == 200
    data = payload["data"]
    assert data.get("effective_mode") == "softlink_ref"
    tree = data.get("tree") or {}
    total_images = int(tree.get("total_images") or 0)
    warnings = data.get("warnings") or []
    if total_images <= 0:
        assert len(warnings) > 0
    assert rar_path.exists()
    assert rar_path.stat().st_size == size_before


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
