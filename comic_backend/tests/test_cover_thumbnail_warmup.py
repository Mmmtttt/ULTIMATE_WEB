from __future__ import annotations

from pathlib import Path
import sys

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import application.cover_thumbnail_service as thumbnail_service
from application.cover_thumbnail_service import CoverThumbnailError
from PIL import Image


class InlineExecutor:
    def submit(self, fn, *args, **kwargs):
        fn(*args, **kwargs)


def test_build_cover_thumbnail_generates_file_and_reuses_cache(tmp_path, monkeypatch):
    cover_dir = tmp_path / "covers"
    cache_dir = tmp_path / "cache"
    cover_dir.mkdir()
    cache_dir.mkdir()
    source = cover_dir / "cover.png"
    Image.new("RGB", (600, 900), color=(20, 80, 140)).save(source)

    monkeypatch.setattr("application.cover_versioning.get_cover_dir", lambda: str(cover_dir))
    monkeypatch.setattr(thumbnail_service, "get_cache_root_dir", lambda: str(cache_dir))

    first_path, first_generated = thumbnail_service.build_cover_thumbnail("/static/cover/cover.png", 360)
    second_path, second_generated = thumbnail_service.build_cover_thumbnail("/static/cover/cover.png", 360)

    assert first_generated is True
    assert second_generated is False
    assert first_path == second_path
    assert Path(first_path).is_file()


def test_warm_cover_thumbnails_dedupes_cached_and_invalid_sources(tmp_path, monkeypatch):
    cached_target = tmp_path / "cached.jpg"
    cached_target.write_bytes(b"cached")
    missing_target = tmp_path / "missing.jpg"
    calls = []

    def fake_resolve_thumbnail_target(src, width):
        if src == "bad":
            raise CoverThumbnailError(404, "source cover not found")
        target_path = cached_target if src == "cached" else missing_target
        return str(tmp_path / f"{src}.source"), 360, f"key-{src}", str(target_path)

    def fake_build_cover_thumbnail(src, width):
        calls.append((src, width))
        return str(missing_target), True

    monkeypatch.setattr(thumbnail_service, "_resolve_thumbnail_target", fake_resolve_thumbnail_target)
    monkeypatch.setattr(thumbnail_service, "_get_warmup_executor", lambda: InlineExecutor())
    monkeypatch.setattr(thumbnail_service, "build_cover_thumbnail", fake_build_cover_thumbnail)
    thumbnail_service._warmup_pending.clear()

    stats = thumbnail_service.warm_cover_thumbnails(
        ["cached", "missing", "missing", "bad"],
        max_items=10,
    )

    assert stats == {
        "queued": 1,
        "cached": 1,
        "pending": 1,
        "invalid": 1,
        "queue_full": 0,
    }
    assert calls == [("missing", 360)]
    assert thumbnail_service._warmup_pending == set()


def test_warm_cover_thumbnails_for_items_uses_first_available_cover_key(monkeypatch):
    sources = []

    monkeypatch.setattr(
        thumbnail_service,
        "warm_cover_thumbnails",
        lambda values, width=360, max_items=None: sources.extend(values) or {"queued": len(sources)},
    )

    thumbnail_service.warm_cover_thumbnails_for_items(
        [
            {"cover_path_local": "/media/local.jpg", "cover_path": "/static/cover/remote.jpg"},
            {"cover_path": "/static/cover/fallback.jpg"},
            {"title": "missing cover"},
        ]
    )

    assert sources == ["/media/local.jpg", "/static/cover/fallback.jpg"]
