from __future__ import annotations

import hashlib
import os
import shutil
import socket
import subprocess
import sys
import time
import zipfile
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import pytest
import requests

from tests.shared.runtime_data import find_by_id, load_json, save_json
from tests.shared.test_constants import REPO_ROOT
from tests.tools.prepare_test_env import prepare_profile


def _wait_for_backend(base_url: str, timeout_seconds: int = 90) -> None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            response = requests.get(f"{base_url}/health", timeout=1)
            if response.status_code == 200:
                return
        except requests.RequestException:
            pass
        time.sleep(0.5)
    raise TimeoutError(f"Backend did not become ready in {timeout_seconds}s: {base_url}")


def _reserve_port() -> int:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = int(sock.getsockname()[1])
    sock.close()
    return port


def _start_backend(prepared: dict, port: int, log_name: str) -> dict:
    env = os.environ.copy()
    fake_deps_dir = Path(REPO_ROOT) / "tests" / "shared" / "fake_deps"
    existing_pythonpath = str(env.get("PYTHONPATH", "")).strip()
    env["PYTHONPATH"] = (
        f"{fake_deps_dir}{os.pathsep}{existing_pythonpath}"
        if existing_pythonpath
        else str(fake_deps_dir)
    )
    env.update(
        {
            "SERVER_CONFIG_PATH": prepared["server_config_path"],
            "THIRD_PARTY_CONFIG_PATH": prepared["third_party_config_path"],
            "BACKEND_HOST": "127.0.0.1",
            "BACKEND_PORT": str(port),
            "BACKEND_DEBUG": "0",
            "BACKEND_ENABLE_THIRD_PARTY": "0",
            "PYTHONUNBUFFERED": "1",
        }
    )

    runtime_root = Path(prepared["runtime_root"])
    data_dir = Path(prepared["data_dir"])
    meta_dir = data_dir / "meta_data"
    log_path = runtime_root / log_name
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_fp = log_path.open("w", encoding="utf-8")

    backend_app = Path(REPO_ROOT) / "comic_backend" / "app.py"
    process = subprocess.Popen(
        [sys.executable, str(backend_app)],
        cwd=str(REPO_ROOT),
        env=env,
        stdout=log_fp,
        stderr=log_fp,
    )

    base_url = f"http://127.0.0.1:{port}"
    _wait_for_backend(base_url, timeout_seconds=90)
    return {
        "process": process,
        "log_fp": log_fp,
        "log_path": log_path,
        "runtime_root": runtime_root,
        "data_dir": data_dir,
        "meta_dir": meta_dir,
        "base_url": base_url,
    }


def _stop_backend(runtime: dict) -> None:
    process = runtime["process"]
    log_fp = runtime["log_fp"]
    try:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)
    finally:
        log_fp.close()


def _request_ok(
    method: str,
    url: str,
    *,
    json_body: dict | None = None,
    params: dict | None = None,
    timeout: int = 20,
) -> dict:
    response = requests.request(method, url, json=json_body, params=params, timeout=timeout)
    assert response.status_code == 200, f"{method} {url} failed: {response.status_code} {response.text[:300]}"
    payload = response.json()
    assert payload.get("code") == 200, f"{method} {url} business failed: {payload}"
    return payload.get("data")


def _upsert_by_id(items: list[dict], row: dict) -> None:
    row_id = str(row.get("id", "")).strip()
    assert row_id
    found = find_by_id(items, row_id)
    if found is None:
        items.append(row)
        return
    found.update(row)


def _update_total(payload: dict, root_key: str, total_key: str) -> None:
    rows = payload.get(root_key, [])
    payload[total_key] = len(rows) if isinstance(rows, list) else 0
    payload["last_updated"] = datetime.now().strftime("%Y-%m-%d")


def _write_binary(root: Path, rel_path: str, content: bytes) -> None:
    abs_path = root / rel_path.replace("/", os.sep)
    abs_path.parent.mkdir(parents=True, exist_ok=True)
    abs_path.write_bytes(content)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fp:
        while True:
            chunk = fp.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _wait_for_no_zip_files(directory: Path, timeout_seconds: float = 6.0) -> bool:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if not directory.is_dir():
            return True
        if not list(directory.glob("*.zip")):
            return True
        time.sleep(0.1)
    if not directory.is_dir():
        return True
    return not list(directory.glob("*.zip"))


def _collect_media_dirs(data_dir: Path) -> list[str]:
    result: list[str] = []
    for root in (data_dir / "comic", data_dir / "video"):
        if not root.is_dir():
            continue
        for platform_dir in sorted([p for p in root.iterdir() if p.is_dir()]):
            for content_dir in sorted([p for p in platform_dir.iterdir() if p.is_dir()]):
                has_file = any(path.is_file() for path in content_dir.rglob("*"))
                if not has_file:
                    continue
                rel = str(content_dir.relative_to(data_dir)).replace("\\", "/")
                result.append(rel)
    return sorted(result)


