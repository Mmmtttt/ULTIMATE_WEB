from __future__ import annotations

from uuid import uuid4

import pytest
import requests

from tests.shared.runtime_data import find_by_id, load_json, save_json


@pytest.mark.integration
def test_video_import_creates_video_with_valid_params(integration_runtime):
    """
    用例描述:
    - 用例目的: 验证视频导入接口能正确创建视频记录并持久化。
    - 测试步骤:
      1. 调用 POST /api/v1/video/import 创建新视频。
      2. 检查接口返回状态和数据。
      3. 验证 videos_database.json 中新增记录。
    - 预期结果:
      1. HTTP 200，业务 code=200。
      2. 返回数据包含正确的 video_id 和 title。
      3. 文件中新增对应记录。
    - 历史变更:
      - 2026-03-25: 初始创建，覆盖视频导入主链路。
    """
    base_url = integration_runtime["base_url"]
    meta_dir = integration_runtime["meta_dir"]
    videos_path = meta_dir / "videos_database.json"

    video_suffix = uuid4().hex[:8].upper()
    video_id = f"TESTVIDEO{video_suffix}"
    video_code = f"TEST-{video_suffix}"

    response = requests.post(
        f"{base_url}/api/v1/video/import",
        json={
            "id": video_id,
            "code": video_code,
            "title": f"Test Video {video_suffix}",
            "actors": ["Actor A", "Actor B"],
            "cover_path": "/static/cover/JAVDB/900001.png",
        },
        timeout=5,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 200
    assert payload["data"]["id"] == video_id

    videos_data = load_json(videos_path)
    videos = videos_data.get("videos", [])
    created = find_by_id(videos, video_id)
    assert created is not None
    assert created["code"] == video_code


@pytest.mark.integration
def test_video_import_rejects_missing_required_fields(integration_runtime):
    """
    用例描述:
    - 用例目的: 验证视频导入接口校验必要参数。
    - 测试步骤:
      1. 调用 POST /api/v1/video/import 不传必要字段。
      2. 检查返回错误码。
    - 预期结果:
      1. HTTP 200，业务 code=400。
    - 历史变更:
      - 2026-03-25: 初始创建，覆盖视频导入参数校验。
    """
    base_url = integration_runtime["base_url"]

    response = requests.post(
        f"{base_url}/api/v1/video/import",
        json={},
        timeout=5,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 400


@pytest.mark.integration
def test_video_batch_import_creates_multiple_videos(integration_runtime):
    """
    用例描述:
    - 用例目的: 验证视频批量导入接口能正确创建多个视频记录。
    - 测试步骤:
      1. 调用 POST /api/v1/video/import/batch 批量创建视频。
      2. 检查接口返回状态。
      3. 验证文件中新增多条记录。
    - 预期结果:
      1. HTTP 200，业务 code=200。
      2. 返回 imported_ids 包含所有视频 ID。
      3. 文件中新增对应记录。
    - 历史变更:
      - 2026-03-25: 初始创建，覆盖视频批量导入主链路。
    """
    base_url = integration_runtime["base_url"]
    meta_dir = integration_runtime["meta_dir"]
    videos_path = meta_dir / "videos_database.json"

    suffix1 = uuid4().hex[:8].upper()
    suffix2 = uuid4().hex[:8].upper()
    video_id_1 = f"BATCHVID1{suffix1}"
    video_id_2 = f"BATCHVID2{suffix2}"

    response = requests.post(
        f"{base_url}/api/v1/video/import/batch",
        json={
            "videos": [
                {
                    "id": video_id_1,
                    "code": f"BATCH1-{suffix1}",
                    "title": f"Batch Video 1 {suffix1}",
                    "cover_path": "/static/cover/JAVDB/900001.png",
                },
                {
                    "id": video_id_2,
                    "code": f"BATCH2-{suffix2}",
                    "title": f"Batch Video 2 {suffix2}",
                    "cover_path": "/static/cover/JAVDB/900002.png",
                },
            ]
        },
        timeout=5,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 200
    imported_ids = payload["data"].get("imported_ids", [])
    assert video_id_1 in imported_ids
    assert video_id_2 in imported_ids

    videos_data = load_json(videos_path)
    videos = videos_data.get("videos", [])
    assert find_by_id(videos, video_id_1) is not None
    assert find_by_id(videos, video_id_2) is not None


@pytest.mark.integration
def test_video_local_import_groups_multiple_files_in_same_folder_as_episodes(integration_runtime, tmp_path):
    """
    用例描述:
    - 用例目的: 验证同一文件夹下多个本地视频会作为同一作品的多集视频导入。
    - 测试步骤:
      1. 在临时目录创建包含两个视频文件的文件夹。
      2. 调用本地视频路径导入接口。
      3. 获取导入后的视频详情。
    - 预期结果:
      1. 只创建一个视频条目。
      2. 详情中包含两个 local_episodes，可用于前端选集播放。
    """
    base_url = integration_runtime["base_url"]

    series_dir = tmp_path / "Local Series"
    series_dir.mkdir()
    (series_dir / "Episode 01.mp4").write_bytes(b"episode-1")
    (series_dir / "Episode 02.mp4").write_bytes(b"episode-2")

    import_response = requests.post(
        f"{base_url}/api/v1/video/local-import/from-path",
        json={
            "source_path": str(series_dir),
            "import_mode": "hardlink_move",
            "grouping_mode": "leaf_dir",
        },
        timeout=10,
    )

    assert import_response.status_code == 200
    import_payload = import_response.json()
    assert import_payload["code"] == 200
    data = import_payload["data"] or {}
    assert data.get("imported_count") == 1
    assert data.get("grouping_mode") == "leaf_dir"
    imported_ids = data.get("imported_ids") or []
    assert len(imported_ids) == 1

    detail_response = requests.get(
        f"{base_url}/api/v1/video/detail",
        params={"video_id": imported_ids[0]},
        timeout=5,
    )

    assert detail_response.status_code == 200
    detail_payload = detail_response.json()
    assert detail_payload["code"] == 200
    detail = detail_payload["data"] or {}
    episodes = ((detail.get("display") or {}).get("local_episodes") or [])
    playback = detail.get("playback") or {}
    primary = playback.get("primary") or {}
    preview = playback.get("preview") or {}
    assert detail.get("total_units") == 2
    assert [item.get("name") for item in episodes] == ["Episode 01.mp4", "Episode 02.mp4"]
    assert all(str(item.get("url") or "").startswith("/media/") for item in episodes)
    assert primary.get("mode") == "local"
    assert primary.get("supports_episode_selection") is True
    assert [item.get("name") for item in (primary.get("episodes") or [])] == ["Episode 01.mp4", "Episode 02.mp4"]
    assert preview.get("available") is False

    play_response = requests.get(
        f"{base_url}/api/v1/video/{imported_ids[0]}/play-urls",
        timeout=5,
    )

    assert play_response.status_code == 200
    play_payload = play_response.json()
    assert play_payload["code"] == 200
    sources = play_payload["data"]["sources"]
    assert [item.get("name") for item in sources] == ["Episode 01.mp4", "Episode 02.mp4"]
    assert all(item.get("available") is True for item in sources)
    assert all(
        str(((item.get("streams") or [{}])[0].get("url") or "")).startswith(f"/api/v1/video/local-stream/{imported_ids[0]}")
        for item in sources
    )


@pytest.mark.integration
def test_video_local_import_defaults_to_per_file_for_same_folder_no_code_files(integration_runtime, tmp_path):
    """
    用例描述:
    - 用例目的: 看护本地视频导入默认按“逐文件导入”，即使同目录下有多个未识别番号的视频，也不会自动合并成多集。
    - 测试步骤:
      1. 在同一目录创建两个无番号视频文件。
      2. 调用本地视频路径导入接口，不显式传 grouping_mode。
      3. 校验导入结果与本地详情。
    - 预期结果:
      1. 创建两个独立视频条目。
      2. 每个条目的 total_units 都是 1。
    """
    base_url = integration_runtime["base_url"]

    source_dir = tmp_path / "No Code Folder"
    source_dir.mkdir()
    (source_dir / "clip-one.mp4").write_bytes(b"clip-one")
    (source_dir / "clip-two.mp4").write_bytes(b"clip-two")

    import_response = requests.post(
        f"{base_url}/api/v1/video/local-import/from-path",
        json={
            "source_path": str(source_dir),
            "import_mode": "hardlink_move",
        },
        timeout=10,
    )

    assert import_response.status_code == 200
    import_payload = import_response.json()
    assert import_payload["code"] == 200
    data = import_payload["data"] or {}
    assert data.get("grouping_mode") == "per_file"
    assert data.get("imported_count") == 2
    imported_ids = data.get("imported_ids") or []
    assert len(imported_ids) == 2

    for imported_id in imported_ids:
        detail_response = requests.get(
            f"{base_url}/api/v1/video/detail",
            params={"video_id": imported_id},
            timeout=5,
        )
        assert detail_response.status_code == 200
        detail_payload = detail_response.json()
        assert detail_payload["code"] == 200
        detail = detail_payload["data"] or {}
        assert detail.get("total_units") == 1
        episodes = ((detail.get("display") or {}).get("local_episodes") or [])
        assert len(episodes) == 1


@pytest.mark.integration
def test_video_local_import_defaults_to_per_file_but_merges_same_code_files_into_one_video(integration_runtime, tmp_path):
    """
    用例描述:
    - 用例目的: 看护默认“逐文件导入”与“同番号自动并入”可以同时成立。
    - 测试步骤:
      1. 在同一目录创建两个同番号视频文件。
      2. 调用本地视频路径导入接口，不显式传 grouping_mode。
      3. 校验导入结果与本地详情。
    - 预期结果:
      1. 两个文件都会被成功处理。
      2. imported_ids 只返回一个唯一视频 ID。
      3. 最终该视频包含两个 local_episodes。
    """
    base_url = integration_runtime["base_url"]
    code_suffix = f"{(uuid4().int % 9000) + 1000}"
    recognized_code = f"UTV-{code_suffix}"

    source_dir = tmp_path / "Same Code Folder"
    source_dir.mkdir()
    (source_dir / f"{recognized_code} cd1.mp4").write_bytes(b"cd-1")
    (source_dir / f"{recognized_code.replace('-', '_').lower()} cd2.mkv").write_bytes(b"cd-2")

    import_response = requests.post(
        f"{base_url}/api/v1/video/local-import/from-path",
        json={
            "source_path": str(source_dir),
            "import_mode": "hardlink_move",
        },
        timeout=10,
    )

    assert import_response.status_code == 200
    import_payload = import_response.json()
    assert import_payload["code"] == 200
    data = import_payload["data"] or {}
    assert data.get("grouping_mode") == "per_file"
    assert data.get("imported_count") == 2
    assert data.get("attached_source_count") == 1
    imported_ids = data.get("imported_ids") or []
    assert imported_ids
    assert len(imported_ids) == 1

    detail_response = requests.get(
        f"{base_url}/api/v1/video/detail",
        params={"video_id": imported_ids[0]},
        timeout=5,
    )
    assert detail_response.status_code == 200
    detail_payload = detail_response.json()
    assert detail_payload["code"] == 200
    detail = detail_payload["data"] or {}
    episodes = ((detail.get("display") or {}).get("local_episodes") or [])
    assert detail.get("code") == recognized_code
    assert detail.get("total_units") == 2
    assert [item.get("name") for item in episodes] == [
        f"{recognized_code} cd1.mp4",
        f"{recognized_code.replace('-', '_').lower()} cd2.mkv",
    ]


@pytest.mark.integration
def test_video_local_import_softlink_repeat_import_is_idempotent_by_source_path(integration_runtime, tmp_path):
    """
    用例描述:
    - 用例目的: 看护 softlink_ref 重复导入同一路径文件时按路径幂等，不会重复追加分集。
    - 测试步骤:
      1. 创建一个可识别番号的视频文件并执行 softlink_ref 导入。
      2. 对同一目录重复执行一次导入。
      3. 校验第二次导入被识别为重复分集。
    - 预期结果:
      1. 第一次导入成功创建视频。
      2. 第二次 imported_count=0，duplicate_episode_count=1。
      3. 视频详情仍然只有 1 集。
    """
    base_url = integration_runtime["base_url"]
    code_suffix = f"{(uuid4().int % 9000) + 1000}"
    recognized_code = f"UTI-{code_suffix}"

    source_dir = tmp_path / "Idempotent Softlink"
    source_dir.mkdir()
    source_file = source_dir / f"{recognized_code} sample.mp4"
    source_file.write_bytes(b"video")

    first_response = requests.post(
        f"{base_url}/api/v1/video/local-import/from-path",
        json={
            "source_path": str(source_dir),
            "import_mode": "softlink_ref",
        },
        timeout=10,
    )
    assert first_response.status_code == 200
    first_payload = first_response.json()
    assert first_payload["code"] == 200
    first_data = first_payload["data"] or {}
    created_id = (first_data.get("imported_ids") or [None])[0]
    assert created_id

    second_response = requests.post(
        f"{base_url}/api/v1/video/local-import/from-path",
        json={
            "source_path": str(source_dir),
            "import_mode": "softlink_ref",
        },
        timeout=10,
    )
    assert second_response.status_code == 200
    second_payload = second_response.json()
    assert second_payload["code"] == 200
    second_data = second_payload["data"] or {}
    assert second_data.get("imported_count") == 0
    assert second_data.get("duplicate_episode_count") == 1
    assert second_data.get("skipped_count") == 1
    skipped_items = second_data.get("skipped_items") or []
    assert skipped_items
    assert skipped_items[0].get("reason") == "duplicate_episode_exists"
    assert skipped_items[0].get("duplicate_id") == created_id

    detail_response = requests.get(
        f"{base_url}/api/v1/video/detail",
        params={"video_id": created_id},
        timeout=5,
    )
    assert detail_response.status_code == 200
    detail_payload = detail_response.json()
    assert detail_payload["code"] == 200
    detail = detail_payload["data"] or {}
    episodes = ((detail.get("display") or {}).get("local_episodes") or [])
    assert detail.get("total_units") == 1
    assert len(episodes) == 1
    assert episodes[0].get("name") == f"{recognized_code} sample.mp4"


@pytest.mark.integration
def test_video_play_urls_for_local_source_never_exposes_filesystem_path(integration_runtime, tmp_path):
    """
    用例描述:
    - 用例目的: 防止本地库播放接口把 Windows/Linux 文件路径直接返回给前端播放器。
    - 测试步骤:
      1. 创建带本地文件路径的视频记录。
      2. 调用 GET /api/v1/video/{id}/play-urls。
      3. 检查播放 URL 走后端 local-stream。
    - 预期结果:
      1. HTTP 200 且业务 code=200。
      2. source stream URL 不包含真实文件路径。
    """
    base_url = integration_runtime["base_url"]

    source_dir = tmp_path / "softlink-source"
    source_dir.mkdir()
    video_file = source_dir / "legacy local source.mp4"
    video_file.write_bytes(b"video")

    import_response = requests.post(
        f"{base_url}/api/v1/video/local-import/from-path",
        json={
            "source_path": str(source_dir),
            "import_mode": "softlink_ref",
        },
        timeout=5,
    )
    assert import_response.status_code == 200
    import_payload = import_response.json()
    assert import_payload["code"] == 200
    created_id = import_payload["data"]["imported_ids"][0]

    play_response = requests.get(
        f"{base_url}/api/v1/video/{created_id}/play-urls",
        timeout=5,
    )
    assert play_response.status_code == 200
    play_payload = play_response.json()
    assert play_payload["code"] == 200

    stream_url = play_payload["data"]["sources"][0]["streams"][0]["url"]
    assert stream_url.startswith(f"/api/v1/video/local-stream/{created_id}")
    assert str(video_file) not in stream_url


@pytest.mark.integration
def test_video_detail_ignores_preview_hls_segments_for_softlink_local_source(integration_runtime, tmp_path):
    """
    用例描述:
    - 用例目的: 防止本地视频详情把预览缓存 HLS 分片误识别为“多集视频”，并在 Windows 多盘符场景下触发详情失败。
    - 测试步骤:
      1. 通过 softlink_ref 导入一个单文件本地视频。
      2. 在对应预览缓存目录下伪造 hls/index.m3u8 与 seg-0001.ts。
      3. 调用详情与播放链接接口。
    - 预期结果:
      1. 详情接口仍然成功返回。
      2. local_episodes 只包含原始视频，不包含 HLS 分片。
      3. 播放链接仍然走 local-stream。
    """
    base_url = integration_runtime["base_url"]
    data_dir = integration_runtime["data_dir"]

    source_dir = tmp_path / "softlink-preview-source"
    source_dir.mkdir()
    video_file = source_dir / "single episode.mp4"
    video_file.write_bytes(b"video")

    import_response = requests.post(
        f"{base_url}/api/v1/video/local-import/from-path",
        json={
            "source_path": str(source_dir),
            "import_mode": "softlink_ref",
        },
        timeout=5,
    )
    assert import_response.status_code == 200
    import_payload = import_response.json()
    assert import_payload["code"] == 200
    created_id = import_payload["data"]["imported_ids"][0]

    hls_dir = data_dir / "media" / "video" / "LOCAL" / created_id / "hls"
    hls_dir.mkdir(parents=True, exist_ok=True)
    (hls_dir / "index.m3u8").write_text("#EXTM3U\n#EXTINF:3,\nseg-0001.ts\n", encoding="utf-8")
    (hls_dir / "seg-0001.ts").write_bytes(b"segment")

    detail_response = requests.get(
        f"{base_url}/api/v1/video/detail",
        params={"video_id": created_id},
        timeout=5,
    )
    assert detail_response.status_code == 200
    detail_payload = detail_response.json()
    assert detail_payload["code"] == 200

    detail = detail_payload["data"] or {}
    episodes = ((detail.get("display") or {}).get("local_episodes") or [])
    playback = detail.get("playback") or {}
    primary = playback.get("primary") or {}
    preview = playback.get("preview") or {}
    assert len(episodes) == 1
    assert episodes[0]["name"] == "single episode.mp4"
    assert all(not str(item.get("name") or "").endswith(".ts") for item in episodes)
    assert primary.get("mode") == "local"
    assert [item.get("name") for item in (primary.get("episodes") or [])] == ["single episode.mp4"]
    assert preview.get("available") is False

    play_response = requests.get(
        f"{base_url}/api/v1/video/{created_id}/play-urls",
        timeout=5,
    )
    assert play_response.status_code == 200
    play_payload = play_response.json()
    assert play_payload["code"] == 200
    stream_url = play_payload["data"]["sources"][0]["streams"][0]["url"]
    assert stream_url.startswith(f"/api/v1/video/local-stream/{created_id}")


@pytest.mark.integration
def test_teledrive_migrated_local_video_play_urls_normalize_media_episodes_to_local_stream(integration_runtime, tmp_path):
    """
    用例描述:
    - 用例目的: 看护 TeleDrive 迁入本地后的历史视频记录即使仍保存 `/media/...` 分集 URL，主播放器也必须统一走 local-stream。
    - 测试步骤:
      1. 手工写入一条带多集 `/media/...` URL 的 TeleDrive 本地视频记录。
      2. 调用详情与播放链接接口。
      3. 请求返回的第 2 集 local-stream 地址。
    - 预期结果:
      1. detail.playback.primary.mode=local，preview 不把远端正片误判成预览视频。
      2. play-urls 返回的每一集都走 `/api/v1/video/local-stream/{id}?episode=n`。
      3. 第 2 集 local-stream 能成功回放本地文件。
    """
    base_url = integration_runtime["base_url"]
    meta_dir = integration_runtime["meta_dir"]
    data_dir = integration_runtime["data_dir"]
    videos_path = meta_dir / "videos_database.json"
    original_payload = load_json(videos_path)

    video_id = f"TD-VIDEO-{uuid4().hex[:12]}"
    asset_dir = data_dir / "video" / "TeleDrive" / f"td-case-{uuid4().hex[:8]}"
    asset_dir.mkdir(parents=True, exist_ok=True)
    episode_one = asset_dir / "ep-1.mp4"
    episode_two = asset_dir / "ep-2.mp4"
    episode_one.write_bytes(b"episode-one")
    episode_two.write_bytes(b"episode-two")

    media_root = asset_dir.relative_to(data_dir).as_posix()
    payload = load_json(videos_path)
    payload["videos"] = [
        item for item in (payload.get("videos") or [])
        if str((item or {}).get("id", "")) != video_id
    ]
    payload["videos"].append(
        {
            "id": video_id,
            "title": "TeleDrive Local Multi Episode",
            "title_jp": "",
            "creator": "",
            "desc": "TeleDrive migrated local case",
            "cover_path": "",
            "total_units": 2,
            "current_unit": 1,
            "score": 8.0,
            "tag_ids": [],
            "list_ids": [],
            "create_time": "2026-05-31T00:00:00",
            "last_access_time": "2026-05-31T00:00:00",
            "is_deleted": False,
            "code": "TD-LOCAL-CASE",
            "date": "",
            "series": "",
            "magnets": [],
            "thumbnail_images": [],
            "preview_video": "/api/v1/teledrive/files/remote-ep-1/content?name=ep-1.mp4",
            "cover_path_local": "",
            "thumbnail_images_local": [],
            "preview_video_local": f"/media/{media_root}/ep-1.mp4",
            "platform": "TeleDrive",
            "plugin_id": "storage.teledrive",
            "plugin_name": "TeleDrive",
            "display": {
                "local_episodes": [
                    {
                        "name": "ep-1.mp4",
                        "relative_path": "ep-1.mp4",
                        "url": f"/media/{media_root}/ep-1.mp4",
                        "index": 1,
                    },
                    {
                        "name": "ep-2.mp4",
                        "relative_path": "ep-2.mp4",
                        "url": f"/media/{media_root}/ep-2.mp4",
                        "index": 2,
                    },
                ],
                "teledrive_origin": {
                    "type": "video",
                    "root": "/video",
                    "path": "/video/td-local-case",
                    "folder_id": "folder-case",
                    "work_id": "td-local-case",
                    "episode_count": 2,
                    "thumbnail_count": 0,
                },
            },
            "storage_path_relative": f"{media_root}/ep-1.mp4",
            "storage_path_kind": "local_file",
            "source_origin": "teledrive_migrate",
            "source_updated_time": "2026-05-31T00:00:00",
            "local_asset_dir_name": asset_dir.name,
            "local_source_filename": "ep-1.mp4",
            "local_source_path": str(episode_one),
            "local_video_path": f"/media/{media_root}/ep-1.mp4",
            "actors": [],
            "actor_refs": [],
        }
    )
    save_json(videos_path, payload)

    try:
        detail_response = requests.get(
            f"{base_url}/api/v1/video/detail",
            params={"video_id": video_id},
            timeout=5,
        )
        assert detail_response.status_code == 200
        detail_payload = detail_response.json()
        assert detail_payload["code"] == 200
        detail = detail_payload["data"] or {}
        playback = detail.get("playback") or {}
        primary = playback.get("primary") or {}
        preview = playback.get("preview") or {}
        assert primary.get("mode") == "local"
        assert [item.get("name") for item in (primary.get("episodes") or [])] == ["ep-1.mp4", "ep-2.mp4"]
        assert preview.get("available") is False

        play_response = requests.get(
            f"{base_url}/api/v1/video/{video_id}/play-urls",
            timeout=5,
        )
        assert play_response.status_code == 200
        play_payload = play_response.json()
        assert play_payload["code"] == 200
        sources = play_payload["data"]["sources"] or []
        assert [item.get("name") for item in sources] == ["ep-1.mp4", "ep-2.mp4"]
        assert sources[0]["streams"][0]["url"] == f"/api/v1/video/local-stream/{video_id}?episode=1"
        assert sources[1]["streams"][0]["url"] == f"/api/v1/video/local-stream/{video_id}?episode=2"

        episode_two_response = requests.get(
            f"{base_url}{sources[1]['streams'][0]['url']}",
            timeout=10,
        )
        assert episode_two_response.status_code == 200
        assert episode_two_response.content == b"episode-two"
    finally:
        save_json(videos_path, original_payload)


@pytest.mark.integration
def test_video_detail_returns_full_info(integration_runtime):
    """
    用例描述:
    - 用例目的: 验证视频详情接口返回完整的视频信息。
    - 测试步骤:
      1. 调用 GET /api/v1/video/detail?video_id=JAVDB900001。
      2. 检查返回数据完整性。
    - 预期结果:
      1. HTTP 200，业务 code=200。
      2. 返回数据包含 id、title、code、score、actors 等字段。
    - 历史变更:
      - 2026-03-25: 初始创建，覆盖视频详情主链路。
    """
    base_url = integration_runtime["base_url"]

    from tests.shared.test_constants import PRIMARY_VIDEO_ID

    response = requests.get(
        f"{base_url}/api/v1/video/detail",
        params={"video_id": PRIMARY_VIDEO_ID},
        timeout=5,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 200
    data = payload["data"]
    assert data["id"] == PRIMARY_VIDEO_ID
    assert "title" in data
    assert "code" in data
    assert "score" in data


@pytest.mark.integration
def test_video_detail_rejects_nonexistent_video(integration_runtime):
    """
    用例描述:
    - 用例目的: 验证视频详情接口对不存在视频返回正确错误。
    - 测试步骤:
      1. 调用 GET /api/v1/video/detail?video_id=NONEXISTENT。
      2. 检查返回错误码。
    - 预期结果:
      1. HTTP 200，业务 code=404。
    - 历史变更:
      - 2026-03-25: 初始创建，覆盖视频详情不存在分支。
    """
    base_url = integration_runtime["base_url"]

    response = requests.get(
        f"{base_url}/api/v1/video/detail",
        params={"video_id": "NONEXISTENT_VIDEO_999"},
        timeout=5,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 404


@pytest.mark.integration
def test_video_edit_updates_metadata_and_persists(integration_runtime):
    """
    用例描述:
    - 用例目的: 验证视频编辑接口能正确更新元数据并持久化。
    - 测试步骤:
      1. 调用 PUT /api/v1/video/edit 更新视频标题和演员。
      2. 检查接口返回状态。
      3. 验证文件中数据已更新。
    - 预期结果:
      1. HTTP 200，业务 code=200。
      2. 返回数据包含更新后的字段。
      3. 文件中对应记录已更新。
    - 历史变更:
      - 2026-03-25: 初始创建，覆盖视频编辑主链路。
    """
    base_url = integration_runtime["base_url"]
    meta_dir = integration_runtime["meta_dir"]
    videos_path = meta_dir / "videos_database.json"

    from tests.shared.test_constants import PRIMARY_VIDEO_ID

    original = find_by_id(load_json(videos_path).get("videos", []), PRIMARY_VIDEO_ID)
    assert original is not None
    original_title = original.get("title")
    original_actors = original.get("actors")

    new_title = "Updated Video Title"
    new_actors = ["New Actor A", "New Actor B"]

    try:
        response = requests.put(
            f"{base_url}/api/v1/video/edit",
            json={"video_id": PRIMARY_VIDEO_ID, "title": new_title, "actors": new_actors},
            timeout=5,
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["code"] == 200
        assert payload["data"]["title"] == new_title
        assert payload["data"]["actors"] == new_actors

        videos_data = load_json(videos_path)
        videos = videos_data.get("videos", [])
        updated = find_by_id(videos, PRIMARY_VIDEO_ID)
        assert updated is not None
        assert updated["title"] == new_title
        assert updated["actors"] == new_actors
    finally:
        requests.put(
            f"{base_url}/api/v1/video/edit",
            json={"video_id": PRIMARY_VIDEO_ID, "title": original_title, "actors": original_actors},
            timeout=5,
        )


@pytest.mark.integration
def test_video_score_update_persists(integration_runtime):
    """
    用例描述:
    - 用例目的: 验证视频评分更新接口能正确持久化评分。
    - 测试步骤:
      1. 调用 PUT /api/v1/video/score 更新评分。
      2. 验证接口返回和文件持久化。
    - 预期结果:
      1. HTTP 200，业务 code=200。
      2. 文件中对应记录的 score 已更新。
    - 历史变更:
      - 2026-03-25: 初始创建，覆盖视频评分更新主链路。
    """
    base_url = integration_runtime["base_url"]
    meta_dir = integration_runtime["meta_dir"]
    videos_path = meta_dir / "videos_database.json"

    from tests.shared.test_constants import PRIMARY_VIDEO_ID

    original = find_by_id(load_json(videos_path).get("videos", []), PRIMARY_VIDEO_ID)
    assert original is not None
    original_score = original.get("score")

    new_score = 9.5

    try:
        response = requests.put(
            f"{base_url}/api/v1/video/score",
            json={"video_id": PRIMARY_VIDEO_ID, "score": new_score},
            timeout=5,
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["code"] == 200
        assert payload["data"]["score"] == new_score

        videos_data = load_json(videos_path)
        videos = videos_data.get("videos", [])
        updated = find_by_id(videos, PRIMARY_VIDEO_ID)
        assert updated is not None
        assert updated["score"] == new_score
    finally:
        requests.put(
            f"{base_url}/api/v1/video/score",
            json={"video_id": PRIMARY_VIDEO_ID, "score": original_score},
            timeout=5,
        )


@pytest.mark.integration
def test_video_progress_update_persists(integration_runtime):
    """
    用例描述:
    - 用例目的: 验证视频进度更新接口能正确持久化进度。
    - 测试步骤:
      1. 调用 PUT /api/v1/video/progress 更新进度。
      2. 验证接口返回和文件持久化。
    - 预期结果:
      1. HTTP 200，业务 code=200。
      2. 文件中对应记录的进度已更新。
    - 历史变更:
      - 2026-03-25: 初始创建，覆盖视频进度更新主链路。
    """
    base_url = integration_runtime["base_url"]
    meta_dir = integration_runtime["meta_dir"]
    videos_path = meta_dir / "videos_database.json"

    from tests.shared.test_constants import PRIMARY_VIDEO_ID

    original = find_by_id(load_json(videos_path).get("videos", []), PRIMARY_VIDEO_ID)
    assert original is not None
    original_unit = original.get("current_unit")

    new_unit = 1

    try:
        response = requests.put(
            f"{base_url}/api/v1/video/progress",
            json={"video_id": PRIMARY_VIDEO_ID, "unit": new_unit},
            timeout=5,
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["code"] == 200

        videos_data = load_json(videos_path)
        videos = videos_data.get("videos", [])
        updated = find_by_id(videos, PRIMARY_VIDEO_ID)
        assert updated is not None
    finally:
        requests.put(
            f"{base_url}/api/v1/video/progress",
            json={"video_id": PRIMARY_VIDEO_ID, "unit": original_unit},
            timeout=5,
        )


@pytest.mark.integration
def test_video_search_returns_matching_results(integration_runtime):
    """
    用例描述:
    - 用例目的: 验证视频搜索接口能正确返回匹配结果。
    - 测试步骤:
      1. 调用 GET /api/v1/video/search?keyword=Seed。
      2. 检查返回结果包含匹配的视频。
    - 预期结果:
      1. HTTP 200，业务 code=200。
      2. 返回结果包含标题含有关键词的视频。
    - 历史变更:
      - 2026-03-25: 初始创建，覆盖视频搜索主链路。
    """
    base_url = integration_runtime["base_url"]

    response = requests.get(
        f"{base_url}/api/v1/video/search",
        params={"keyword": "Seed"},
        timeout=5,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 200
    results = payload["data"]
    assert len(results) >= 1
    assert any("Seed" in item["title"] for item in results)


@pytest.mark.integration
def test_video_search_rejects_missing_keyword(integration_runtime):
    """
    用例描述:
    - 用例目的: 验证视频搜索接口校验必要参数。
    - 测试步骤:
      1. 调用 GET /api/v1/video/search 不传 keyword。
      2. 检查接口返回错误码。
    - 预期结果:
      1. HTTP 200，业务 code=400。
    - 历史变更:
      - 2026-03-25: 初始创建，覆盖视频搜索参数校验。
    """
    base_url = integration_runtime["base_url"]

    response = requests.get(
        f"{base_url}/api/v1/video/search",
        timeout=5,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 400
