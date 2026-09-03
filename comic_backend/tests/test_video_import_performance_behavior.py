from __future__ import annotations

from pathlib import Path
import sys

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from application.video_app_service import VideoAppService
from domain.video import Video


class _CountingVideoRepo:
    def __init__(self, videos):
        self._videos = list(videos)
        self.get_all_calls = 0
        self.get_by_id_calls = 0
        self.save_many_calls = 0

    def get_all(self):
        self.get_all_calls += 1
        return list(self._videos)

    def get_by_id(self, video_id):
        self.get_by_id_calls += 1
        return next((video for video in self._videos if video.id == video_id), None)

    def save_many(self, videos):
        self.save_many_calls += 1
        by_id = {video.id: video for video in self._videos}
        for video in videos:
            by_id[video.id] = video
        self._videos = list(by_id.values())
        return len(videos)


def test_local_video_duplicate_cache_avoids_repeated_full_repo_reads():
    repo = _CountingVideoRepo(
        [
            Video(id="VIDEO001", title="Video 1", code="ABC-123"),
            Video(id="VIDEO002", title="Video 2", code="XYZ-456"),
        ]
    )
    service = VideoAppService(video_repo=repo)

    cache = service._build_local_video_duplicate_cache()
    for _ in range(20):
        duplicate = service._find_local_video_duplicate_entity(
            "",
            "abc123",
            local_video_cache=cache,
        )
        assert duplicate is not None
        assert duplicate.id == "VIDEO001"

    assert repo.get_all_calls == 1
    assert repo.get_by_id_calls == 0


def test_import_videos_rejects_duplicate_codes_inside_same_batch():
    repo = _CountingVideoRepo([])
    service = VideoAppService(video_repo=repo)
    cache = service._build_local_video_duplicate_cache()

    result = service.import_videos(
        [
            {"id": "VIDEO001", "title": "Video 1", "code": "ABC-123"},
            {"id": "VIDEO002", "title": "Video 2", "code": "abc123"},
        ],
        local_video_cache=cache,
    )

    assert result.success is True
    assert result.data["imported_count"] == 1
    assert result.data["failed_items"] == [{"lookup": "ABC-123", "reason": "批次内番号重复"}]
    assert [video.id for video in repo._videos] == ["VIDEO001"]
    assert repo.save_many_calls == 1


def test_batch_import_videos_uses_single_bulk_save_and_skips_existing():
    repo = _CountingVideoRepo(
        [
            Video(id="EXISTING001", title="Existing", code="ABC-123"),
        ]
    )
    service = VideoAppService(video_repo=repo)

    result = service.batch_import_videos(
        [
            {"id": "EXISTING001", "title": "Duplicate", "code": "ABC-123"},
            {"id": "VIDEO002", "title": "Video 2", "code": "DEF-456"},
            {"id": "VIDEO003", "title": "Video 3", "code": "GHI-789"},
        ]
    )

    assert result.success is True
    assert result.data["imported_count"] == 2
    assert result.data["skipped"] == ["ABC-123"]
    assert result.data["imported_ids"] == ["VIDEO002", "VIDEO003"]
    assert [video.id for video in repo._videos] == ["EXISTING001", "VIDEO002", "VIDEO003"]
    assert repo.get_all_calls == 1
    assert repo.save_many_calls == 1
