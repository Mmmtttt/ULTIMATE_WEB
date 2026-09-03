from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

task_manager_module = importlib.import_module("infrastructure.task_manager")
json_storage_module = importlib.import_module("infrastructure.persistence.json_storage")

ImportTask = task_manager_module.ImportTask
TaskManager = task_manager_module.TaskManager
TaskStatus = task_manager_module.TaskStatus
JsonStorage = json_storage_module.JsonStorage


class _ServiceResult:
    def __init__(self, success: bool, message: str = "", data=None):
        self.success = success
        self.message = message
        self.data = data or {}


def _build_manager(tmp_path, monkeypatch):
    existing = TaskManager._instance
    if existing is not None:
        existing._running = False
    TaskManager._instance = None
    JsonStorage._instances.clear()
    JsonStorage._locks.clear()
    monkeypatch.setattr(json_storage_module, "get_meta_dir", lambda: str(tmp_path))
    monkeypatch.setattr(TaskManager, "_start_worker", lambda self: None)
    manager = TaskManager(task_file=str(tmp_path / "tasks.json"))
    manager._running = False
    return manager


def test_create_batch_task_sets_expected_initial_fields(tmp_path, monkeypatch):
    manager = _build_manager(tmp_path, monkeypatch)

    task_id = manager.create_batch_task(
        task_type=manager.TASK_TYPE_COMIC_LOCAL_METADATA_REFRESH,
        content_type="comic",
        item_ids=["LOCALA001", "LOCALA002"],
        title="批量补全本地漫画信息（2 项）",
    )

    task = manager.get_task(task_id)
    assert task is not None
    assert task.status == TaskStatus.PENDING
    assert task.import_type == manager.TASK_TYPE_COMIC_LOCAL_METADATA_REFRESH
    assert task.content_type == "comic"
    assert task.platform == "LOCAL"
    assert task.target == "local"
    assert task.comic_ids == ["LOCALA001", "LOCALA002"]
    assert task.total_pages == 2
    assert task.downloaded_pages == 0
    assert task.cancel_requested is False


def test_execute_batch_thumbnail_task_tracks_success_failed_and_skipped(tmp_path, monkeypatch):
    manager = _build_manager(tmp_path, monkeypatch)
    video_app_module = importlib.import_module("application.video_app_service")

    monkeypatch.setattr(
        video_app_module,
        "probe_local_video_thumbnail_runtime",
        lambda: {"supported": True, "reason": "", "runtime_profile": "full"},
    )

    class _FakeVideoService:
        def generate_local_video_thumbnails(self, video_id: str):
            if video_id == "LOCALV_SKIP":
                return _ServiceResult(False, "未找到可用的本地视频文件")
            if video_id == "LOCALV_FAIL":
                return _ServiceResult(False, "ffmpeg 执行失败")
            return _ServiceResult(True, "ok", {"id": video_id})

    monkeypatch.setattr(video_app_module, "VideoAppService", _FakeVideoService)

    task_id = manager.create_batch_task(
        task_type=manager.TASK_TYPE_VIDEO_LOCAL_THUMBNAIL_GENERATE,
        content_type="video",
        item_ids=["LOCALV_OK", "LOCALV_SKIP", "LOCALV_FAIL"],
        title="批量生成视频缩略图（3 项）",
    )
    task = manager.get_task(task_id)

    result = manager._execute_batch_content_task(task)

    assert result["success"] is True
    assert result["processed_count"] == 3
    assert result["success_count"] == 1
    assert result["skipped_count"] == 1
    assert result["failed_count"] == 1
    assert result["skipped_items"] == [{"id": "LOCALV_SKIP", "error": "未找到可用的本地视频文件"}]
    assert result["failed_items"] == [{"id": "LOCALV_FAIL", "error": "ffmpeg 执行失败"}]
    assert task.downloaded_pages == 3
    assert task.total_pages == 3
    assert task.progress == 100


def test_execute_batch_task_stops_after_cancel_request(tmp_path, monkeypatch):
    manager = _build_manager(tmp_path, monkeypatch)
    video_app_module = importlib.import_module("application.video_app_service")

    monkeypatch.setattr(
        video_app_module,
        "probe_local_video_thumbnail_runtime",
        lambda: {"supported": True, "reason": "", "runtime_profile": "full"},
    )

    task_id = manager.create_batch_task(
        task_type=manager.TASK_TYPE_VIDEO_LOCAL_THUMBNAIL_GENERATE,
        content_type="video",
        item_ids=["LOCALV_1", "LOCALV_2"],
        title="批量生成视频缩略图（2 项）",
    )
    task = manager.get_task(task_id)

    class _FakeVideoService:
        def generate_local_video_thumbnails(self, video_id: str):
            if video_id == "LOCALV_1":
                manager._tasks[task_id].cancel_requested = True
            return _ServiceResult(True, "ok", {"id": video_id})

    monkeypatch.setattr(video_app_module, "VideoAppService", _FakeVideoService)

    result = manager._execute_batch_content_task(task)

    assert result["cancelled"] is True
    assert result["processed_count"] == 1
    assert result["success_count"] == 1
    assert task.downloaded_pages == 1
    assert task.progress == 50


