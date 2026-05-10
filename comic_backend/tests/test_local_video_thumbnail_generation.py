from __future__ import annotations

import importlib
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

video_app_module = importlib.import_module("application.video_app_service")
video_domain_module = importlib.import_module("domain.video")

VideoAppService = video_app_module.VideoAppService
Video = video_domain_module.Video


class _VideoRepo:
    def __init__(self, video: Video):
        self.video = video
        self.save_calls = 0

    def get_by_id(self, video_id: str):
        if str(video_id or "").strip() == str(self.video.id or "").strip():
            return self.video
        return None

    def save(self, video: Video):
        self.video = video
        self.save_calls += 1
        return True

    def get_all(self):
        return [self.video]


class _EmptyRepo:
    def get_by_id(self, _item_id):
        return None

    def save(self, _item):
        return True

    def get_all(self, *args, **kwargs):
        return []


class _TagRepo:
    def get_all(self, *args, **kwargs):
        return []


def _make_service(tmp_path: Path, video: Video, monkeypatch):
    data_dir = tmp_path / "data"
    video_dir = data_dir / "video"
    data_dir.mkdir(parents=True, exist_ok=True)
    video_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(video_app_module, "DATA_DIR", str(data_dir))
    monkeypatch.setattr(video_app_module, "VIDEO_DIR", str(video_dir))
    monkeypatch.setattr(video_app_module, "VIDEO_RECOMMENDATION_CACHE_DIR", str(data_dir / "recommendation_cache" / "video"))

    return VideoAppService(
        video_repo=_VideoRepo(video),
        video_rec_repo=_EmptyRepo(),
        tag_repo=_TagRepo(),
        actor_repo=_EmptyRepo(),
    )


def test_generate_local_video_thumbnails_persists_assets_and_cover_selection(tmp_path, monkeypatch):
    source_file = tmp_path / "imports" / "demo-source.mp4"
    source_file.parent.mkdir(parents=True, exist_ok=True)
    source_file.write_bytes(b"not-a-real-video-but-good-enough-for-mocked-generator")

    video = Video(
        id="LOCALV_THUMB001",
        code="DEMO-001",
        title="Local Demo Video",
        local_source_path=str(source_file),
        local_asset_dir_name="Local Demo Video",
        source_origin="local_import",
    )
    service = _make_service(tmp_path, video, monkeypatch)

    monkeypatch.setattr(
        video_app_module,
        "probe_local_video_thumbnail_runtime",
        lambda: {
            "supported": True,
            "provider": "ffmpeg_seek",
            "platform": "windows",
            "runtime_profile": "full",
            "reason": "",
            "ffmpeg_path": "fake-ffmpeg",
        },
    )

    class _FakeGenerator:
        def __init__(self, ffmpeg_path=""):
            self.ffmpeg_path = ffmpeg_path

        def generate_thumbnails(self, *, video_path, output_dir, count, width):
            assert Path(video_path) == source_file
            assert int(count) == service.LOCAL_THUMBNAIL_TARGET_COUNT
            assert int(width) == service.LOCAL_THUMBNAIL_WIDTH
            Path(output_dir).mkdir(parents=True, exist_ok=True)
            for index in range(1, count + 1):
                (Path(output_dir) / f"thumb-{index:04d}.jpg").write_bytes(f"thumb-{index}".encode("utf-8"))
            return {
                "duration_seconds": 120.0,
                "thumbnail_count": count,
                "default_cover_index": 10,
                "timestamps": [float(index) for index in range(count)],
            }

    monkeypatch.setattr(video_app_module, "FFmpegLocalVideoThumbnailService", _FakeGenerator)

    result = service.generate_local_video_thumbnails(video.id)

    assert result.success is True
    payload = dict(result.data or {})
    assert len(payload.get("thumbnail_images_local") or []) == 20
    assert payload.get("local_cover_thumbnail_index") == 10
    assert str(payload.get("cover_path_local") or "").endswith("/cover.jpg")
    assert payload.get("local_thumbnail_capability", {}).get("show_generate_action") is True
    assert payload.get("local_thumbnail_capability", {}).get("can_select_cover") is True

    asset_dir = Path(service._resolve_video_local_asset_dir(service._video_repo.video))
    assert (asset_dir / "cover.jpg").is_file()
    assert (asset_dir / "thumbs" / "thumb-0001.jpg").is_file()
    assert (asset_dir / "thumbs" / "thumb-0020.jpg").is_file()
    assert (asset_dir / "cover.jpg").read_bytes() == (asset_dir / "thumbs" / "thumb-0011.jpg").read_bytes()