@pytest.fixture
def dual_sync_runtime() -> dict:
    suffix = uuid4().hex[:8]
    source_profile = f"sync_source_{suffix}"
    target_profile = f"sync_target_{suffix}"
    source_prepared = prepare_profile(source_profile, clean=True)
    target_prepared = prepare_profile(target_profile, clean=True)

    source_runtime: dict | None = None
    target_runtime: dict | None = None
    try:
        source_runtime = _start_backend(source_prepared, _reserve_port(), "backend-sync-source.log")
        target_runtime = _start_backend(target_prepared, _reserve_port(), "backend-sync-target.log")
        yield {"source": source_runtime, "target": target_runtime}
    finally:
        if target_runtime is not None:
            _stop_backend(target_runtime)
        if source_runtime is not None:
            _stop_backend(source_runtime)


@pytest.fixture
def single_sync_runtime() -> dict:
    profile = f"sync_single_{uuid4().hex[:8]}"
    prepared = prepare_profile(profile, clean=True)
    runtime = _start_backend(prepared, _reserve_port(), "backend-sync-single.log")
    try:
        yield runtime
    finally:
        _stop_backend(runtime)


@pytest.mark.integration
def test_sync_session_layered_packages_and_cleanup_exports(single_sync_runtime):
    """
    用例描述:
    - 用例目的: 看护同步会话的分层打包（media/cache/cover/meta）与会话结束后的导出压缩包清理。
    - 测试步骤:
      1. 在隔离 data 下写入 cache/recommendation_cache 真实文件，触发 cache 分层打包。
      2. 调用 /api/v1/sync/session/start，指定 media_chunk_size=1 与 client_media_dirs 以触发分块增量打包。
      3. 下载每个 package 并逐个检查 zip 内条目路径是否符合对应层级。
      4. 调用 /api/v1/sync/session/finish，并校验导出目录被删除、session 内 package 标记 unavailable。
    - 预期结果:
      1. packages 至少包含 media/cache/cover/meta 四类，且 media 为分块产物。
      2. 下载包内容与层级一致：media 仅含 comic/video，cache 包含 cache 与 recommendation_cache，meta 包含 meta_data 下核心 json。
      3. finish 后 source 端不会残留本次会话导出压缩包目录。
    - 历史变更:
      - 2026-03-23: 初始创建，覆盖分层压缩与会话收尾清理。
    """
    base_url = single_sync_runtime["base_url"]
    data_dir: Path = single_sync_runtime["data_dir"]

    cache_probe_rel = "cache/comic/sync_guard_cache_payload.bin"
    rec_cache_probe_rel = "recommendation_cache/comic/JM/sync_guard_thumb.png"
    _write_binary(data_dir, cache_probe_rel, b"sync-cache-probe")
    _write_binary(data_dir, rec_cache_probe_rel, b"sync-rec-cache-probe")

    all_media_dirs = _collect_media_dirs(data_dir)
    assert all_media_dirs, "seeded integration profile should contain media directories"
    client_known_dirs = [all_media_dirs[0]]
    expected_missing_dirs = [item for item in all_media_dirs if item not in client_known_dirs]

    session_data = _request_ok(
        "POST",
        f"{base_url}/api/v1/sync/session/start",
        json_body={
            "layers": ["media", "cache", "cover", "meta"],
            "media_chunk_size": 1,
            "client_media_dirs": client_known_dirs,
            "include_media": True,
            "include_cache": True,
            "include_cover": True,
            "include_meta": True,
        },
        timeout=40,
    )
    session_id = str(session_data.get("session_id", "")).strip()
    assert session_id

    packages = session_data.get("packages", [])
    assert isinstance(packages, list) and packages
    kinds = {str(item.get("type") or item.get("kind") or "").strip() for item in packages}
    assert {"media", "cache", "cover", "meta"}.issubset(kinds)

    media_packages = [item for item in packages if str(item.get("type") or item.get("kind")) == "media"]
    assert len(media_packages) == len(expected_missing_dirs)
    assert all(int(item.get("source_dirs", 0)) == 1 for item in media_packages)

    downloaded_entries: dict[str, list[str]] = {}
    tmp_root = data_dir / "cache" / f"sync_session_guard_downloads_{uuid4().hex[:8]}"
    tmp_root.mkdir(parents=True, exist_ok=True)
    try:
        for item in packages:
            package_name = str(item.get("name") or item.get("file") or "").strip()
            assert package_name
            download_resp = requests.get(
                f"{base_url}/api/v1/sync/download/{session_id}/{package_name}",
                timeout=40,
            )
            assert download_resp.status_code == 200
            zip_path = tmp_root / package_name
            zip_path.write_bytes(download_resp.content)
            with zipfile.ZipFile(zip_path, "r") as zip_fp:
                entries = sorted(zip_fp.namelist())
                downloaded_entries[package_name] = entries
    finally:
        shutil.rmtree(tmp_root, ignore_errors=True)

    for item in media_packages:
        package_name = str(item.get("name") or item.get("file") or "").strip()
        entries = downloaded_entries[package_name]
        assert entries
        assert all(entry.startswith(("comic/", "video/")) for entry in entries)

    cache_package = next(item for item in packages if str(item.get("type") or item.get("kind")) == "cache")
    cache_entries = downloaded_entries[str(cache_package.get("name"))]
    assert cache_probe_rel in cache_entries
    assert rec_cache_probe_rel in cache_entries

    cover_package = next(item for item in packages if str(item.get("type") or item.get("kind")) == "cover")
    cover_entries = downloaded_entries[str(cover_package.get("name"))]
    assert any(entry.startswith("static/cover/") for entry in cover_entries)

    meta_package = next(item for item in packages if str(item.get("type") or item.get("kind")) == "meta")
    meta_entries = set(downloaded_entries[str(meta_package.get("name"))])
    assert "meta_data/comics_database.json" in meta_entries
    assert "meta_data/videos_database.json" in meta_entries
    assert "meta_data/tags_database.json" in meta_entries
    assert "meta_data/lists_database.json" in meta_entries

    manifest_data = _request_ok(
        "GET",
        f"{base_url}/api/v1/sync/manifest",
        params={"session_id": session_id},
        timeout=10,
    )
    assert manifest_data.get("session_id") == session_id

    finish_data = _request_ok(
        "POST",
        f"{base_url}/api/v1/sync/session/finish",
        json_body={"session_id": session_id, "status": "completed"},
        timeout=20,
    )
    assert finish_data.get("session_id") == session_id
    assert bool(finish_data.get("exports_cleaned")) is True
    assert str(finish_data.get("exports_cleanup_error", "")).strip() == ""

    export_dir = data_dir / "cache" / "sync_exports" / session_id
    assert not export_dir.exists()

    session_detail = _request_ok("GET", f"{base_url}/api/v1/sync/session/{session_id}", timeout=10)
    for item in session_detail.get("packages", []):
        assert item.get("available") is False


