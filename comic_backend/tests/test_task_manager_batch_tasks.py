from __future__ import annotations

import importlib
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

task_manager_module = importlib.import_module("infrastructure.task_manager")

ImportTask = task_manager_module.ImportTask
TaskManager = task_manager_module.TaskManager
TaskStatus = task_manager_module.TaskStatus


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