def test_execute_batch_task_continues_after_single_item_exception(tmp_path, monkeypatch):
    manager = _build_manager(tmp_path, monkeypatch)
    video_app_module = importlib.import_module("application.video_app_service")

    monkeypatch.setattr(
        video_app_module,
        "probe_local_video_thumbnail_runtime",
        lambda: {"supported": True, "reason": "", "runtime_profile": "full"},
    )

    class _FakeVideoService:
        def generate_local_video_thumbnails(self, video_id: str):
            if video_id == "LOCALV_BROKEN":
                raise RuntimeError("ffmpeg crashed")
            return _ServiceResult(True, "ok", {"id": video_id})

    monkeypatch.setattr(video_app_module, "VideoAppService", _FakeVideoService)

    task_id = manager.create_batch_task(
        task_type=manager.TASK_TYPE_VIDEO_LOCAL_THUMBNAIL_GENERATE,
        content_type="video",
        item_ids=["LOCALV_OK_1", "LOCALV_BROKEN", "LOCALV_OK_2"],
        title="批量生成视频缩略图（3 项）",
    )
    task = manager.get_task(task_id)

    result = manager._execute_batch_content_task(task)

    assert result["success"] is True
    assert result["processed_count"] == 3
    assert result["success_count"] == 2
    assert result["failed_count"] == 1
    assert result["failed_items"] == [{"id": "LOCALV_BROKEN", "error": "ffmpeg crashed"}]
    assert task.downloaded_pages == 3
    assert task.progress == 100


def test_execute_comic_import_backfills_storage_fields_before_save(tmp_path, monkeypatch):
    manager = _build_manager(tmp_path, monkeypatch)

    json_file = tmp_path / "comics_database.json"
    recommendation_file = tmp_path / "recommendations_database.json"
    tags_file = tmp_path / "tags_database.json"
    json_file.write_text(json.dumps({"comics": [], "total_comics": 0}, ensure_ascii=False), encoding="utf-8")
    recommendation_file.write_text(json.dumps({"recommendations": [], "total_recommendations": 0}, ensure_ascii=False), encoding="utf-8")
    tags_file.write_text(json.dumps({"tags": []}, ensure_ascii=False), encoding="utf-8")

    monkeypatch.setattr(task_manager_module, "JSON_FILE", str(json_file))
    monkeypatch.setattr(task_manager_module, "RECOMMENDATION_JSON_FILE", str(recommendation_file))
    constants_module = importlib.import_module("core.constants")
    monkeypatch.setattr(constants_module, "TAGS_JSON_FILE", str(tags_file))

    monkeypatch.setattr(manager, "_resolve_comic_manifest", lambda platform: None)
    monkeypatch.setattr(manager, "_resolve_comic_download_dir", lambda platform: str(tmp_path / "downloads"))
    monkeypatch.setattr(
        manager,
        "_convert_to_standard_format",
        lambda albums, existing_tags, platform: {
            "comics": [
                {
                    "id": "JMTEST001",
                    "title": "Task Import Comic",
                    "title_jp": "",
                    "author": "Tester",
                    "desc": "",
                    "cover_path": "",
                    "total_page": 12,
                    "current_page": 1,
                    "score": 8.0,
                    "tag_ids": [],
                    "list_ids": [],
                    "create_time": "2026-05-15T00:00:00",
                    "last_read_time": "2026-05-15T00:00:00",
                    "is_deleted": False,
                    "storage_path_relative": "",
                    "storage_path_kind": "",
                }
            ],
            "tags": [],
        },
    )

    platform_service_module = importlib.import_module("protocol.platform_service")
    platform_meta_module = importlib.import_module("protocol.platform_meta")
    comic_app_module = importlib.import_module("application.comic_app_service")

    class _FakePlatformService:
        def get_album_by_id(self, platform, comic_id):
            return {"albums": [{"album_id": "TEST001", "title": "Task Import Comic", "pages": 12}]}

        def download_album(self, platform, original_id, download_dir=None, show_progress=False):
            return ({"local_pages": 12}, True)

    class _FakeComicService:
        def _refresh_comic_persisted_metadata(self, comic, *, source: str):
            comic["storage_path_relative"] = "comic/JM/TEST001"
            comic["storage_path_kind"] = "local_dir"
            comic["platform"] = "JM"
            return True

    monkeypatch.setattr(platform_service_module, "get_platform_service", lambda: _FakePlatformService())
    monkeypatch.setattr(platform_meta_module, "split_prefixed_id", lambda comic_id, media_type="comic": ("JM", "TEST001", None))
    monkeypatch.setattr(comic_app_module, "ComicAppService", _FakeComicService)

    task_id = manager.create_task(platform="JM", import_type="by_id", target="home", comic_id="TEST001")
    task = manager.get_task(task_id)

    result = manager._execute_import(task)

    assert result["success"] is True
    saved = json.loads(json_file.read_text(encoding="utf-8"))
    assert saved["comics"][0]["storage_path_relative"] == "comic/JM/TEST001"
    assert saved["comics"][0]["storage_path_kind"] == "local_dir"