def test_select_local_thumbnail_as_cover_copies_requested_thumbnail_and_updates_index(tmp_path, monkeypatch):
    source_file = tmp_path / "imports" / "select-source.mp4"
    source_file.parent.mkdir(parents=True, exist_ok=True)
    source_file.write_bytes(b"local-video")

    video = Video(
        id="LOCALV_THUMB002",
        code="DEMO-002",
        title="Select Cover Demo",
        local_source_path=str(source_file),
        local_asset_dir_name="Select Cover Demo",
        source_origin="local_import",
    )
    service = _make_service(tmp_path, video, monkeypatch)

    asset_dir = Path(service._resolve_video_local_asset_dir(video))
    thumbs_dir = asset_dir / "thumbs"
    thumbs_dir.mkdir(parents=True, exist_ok=True)

    thumb_urls = []
    for index in range(1, 5):
        thumb_path = thumbs_dir / f"thumb-{index:04d}.jpg"
        thumb_path.write_bytes(f"choose-{index}".encode("utf-8"))
        thumb_urls.append(f"/media/video/LOCAL/Select Cover Demo/thumbs/thumb-{index:04d}.jpg")

    cover_path = asset_dir / "cover.jpg"
    cover_path.write_bytes(b"old-cover")

    video.thumbnail_images_local = thumb_urls
    video.cover_path_local = "/media/video/LOCAL/Select Cover Demo/cover.jpg"
    video.local_cover_thumbnail_index = 0

    result = service.select_local_thumbnail_as_cover(video.id, 2)

    assert result.success is True
    payload = dict(result.data or {})
    assert payload.get("local_cover_thumbnail_index") == 2
    assert str(payload.get("cover_path_local") or "").endswith("/cover.jpg")
    assert cover_path.read_bytes() == (thumbs_dir / "thumb-0003.jpg").read_bytes()


def test_local_thumbnail_capability_requires_runtime_support_and_existing_source(tmp_path, monkeypatch):
    missing_source_video = Video(
        id="LOCALV_THUMB003",
        code="DEMO-003",
        title="No Source Video",
        local_source_path=str(tmp_path / "missing.mp4"),
        local_asset_dir_name="No Source Video",
    )
    service = _make_service(tmp_path, missing_source_video, monkeypatch)

    monkeypatch.setattr(
        video_app_module,
        "probe_local_video_thumbnail_runtime",
        lambda: {
            "supported": False,
            "provider": "ffmpeg_seek",
            "platform": "android",
            "runtime_profile": "mobile_core",
            "reason": "当前运行时未启用本地视频缩略图能力",
            "ffmpeg_path": "",
        },
    )

    capability = service._build_local_thumbnail_capability(missing_source_video)

    assert capability["supported"] is False
    assert capability["show_generate_action"] is False
    assert capability["can_generate"] is False
    assert capability["can_select_cover"] is False
    assert "未启用" in capability["reason"]


def test_local_thumbnail_capability_keeps_generate_entry_visible_when_desktop_runtime_lacks_ffmpeg(
    tmp_path,
    monkeypatch,
):
    source_file = tmp_path / "imports" / "desktop-no-ffmpeg.mp4"
    source_file.parent.mkdir(parents=True, exist_ok=True)
    source_file.write_bytes(b"desktop-local-video")

    video = Video(
        id="LOCALV_THUMB004",
        code="DEMO-004",
        title="Desktop Missing FFmpeg",
        local_source_path=str(source_file),
        local_asset_dir_name="Desktop Missing FFmpeg",
    )
    service = _make_service(tmp_path, video, monkeypatch)

    monkeypatch.setattr(
        video_app_module,
        "probe_local_video_thumbnail_runtime",
        lambda: {
            "supported": False,
            "provider": "ffmpeg_seek",
            "platform": "windows",
            "runtime_profile": "full",
            "reason": "未找到 ffmpeg 运行时",
            "ffmpeg_path": "",
        },
    )

    capability = service._build_local_thumbnail_capability(video)

    assert capability["supported"] is False
    assert capability["has_local_source"] is True
    assert capability["show_generate_action"] is True
    assert capability["can_generate"] is False
    assert capability["can_select_cover"] is False
    assert "ffmpeg" in capability["reason"]
