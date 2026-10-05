from __future__ import annotations

import hashlib
import os
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Iterable, Tuple
from urllib.parse import urlsplit

from PIL import Image, ImageOps, UnidentifiedImageError

from application.cover_versioning import DEFAULT_COVER_THUMBNAIL_WIDTH, resolve_local_media_file
from core.storage_layout import get_cache_root_dir
from infrastructure.logger import app_logger, error_logger


ALLOWED_THUMBNAIL_WIDTHS = (160, 240, 320, 360, 480, 640)
THUMBNAIL_CACHE_DIR_NAME = "cover_thumbnails"
RESAMPLE_LANCZOS = getattr(getattr(Image, "Resampling", Image), "LANCZOS")

_locks_guard = threading.Lock()
_locks: dict[str, threading.Lock] = {}
_warmup_guard = threading.Lock()
_warmup_pending: set[str] = set()
_warmup_executor: ThreadPoolExecutor | None = None


class CoverThumbnailError(Exception):
    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.message = message


def build_cover_thumbnail(src: Any, width: Any = DEFAULT_COVER_THUMBNAIL_WIDTH) -> Tuple[str, bool]:
    source_path, safe_width, cache_key, target_path = _resolve_thumbnail_target(src, width)

    if os.path.isfile(target_path):
        return target_path, False

    lock = _lock_for(cache_key)
    with lock:
        if os.path.isfile(target_path):
            return target_path, False
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        _write_thumbnail(source_path, target_path, safe_width)
        return target_path, True


def warm_cover_thumbnails(
    sources: Iterable[Any],
    width: Any = DEFAULT_COVER_THUMBNAIL_WIDTH,
    *,
    max_items: int | None = None,
) -> dict[str, int]:
    """Queue missing local cover thumbnails without blocking the response path."""
    limit = _normalize_warmup_limit(max_items)
    pending_limit = _normalize_positive_int(os.environ.get("COVER_THUMBNAIL_WARMUP_MAX_PENDING"), 256)
    stats = {"queued": 0, "cached": 0, "pending": 0, "invalid": 0, "queue_full": 0}
    seen_keys: set[str] = set()

    for source in sources or []:
        if sum((stats["queued"], stats["cached"], stats["pending"], stats["invalid"])) >= limit:
            break
        try:
            _source_path, safe_width, cache_key, target_path = _resolve_thumbnail_target(source, width)
        except CoverThumbnailError:
            stats["invalid"] += 1
            continue

        if cache_key in seen_keys:
            stats["pending"] += 1
            continue
        seen_keys.add(cache_key)

        if os.path.isfile(target_path):
            stats["cached"] += 1
            continue

        with _warmup_guard:
            if cache_key in _warmup_pending:
                stats["pending"] += 1
                continue
            if len(_warmup_pending) >= pending_limit:
                stats["queue_full"] += 1
                break
            _warmup_pending.add(cache_key)

        _get_warmup_executor().submit(_warm_thumbnail_task, source, safe_width, cache_key)
        stats["queued"] += 1

    if stats["queued"]:
        app_logger.info(f"已排队预热封面缩略图: {stats}")
    return stats


def warm_cover_thumbnails_for_items(
    items: Iterable[dict],
    *,
    width: Any = DEFAULT_COVER_THUMBNAIL_WIDTH,
    max_items: int | None = None,
    preferred_keys: Iterable[str] = ("cover_path_local", "cover_path"),
) -> dict[str, int]:
    sources = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        for key in preferred_keys:
            value = str(item.get(key) or "").strip()
            if value:
                sources.append(value)
                break
    return warm_cover_thumbnails(sources, width=width, max_items=max_items)


def _resolve_thumbnail_target(src: Any, width: Any) -> Tuple[str, int, str, str]:
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
    return source_path, safe_width, cache_key, target_path


def _warm_thumbnail_task(src: Any, width: int, cache_key: str) -> None:
    try:
        build_cover_thumbnail(src, width)
    except CoverThumbnailError as exc:
        app_logger.debug(f"封面缩略图预热跳过: {exc.message}")
    except Exception as exc:
        error_logger.warning(f"封面缩略图预热失败: {exc}")
    finally:
        with _warmup_guard:
            _warmup_pending.discard(cache_key)


def _get_warmup_executor() -> ThreadPoolExecutor:
    global _warmup_executor
    with _warmup_guard:
        if _warmup_executor is None:
            workers = _normalize_positive_int(os.environ.get("COVER_THUMBNAIL_WARMUP_WORKERS"), 2)
            _warmup_executor = ThreadPoolExecutor(
                max_workers=min(workers, 4),
                thread_name_prefix="cover-thumb-warmup",
            )
        return _warmup_executor


def _normalize_warmup_limit(value: Any) -> int:
    default = _normalize_positive_int(os.environ.get("COVER_THUMBNAIL_WARMUP_LIMIT"), 48)
    if value is None:
        return default
    return _normalize_positive_int(value, default)


def _normalize_positive_int(value: Any, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(1, parsed)


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