@pytest.mark.integration
def test_directional_pull_remaps_tag_list_ids_and_verifies_each_transferred_asset(dual_sync_runtime):
    """
    用例描述:
    - 用例目的: 看护双端同步在“同名 tag/list 不同 ID”以及“同 ID 语义冲突”场景下的映射正确性，并逐文件校验资产传输结果。
    - 测试步骤:
      1. 构造 source/target 双环境：同名不同 ID 的 comic/video 最近导入标签、普通标签、列表；并注入同 ID 语义冲突标签。
      2. 构造 source 新漫画/新视频与真实资产文件（comic/video/static/cache/recommendation_cache），target 预置重复内容与不同 ID 标签。
      3. 建立 pairing 后在 target 执行 directional pull。
      4. 校验 target 元数据引用映射、冲突标签别名、特殊标签稳定性、页数差异场景（源 2 话/目标 1 话）与资产哈希一致性。
      5. 再执行一次 pull，校验幂等（无新增内容/无新文件传输）。
    - 预期结果:
      1. 新内容 tag_ids/list_ids 全部映射到 target 既有语义 ID，不出现 source raw ID。
      2. 同 ID 冲突标签会被分配新别名 ID，且内容引用正确回填。
      3. 特殊标签“最近导入”在 comic/video 两个 content_type 上都保持可更新状态，不产生重复语义标签。
      4. 每个新增传输文件在 target 存在且 sha256 与 source 一致。
      5. 二次 pull 不再新增数据或传输文件。
    - 历史变更:
      - 2026-03-23: 初始创建，覆盖增量同步 tag/list 映射回归场景。
    """
    source = dual_sync_runtime["source"]
    target = dual_sync_runtime["target"]
    source_base = source["base_url"]
    target_base = target["base_url"]
    source_data: Path = source["data_dir"]
    target_data: Path = target["data_dir"]

    source_tags_path = source["meta_dir"] / "tags_database.json"
    source_lists_path = source["meta_dir"] / "lists_database.json"
    source_comics_path = source["meta_dir"] / "comics_database.json"
    source_videos_path = source["meta_dir"] / "videos_database.json"

    target_tags_path = target["meta_dir"] / "tags_database.json"
    target_lists_path = target["meta_dir"] / "lists_database.json"
    target_comics_path = target["meta_dir"] / "comics_database.json"
    target_videos_path = target["meta_dir"] / "videos_database.json"

    now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

    source_tags = load_json(source_tags_path)
    target_tags = load_json(target_tags_path)

    _upsert_by_id(target_tags.setdefault("tags", []), {"id": "tag_002", "name": "中出", "content_type": "comic", "create_time": now})
    _upsert_by_id(target_tags.setdefault("tags", []), {"id": "tag_004", "name": "深喉", "content_type": "comic", "create_time": now})
    _upsert_by_id(target_tags.setdefault("tags", []), {"id": "tag_recent_local", "name": "最近导入", "content_type": "comic", "create_time": now})
    _upsert_by_id(target_tags.setdefault("tags", []), {"id": "tag_video_recent_local", "name": "最近导入", "content_type": "video", "create_time": now})
    _upsert_by_id(target_tags.setdefault("tags", []), {"id": "tag_collision", "name": "冲突目标", "content_type": "comic", "create_time": now})
    target_tags["last_updated"] = datetime.now().strftime("%Y-%m-%d")
    save_json(target_tags_path, target_tags)

    _upsert_by_id(source_tags.setdefault("tags", []), {"id": "tag_019", "name": "中出", "content_type": "comic", "create_time": now})
    _upsert_by_id(source_tags.setdefault("tags", []), {"id": "tag_034", "name": "深喉", "content_type": "comic", "create_time": now})
    _upsert_by_id(source_tags.setdefault("tags", []), {"id": "tag_recent_import", "name": "最近导入", "content_type": "comic", "create_time": now})
    _upsert_by_id(source_tags.setdefault("tags", []), {"id": "tag_video_recent_import", "name": "最近导入", "content_type": "video", "create_time": now})
    _upsert_by_id(source_tags.setdefault("tags", []), {"id": "tag_collision", "name": "冲突源", "content_type": "comic", "create_time": now})
    source_tags["last_updated"] = datetime.now().strftime("%Y-%m-%d")
    save_json(source_tags_path, source_tags)

    source_lists = load_json(source_lists_path)
    target_lists = load_json(target_lists_path)
    _upsert_by_id(target_lists.setdefault("lists", []), {"id": "list_002", "name": "同步测试清单", "content_type": "comic", "is_default": False, "create_time": now})
    _upsert_by_id(source_lists.setdefault("lists", []), {"id": "list_019", "name": "同步测试清单", "content_type": "comic", "is_default": False, "create_time": now})
    source_lists["last_updated"] = datetime.now().strftime("%Y-%m-%d")
    target_lists["last_updated"] = datetime.now().strftime("%Y-%m-%d")
    save_json(source_lists_path, source_lists)
    save_json(target_lists_path, target_lists)

    source_comics = load_json(source_comics_path)
    target_comics = load_json(target_comics_path)

    _upsert_by_id(
        target_comics.setdefault("comics", []),
        {
            "id": "JM1406651",
            "title": "Target Existing Comic",
            "title_jp": "",
            "author": "Target Seed",
            "desc": "Target already has this comic with local tag IDs.",
            "cover_path": "/static/cover/JM/1406651.jpg",
            "total_page": 2,
            "current_page": 1,
            "score": 8.2,
            "tag_ids": ["tag_002", "tag_004"],
            "list_ids": ["list_002"],
            "create_time": now,
            "last_read_time": now,
            "is_deleted": False,
        },
    )
    _upsert_by_id(
        source_comics.setdefault("comics", []),
        {
            "id": "JM1406651",
            "title": "Source Existing Comic",
            "title_jp": "",
            "author": "Source Seed",
            "desc": "Source has same comic ID but different tag/list IDs.",
            "cover_path": "/static/cover/JM/1406651.jpg",
            "total_page": 2,
            "current_page": 1,
            "score": 9.1,
            "tag_ids": ["tag_019", "tag_034"],
            "list_ids": ["list_019"],
            "create_time": now,
            "last_read_time": now,
            "is_deleted": False,
        },
    )

    _upsert_by_id(
        source_comics.setdefault("comics", []),
        {
            "id": "PK698e14e13951674692432507",
            "title": "Delta New Comic",
            "title_jp": "",
            "author": "Sync Source",
            "desc": "Validate tag/list remap and collision handling.",
            "cover_path": "/static/cover/PK/698e14e13951674692432507.jpg",
            "total_page": 2,
            "current_page": 1,
            "score": 9.4,
            "tag_ids": ["tag_019", "tag_034", "tag_recent_import", "tag_collision"],
            "list_ids": ["list_019"],
            "create_time": now,
            "last_read_time": now,
            "is_deleted": False,
        },
    )

    _upsert_by_id(
        target_comics.setdefault("comics", []),
        {
            "id": "JM_SYNC_PAGE_DIFF",
            "title": "Target One Page",
            "title_jp": "",
            "author": "Target Seed",
            "desc": "Target keeps metadata while receiving missing assets.",
            "cover_path": "/static/cover/JM/SYNC_PAGE_DIFF.jpg",
            "total_page": 1,
            "current_page": 1,
            "score": 7.1,
            "tag_ids": ["tag_action"],
            "list_ids": [],
            "create_time": now,
            "last_read_time": now,
            "is_deleted": False,
        },
    )
    _upsert_by_id(
        source_comics.setdefault("comics", []),
        {
            "id": "JM_SYNC_PAGE_DIFF",
            "title": "Source Two Pages",
            "title_jp": "",
            "author": "Source Seed",
            "desc": "Source has 2 pages while target has 1 page.",
            "cover_path": "/static/cover/JM/SYNC_PAGE_DIFF.jpg",
            "total_page": 2,
            "current_page": 1,
            "score": 8.8,
            "tag_ids": ["tag_019"],
            "list_ids": [],
            "create_time": now,
            "last_read_time": now,
            "is_deleted": False,
        },
    )

    _update_total(source_comics, "comics", "total_comics")
    _update_total(target_comics, "comics", "total_comics")
    save_json(source_comics_path, source_comics)
    save_json(target_comics_path, target_comics)

    source_videos = load_json(source_videos_path)
    _upsert_by_id(
        source_videos.setdefault("videos", []),
        {
            "id": "JAVDBABF311",
            "code": "ABF-311",
            "title": "Sync Video ABF-311",
            "creator": "Sync Creator",
            "actors": ["Sync Actor"],
            "cover_path": "/static/cover/JAVDB/ABF-311.jpg",
            "thumbnail_images": [],
            "video_url": "/video/JAVDB/ABF-311/preview.mp4",
            "score": 8.9,
            "tag_ids": ["tag_video_recent_import"],
            "list_ids": [],
            "create_time": now,
            "last_read_time": now,
            "is_deleted": False,
        },
    )
    _update_total(source_videos, "videos", "total_videos")
    save_json(source_videos_path, source_videos)

    expected_missing_hashes: dict[str, str] = {}

    _write_binary(source_data, "comic/PK/698e14e13951674692432507/001.png", b"source-new-comic-page-1")
    _write_binary(source_data, "comic/PK/698e14e13951674692432507/002.png", b"source-new-comic-page-2")
    _write_binary(source_data, "static/cover/PK/698e14e13951674692432507.jpg", b"source-new-comic-cover")
    _write_binary(source_data, "video/JAVDB/ABF-311/preview.mp4", b"source-video-preview")
    _write_binary(source_data, "static/cover/JAVDB/ABF-311.jpg", b"source-video-cover")
    _write_binary(source_data, "cache/comic/sync_guard_from_source.bin", b"source-cache-payload")
    _write_binary(source_data, "recommendation_cache/comic/PK/698e14e13951674692432507/thumb_001.png", b"source-rec-cache-thumb")
    _write_binary(source_data, "comic/JM/SYNC_PAGE_DIFF/001.png", b"source-page-diff-001")
    _write_binary(source_data, "comic/JM/SYNC_PAGE_DIFF/002.png", b"source-page-diff-002")

    _write_binary(target_data, "comic/JM/SYNC_PAGE_DIFF/001.png", b"target-page-diff-001")

    expected_missing_paths = [
        "comic/PK/698e14e13951674692432507/001.png",
        "comic/PK/698e14e13951674692432507/002.png",
        "static/cover/PK/698e14e13951674692432507.jpg",
        "video/JAVDB/ABF-311/preview.mp4",
        "static/cover/JAVDB/ABF-311.jpg",
        "cache/comic/sync_guard_from_source.bin",
        "recommendation_cache/comic/PK/698e14e13951674692432507/thumb_001.png",
        "comic/JM/SYNC_PAGE_DIFF/002.png",
    ]
    for rel in expected_missing_paths:
        expected_missing_hashes[rel] = _sha256(source_data / rel.replace("/", os.sep))
        assert not (target_data / rel.replace("/", os.sep)).exists()

    invite_data = _request_ok(
        "POST",
        f"{source_base}/api/v1/sync/pairing/invite",
        json_body={"ttl_minutes": 10},
        timeout=10,
    )
    pairing_code = str(invite_data.get("pairing_code", "")).strip()
    assert pairing_code

    connect_data = _request_ok(
        "POST",
        f"{target_base}/api/v1/sync/pairing/connect",
        json_body={
            "remote_base_url": source_base,
            "pairing_code": pairing_code,
            "requester_base_url": target_base,
        },
        timeout=20,
    )
    peer_id = str(connect_data.get("peer_id", "")).strip()
    assert peer_id

    pull_data = _request_ok(
        "POST",
        f"{target_base}/api/v1/sync/directional/pull",
        json_body={"peer_id": peer_id},
        timeout=180,
    )
    assert pull_data.get("status") == "completed"
    assert pull_data.get("direction") == "pull"
    assert pull_data.get("peer_id") == peer_id
    asset_sync = pull_data.get("asset_sync", {})
    assert int(asset_sync.get("file_count", 0)) >= len(expected_missing_paths)

    target_tags_after = load_json(target_tags_path).get("tags", [])
    target_lists_after = load_json(target_lists_path).get("lists", [])
    target_comics_after = load_json(target_comics_path).get("comics", [])
    target_videos_after = load_json(target_videos_path).get("videos", [])

    new_comic = find_by_id(target_comics_after, "PK698e14e13951674692432507")
    assert new_comic is not None
    assert "tag_002" in (new_comic.get("tag_ids") or [])
    assert "tag_004" in (new_comic.get("tag_ids") or [])
    assert "tag_recent_local" in (new_comic.get("tag_ids") or [])
    assert "tag_019" not in (new_comic.get("tag_ids") or [])
    assert "tag_034" not in (new_comic.get("tag_ids") or [])
    assert "tag_recent_import" not in (new_comic.get("tag_ids") or [])
    assert "list_002" in (new_comic.get("list_ids") or [])
    assert "list_019" not in (new_comic.get("list_ids") or [])

    conflict_target_tag = find_by_id(target_tags_after, "tag_collision")
    assert conflict_target_tag is not None
    assert conflict_target_tag.get("name") == "冲突目标"
    conflict_source_tag = next(
        (
            item for item in target_tags_after
            if item.get("name") == "冲突源"
            and str(item.get("content_type", "comic")).strip().lower() == "comic"
        ),
        None,
    )
    assert conflict_source_tag is not None
    assert conflict_source_tag.get("id") != "tag_collision"
    assert conflict_source_tag.get("id") in (new_comic.get("tag_ids") or [])

    comic_recent_tags = [
        item for item in target_tags_after
        if item.get("name") == "最近导入" and str(item.get("content_type", "comic")).strip().lower() == "comic"
    ]
    video_recent_tags = [
        item for item in target_tags_after
        if item.get("name") == "最近导入" and str(item.get("content_type", "comic")).strip().lower() == "video"
    ]
    assert any(item.get("id") == "tag_recent_local" for item in comic_recent_tags)
    assert any(item.get("id") == "tag_video_recent_local" for item in video_recent_tags)
    assert find_by_id(target_tags_after, "tag_recent_import") is None
    assert find_by_id(target_tags_after, "tag_video_recent_import") is None

    synced_list = find_by_id(target_lists_after, "list_002")
    assert synced_list is not None
    assert synced_list.get("name") == "同步测试清单"
    assert find_by_id(target_lists_after, "list_019") is None

    new_video = find_by_id(target_videos_after, "JAVDBABF311")
    assert new_video is not None
    assert "tag_video_recent_local" in (new_video.get("tag_ids") or [])
    assert "tag_video_recent_import" not in (new_video.get("tag_ids") or [])

    page_diff_comic = find_by_id(target_comics_after, "JM_SYNC_PAGE_DIFF")
    assert page_diff_comic is not None
    assert int(page_diff_comic.get("total_page", 0)) == 1
    assert (target_data / "comic" / "JM" / "SYNC_PAGE_DIFF" / "002.png").exists()
    assert (target_data / "comic" / "JM" / "SYNC_PAGE_DIFF" / "001.png").read_bytes() == b"target-page-diff-001"

    for rel, expected_hash in expected_missing_hashes.items():
        target_file = target_data / rel.replace("/", os.sep)
        assert target_file.exists(), f"missing transferred file: {rel}"
        assert _sha256(target_file) == expected_hash, f"hash mismatch for transferred file: {rel}"

    pull_again_data = _request_ok(
        "POST",
        f"{target_base}/api/v1/sync/directional/pull",
        json_body={"peer_id": peer_id},
        timeout=180,
    )
    assert pull_again_data.get("status") == "completed"
    local_apply_again = pull_again_data.get("local_apply", {})
    assert int(local_apply_again.get("total_added", 0)) == 0
    assert int(pull_again_data.get("asset_sync", {}).get("file_count", 0)) == 0

    source_zip_dir = source_data / "cache" / "sync_assets"
    target_zip_dir = target_data / "cache" / "sync_assets"
    if source_zip_dir.is_dir():
        assert _wait_for_no_zip_files(source_zip_dir), f"source still has temp zip files: {list(source_zip_dir.glob('*.zip'))}"
    if target_zip_dir.is_dir():
        assert _wait_for_no_zip_files(target_zip_dir), f"target still has temp zip files: {list(target_zip_dir.glob('*.zip'))}"


