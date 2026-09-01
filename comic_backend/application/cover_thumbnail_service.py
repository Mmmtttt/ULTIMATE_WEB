from __future__ import annotations

import hashlib
import os
import tempfile
import threading
from typing import Any, Tuple
from urllib.parse import urlsplit

from PIL import Image, ImageOps, UnidentifiedImageError

from application.cover_versioning import DEFAULT_COVER_THUMBNAIL_WIDTH, resolve_local_media_file
from core.storage_layout import get_cache_root_dir


ALLOWED_THUMBNAIL_WIDTHS = (160, 240, 320, 360, 480, 640)
THUMBNAIL_CACHE_DIR_NAME = "cover_thumbnails"
RESAMPLE_LANCZOS = getattr(getattr(Image, "Resampling", Image), "LANCZOS")

_locks_guard = threading.Lock()
_locks: dict[str, threading.Lock] = {}


class CoverThumbnailError(Exception):
    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.message = message


def build_cover_thumbnail(src: Any, width: Any = DEFAULT_COVER_THUMBNAIL_WIDTH) -> Tuple[str, bool]:
    source_path = _resolve_source_path(src)
    if not source_path:
        raise CoverThumbnailError(404, "source cover not found")

    safe_width = _normalize_width(width)
    try:
        source_stat = os.stat(source_path)
    except OSError:
        raise CoverThumbnailError(404, "source cover not found")

    version = str(source_stat.st_mtime_ns)
    cache_key = _build_cache_key(source_path, version, safe_width)
    cache_dir = os.path.join(get_cache_root_dir(), THUMBNAIL_CACHE_DIR_NAME, str(safe_width))
    target_path = os.path.join(cache_dir, f"{cache_key}.jpg")

    if os.path.isfile(target_path):
        return target_path, False

    lock = _lock_for(cache_key)
    with lock:
        if os.path.isfile(target_path):
            return target_path, False
        os.makedirs(cache_dir, exist_ok=True)
        _write_thumbnail(source_path, target_path, safe_width)
        return target_path, True


def _resolve_source_path(src: Any) -> str:
    text = str(src or "").strip()
    if not text:
        return ""
    parsed = urlsplit(text)
    if parsed.scheme or parsed.netloc:
        return ""
    return resolve_local_media_file(parsed.path)


def _normalize_width(width: Any) -> int:
    try:
        requested = int(width)
    except (TypeError, ValueError):
        requested = DEFAULT_COVER_THUMBNAIL_WIDTH
    if requested <= 0:
        requested = DEFAULT_COVER_THUMBNAIL_WIDTH
    return min(ALLOWED_THUMBNAIL_WIDTHS, key=lambda allowed: abs(allowed - requested))


def _build_cache_key(source_path: str, version: str, width: int) -> str:
    raw = f"{os.path.abspath(source_path)}|{version}|{width}"
    return hashlib.sha1(raw.encode("utf-8", errors="ignore")).hexdigest()


def _lock_for(cache_key: str) -> threading.Lock:
    with _locks_guard:
        lock = _locks.get(cache_key)
        if lock is None:
            lock = threading.Lock()
            _locks[cache_key] = lock
        return lock


def _write_thumbnail(source_path: str, target_path: str, width: int) -> None:
    temp_handle = tempfile.NamedTemporaryFile(
        prefix=".cover-thumb-",
        suffix=".tmp",
        dir=os.path.dirname(target_path),
        delete=False,
    )
    temp_path = temp_handle.name
    temp_handle.close()
    try:
        with Image.open(source_path) as image:
            image = ImageOps.exif_transpose(image)
            image.thumbnail((width, width * 4), RESAMPLE_LANCZOS)
            if image.mode not in ("RGB", "L"):
                image = image.convert("RGB")
            image.save(temp_path, "JPEG", quality=82, optimize=True, progressive=True)
        os.replace(temp_path, target_path)
    except UnidentifiedImageError:
        _remove_temp_file(temp_path)
        raise CoverThumbnailError(415, "unsupported cover image")
    except OSError as exc:
        _remove_temp_file(temp_path)
        raise CoverThumbnailError(500, f"thumbnail generation failed: {exc}")


def _remove_temp_file(path: str) -> None:
    try:
        if os.path.exists(path):
            os.remove(path)
    except OSError:
        pass
