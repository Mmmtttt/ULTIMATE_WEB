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

    def get_all(self):
        self.get_all_calls += 1
        return list(self._videos)

    def get_by_id(self, video_id):
        self.get_by_id_calls += 1
        return next((video for video in self._videos if video.id == video_id), None)


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