def _wait_for_directional_task(base_url: str, task_id: str, timeout_seconds: int = 180) -> dict:
    deadline = time.time() + timeout_seconds
    last_payload: dict = {}
    while time.time() < deadline:
        payload = _request_ok("GET", f"{base_url}/api/v1/sync/directional/task/{task_id}", timeout=10)
        last_payload = payload if isinstance(payload, dict) else {}
        status = str(last_payload.get("status", "")).strip().lower()
        if status in {"completed", "failed"}:
            return last_payload
        time.sleep(0.5)
    raise TimeoutError(f"directional task timeout: {task_id}, last={last_payload}")


@pytest.mark.integration
def test_sync_session_meta_only_layer_exports_only_meta_package(single_sync_runtime):
    """
    用例描述:
    - 用例目的: 看护 session 分层开关在 `layers=["meta"]` 时不会误打包 media/cache/cover。
    - 测试步骤:
      1. 调用 /api/v1/sync/session/start，传入 layers=["meta"] 且 include_* 全部 true。
      2. 校验 packages 只有 meta 包，并下载检查 zip 条目均在 meta_data/ 下。
      3. 调用 /api/v1/sync/session/finish，校验导出目录被清理。
    - 预期结果:
      1. 仅返回 1 个 meta 类型包。
      2. meta.zip 内条目全部以 meta_data/ 开头。
      3. finish 后会话导出目录不存在。
    - 历史变更:
      - 2026-03-24: 初始创建，覆盖分层打包开关守卫场景。
    """
    base_url = single_sync_runtime["base_url"]
    data_dir: Path = single_sync_runtime["data_dir"]

    session_data = _request_ok(
        "POST",
        f"{base_url}/api/v1/sync/session/start",
        json_body={
            "layers": ["meta"],
            "include_media": True,
            "include_cache": True,
            "include_cover": True,
            "include_meta": True,
        },
        timeout=40,
    )
    session_id = str(session_data.get("session_id", "")).strip()
    assert session_id

    packages = session_data.get("packages", [])
    assert isinstance(packages, list)
    assert len(packages) == 1
    only = packages[0]
    assert str(only.get("type") or only.get("kind") or "").strip() == "meta"

    package_name = str(only.get("name") or only.get("file") or "").strip()
    assert package_name
    download_resp = requests.get(
        f"{base_url}/api/v1/sync/download/{session_id}/{package_name}",
        timeout=40,
    )
    assert download_resp.status_code == 200

    tmp_zip = data_dir / "cache" / f"sync_meta_only_{uuid4().hex[:8]}.zip"
    try:
        tmp_zip.write_bytes(download_resp.content)
        with zipfile.ZipFile(tmp_zip, "r") as zip_fp:
            entries = [item for item in zip_fp.namelist() if item]
            assert entries
            assert all(item.startswith("meta_data/") for item in entries)
    finally:
        if tmp_zip.exists():
            tmp_zip.unlink()

    finish_data = _request_ok(
        "POST",
        f"{base_url}/api/v1/sync/session/finish",
        json_body={"session_id": session_id, "status": "completed"},
        timeout=20,
    )
    assert finish_data.get("session_id") == session_id
    assert bool(finish_data.get("exports_cleaned")) is True
    assert not (data_dir / "cache" / "sync_exports" / session_id).exists()