def test_execute_video_import_backfills_storage_fields_for_preview_records(tmp_path, monkeypatch):
    manager = _build_manager(tmp_path, monkeypatch)

    preview_json = tmp_path / "video_recommendations_database.json"
    preview_json.write_text(json.dumps({"video_recommendations": []}, ensure_ascii=False), encoding="utf-8")

    constants_module = importlib.import_module("core.constants")
    monkeypatch.setattr(constants_module, "VIDEO_RECOMMENDATION_JSON_FILE", str(preview_json))

    video_runtime_module = importlib.import_module("application.video_runtime_support")
    video_app_module = importlib.import_module("application.video_app_service")
    tag_app_module = importlib.import_module("application.tag_app_service")

    class _FakeAdapter:
        def get_video_detail(self, lookup):
            return {
                "code": "ABP-123",
                "title": "Preview Video",
                "date": "2026-05-15",
                "series": "Series",
                "actors": ["Actor A"],
                "magnets": [],
                "thumbnail_images": [],
                "preview_video": "",
                "cover_url": "",
                "tags": [],
            }

    class _FakeVideoService:
        def _refresh_video_persisted_metadata(self, video, *, source: str):
            video["storage_path_relative"] = "recommendation_cache/video/JAVDB/JAVDBTEST001"
            video["storage_path_kind"] = "preview_asset_dir"
            video["platform"] = "JAVDB"
            return True

        def get_video_by_code(self, code):
            return _ServiceResult(False, "not found", None)

        def import_video(self, video_data):
            return _ServiceResult(True, "ok", video_data)

        def apply_recent_import_tags(self, video_ids, source="local", clear_previous=True):
            return _ServiceResult(True, "ok", {})

    class _FakeTagService:
        def get_tag_list(self, content_type):
            return _ServiceResult(True, "ok", [])

        def create_tag(self, name, content_type):
            return _ServiceResult(True, "ok", {"id": f"tag_{name}"})

    monkeypatch.setattr(video_runtime_module, "resolve_video_lookup_context", lambda video_id="", platform_name="": ("javdb", video_id or "TEST001", None))
    monkeypatch.setattr(video_runtime_module, "build_video_host_id", lambda platform, lookup: "JAVDBTEST001")
    monkeypatch.setattr(video_runtime_module, "get_video_adapter", lambda platform, existing_tags: _FakeAdapter())
    monkeypatch.setattr(video_runtime_module, "platform_allows_preview_video_download", lambda **kwargs: False)
    monkeypatch.setattr(video_runtime_module, "sanitize_preview_video_value", lambda value: str(value or "").strip())
    monkeypatch.setattr(video_runtime_module, "schedule_video_asset_cache", lambda **kwargs: None)
    monkeypatch.setattr(video_runtime_module, "to_proxy_image_url", lambda *args, **kwargs: "")
    monkeypatch.setattr(video_app_module, "VideoAppService", _FakeVideoService)
    monkeypatch.setattr(tag_app_module, "TagAppService", _FakeTagService)

    task_id = manager.create_task(platform="javdb", import_type="by_id", target="recommendation", comic_id="TEST001", content_type="video")
    task = manager.get_task(task_id)

    result = manager._execute_import(task)

    assert result["success"] is True
    saved = json.loads(preview_json.read_text(encoding="utf-8"))
    assert saved["video_recommendations"][0]["storage_path_relative"] == "recommendation_cache/video/JAVDB/JAVDBTEST001"
    assert saved["video_recommendations"][0]["storage_path_kind"] == "preview_asset_dir"