@pytest.mark.integration
def test_sync_api_guards_return_expected_codes(single_sync_runtime):
    """
    用例描述:
    - 用例目的: 看护同步 API 的参数校验和 token 鉴权守卫，避免无效请求误入业务主流程。
    - 测试步骤:
      1. 调用 finish_session 且缺少 session_id。
      2. 调用 directional pull 且缺少 peer_id。
      3. 调用 directional inventory/assets inventory 且缺少或错误 token。
      4. 调用 pairing connect 且缺少必要参数。
    - 预期结果:
      1. 返回业务错误码 400/401，且错误信息明确。
      2. 不会返回 code=200 的成功业务结果。
    - 历史变更:
      - 2026-03-24: 初始创建，覆盖同步入口守卫。
    """
    base_url = single_sync_runtime["base_url"]

    finish_resp = requests.post(
        f"{base_url}/api/v1/sync/session/finish",
        json={},
        timeout=10,
    )
    assert finish_resp.status_code == 200
    finish_payload = finish_resp.json()
    assert finish_payload.get("code") == 400
    assert "session_id is required" in str(finish_payload.get("msg", ""))

    pull_resp = requests.post(
        f"{base_url}/api/v1/sync/directional/pull",
        json={},
        timeout=10,
    )
    assert pull_resp.status_code == 200
    pull_payload = pull_resp.json()
    assert pull_payload.get("code") == 400
    assert "peer_id is required" in str(pull_payload.get("msg", ""))

    inv_resp = requests.get(
        f"{base_url}/api/v1/sync/directional/inventory",
        timeout=10,
    )
    assert inv_resp.status_code == 200
    inv_payload = inv_resp.json()
    assert inv_payload.get("code") == 401
    assert "invalid sync token" in str(inv_payload.get("msg", ""))

    assets_inv_resp = requests.get(
        f"{base_url}/api/v1/sync/directional/assets/inventory",
        headers={"X-Sync-Token": "invalid-token"},
        timeout=10,
    )
    assert assets_inv_resp.status_code == 200
    assets_inv_payload = assets_inv_resp.json()
    assert assets_inv_payload.get("code") == 401
    assert "invalid sync token" in str(assets_inv_payload.get("msg", ""))

    connect_resp = requests.post(
        f"{base_url}/api/v1/sync/pairing/connect",
        json={"remote_base_url": "http://127.0.0.1:1"},
        timeout=10,
    )
    assert connect_resp.status_code == 200
    connect_payload = connect_resp.json()
    assert connect_payload.get("code") == 400
    assert "pairing_code is required" in str(connect_payload.get("msg", ""))


@pytest.mark.integration
def test_directional_push_task_flow_syncs_data_and_assets(dual_sync_runtime):
    """
    用例描述:
    - 用例目的: 看护 directional push 与异步 task 接口主链路，确保 target->source 的数据和资产同步可用。
    - 测试步骤:
      1. 在 target 注入唯一 tag/list/comic 和真实资源文件。
      2. source 发邀请码，target connect 后先调用 preview(push)。
      3. target 调用 directional/task/start(direction=push) 并轮询 task 状态至完成。
      4. 校验 source 侧元数据与文件均已同步，再执行一次 push 校验 no_change 幂等。
    - 预期结果:
      1. task 最终 completed，包含 push 结果。
      2. source 出现新增 comic/tag/list，且 comic 引用了正确 tag/list。
      3. source 新增资源文件存在且内容哈希与 target 一致。
      4. 二次 push 返回 no_change 且 asset file_count=0。
    - 历史变更:
      - 2026-03-24: 初始创建，补齐 push + directional task 覆盖。
    """
    source = dual_sync_runtime["source"]
    target = dual_sync_runtime["target"]
    source_base = source["base_url"]
    target_base = target["base_url"]
    source_data: Path = source["data_dir"]
    target_data: Path = target["data_dir"]

    source_tags_path = source["meta_dir"] / "tags_database.json"
    source_lists_path = source["meta_dir"] / "lists_database.json"
    source_comics_path = source["meta_dir"] / "comics_database.json"
    target_tags_path = target["meta_dir"] / "tags_database.json"
    target_lists_path = target["meta_dir"] / "lists_database.json"
    target_comics_path = target["meta_dir"] / "comics_database.json"

    now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    suffix = uuid4().hex[:8]
    comic_id = f"JM_PUSH_{suffix.upper()}"
    tag_id = f"tag_push_{suffix}"
    list_id = f"list_push_{suffix}"
    tag_name = f"sync-push-tag-{suffix}"
    list_name = f"sync-push-list-{suffix}"

    target_tags = load_json(target_tags_path)
    target_lists = load_json(target_lists_path)
    target_comics = load_json(target_comics_path)
    _upsert_by_id(
        target_tags.setdefault("tags", []),
        {"id": tag_id, "name": tag_name, "content_type": "comic", "create_time": now},
    )
    _upsert_by_id(
        target_lists.setdefault("lists", []),
        {"id": list_id, "name": list_name, "content_type": "comic", "is_default": False, "create_time": now},
    )
    _upsert_by_id(
        target_comics.setdefault("comics", []),
        {
            "id": comic_id,
            "title": f"Push Comic {suffix}",
            "title_jp": "",
            "author": "Push Tester",
            "desc": "Directional push integration guard.",
            "cover_path": f"/static/cover/JM/{comic_id}.jpg",
            "total_page": 1,
            "current_page": 1,
            "score": 8.7,
            "tag_ids": [tag_id],
            "list_ids": [list_id],
            "create_time": now,
            "last_read_time": now,
            "is_deleted": False,
        },
    )
    _update_total(target_comics, "comics", "total_comics")
    target_tags["last_updated"] = datetime.now().strftime("%Y-%m-%d")
    target_lists["last_updated"] = datetime.now().strftime("%Y-%m-%d")
    save_json(target_tags_path, target_tags)
    save_json(target_lists_path, target_lists)
    save_json(target_comics_path, target_comics)

    page_rel = f"comic/JM/{comic_id}/001.png"
    cover_rel = f"static/cover/JM/{comic_id}.jpg"
    _write_binary(target_data, page_rel, f"push-page-{suffix}".encode("utf-8"))
    _write_binary(target_data, cover_rel, f"push-cover-{suffix}".encode("utf-8"))
    expected_hashes = {
        page_rel: _sha256(target_data / page_rel.replace("/", os.sep)),
        cover_rel: _sha256(target_data / cover_rel.replace("/", os.sep)),
    }
    assert not (source_data / page_rel.replace("/", os.sep)).exists()
    assert not (source_data / cover_rel.replace("/", os.sep)).exists()

    invite_data = _request_ok(
        "POST",
        f"{source_base}/api/v1/sync/pairing/invite",
        json_body={"ttl_minutes": 10},
        timeout=10,
    )
    pairing_code = str(invite_data.get("pairing_code", "")).strip()
    assert pairing_code

    connect_data = _request_ok(
        "POST",
        f"{target_base}/api/v1/sync/pairing/connect",
        json_body={
            "remote_base_url": source_base,
            "pairing_code": pairing_code,
            "requester_base_url": target_base,
        },
        timeout=20,
    )
    peer_id = str(connect_data.get("peer_id", "")).strip()
    assert peer_id

    preview_data = _request_ok(
        "POST",
        f"{target_base}/api/v1/sync/directional/preview",
        json_body={"peer_id": peer_id, "direction": "push"},
        timeout=20,
    )
    assert preview_data.get("direction") == "push"
    data_sync = preview_data.get("data_sync", {})
    asset_sync = preview_data.get("asset_sync", {})
    assert int(data_sync.get("total_records", 0)) > 0
    assert int(asset_sync.get("file_count", 0)) >= 2

    task_data = _request_ok(
        "POST",
        f"{target_base}/api/v1/sync/directional/task/start",
        json_body={"peer_id": peer_id, "direction": "push"},
        timeout=20,
    )
    task_id = str(task_data.get("task_id", "")).strip()
    assert task_id
    finished_task = _wait_for_directional_task(target_base, task_id, timeout_seconds=180)
    assert finished_task.get("status") == "completed"
    assert finished_task.get("progress") == 100
    result = finished_task.get("result", {})
    assert isinstance(result, dict)
    assert result.get("status") == "completed"
    assert result.get("direction") == "push"

    source_comics = load_json(source_comics_path).get("comics", [])
    source_tags = load_json(source_tags_path).get("tags", [])
    source_lists = load_json(source_lists_path).get("lists", [])
    pushed_comic = find_by_id(source_comics, comic_id)
    assert pushed_comic is not None

    pushed_tag = next((item for item in source_tags if item.get("name") == tag_name), None)
    pushed_list = next((item for item in source_lists if item.get("name") == list_name), None)
    assert pushed_tag is not None
    assert pushed_list is not None
    assert pushed_tag.get("id") in (pushed_comic.get("tag_ids") or [])
    assert pushed_list.get("id") in (pushed_comic.get("list_ids") or [])

    for rel, expected_hash in expected_hashes.items():
        source_file = source_data / rel.replace("/", os.sep)
        assert source_file.exists(), f"missing pushed file: {rel}"
        assert _sha256(source_file) == expected_hash, f"hash mismatch for pushed file: {rel}"

    push_again = _request_ok(
        "POST",
        f"{target_base}/api/v1/sync/directional/push",
        json_body={"peer_id": peer_id},
        timeout=180,
    )
    assert push_again.get("status") == "completed"
    remote_apply_again = push_again.get("remote_apply", {})
    assert int(remote_apply_again.get("total_added", 0)) == 0
    assert int(remote_apply_again.get("total_updated", 0)) == 0
    assert int(push_again.get("asset_sync", {}).get("file_count", 0)) == 0
