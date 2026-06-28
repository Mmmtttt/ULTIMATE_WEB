from __future__ import annotations

import os
import threading
import time
from typing import Any, Dict, Iterable, List, Sequence, Tuple

from application.persisted_content_metadata import resolve_data_relative_path
from core.constants import (
    CACHE_ROOT_DIR,
    COMIC_DIR,
    COMIC_RECOMMENDATION_CACHE_DIR,
    DATA_DIR,
    LOCAL_PICTURES_DIR,
    LOGS_DIR,
    META_DIR,
    STATIC_DIR,
    VIDEO_DIR,
    VIDEO_RECOMMENDATION_CACHE_DIR,
)
from core.host_platform_fallback import infer_existing_host_comic_dir
from infrastructure.logger import error_logger
from infrastructure.persistence.repositories import (
    ComicJsonRepository,
    RecommendationJsonRepository,
    VideoJsonRepository,
    VideoRecommendationJsonRepository,
)
from infrastructure.recommendation_cache_manager import recommendation_cache_manager


_USAGE_CACHE_TTL_SECONDS = 20.0
_usage_cache_lock = threading.Lock()
_usage_cache: Dict[str, Tuple[float, Dict[str, Any]]] = {}


def invalidate_storage_usage_cache() -> None:
    with _usage_cache_lock:
        _usage_cache.clear()


def format_storage_size(size_bytes: int) -> str:
    try:
        size = max(0, int(size_bytes or 0))
    except (TypeError, ValueError):
        size = 0

    units = ("B", "KB", "MB", "GB", "TB")
    value = float(size)
    unit_index = 0
    while value >= 1024 and unit_index < len(units) - 1:
        value /= 1024
        unit_index += 1

    if unit_index == 0:
        return f"{int(value)} B"
    if value >= 100:
        return f"{value:.0f} {units[unit_index]}"
    if value >= 10:
        return f"{value:.1f} {units[unit_index]}"
    return f"{value:.2f} {units[unit_index]}"


def _empty_usage(reason: str = "") -> Dict[str, Any]:
    return {
        "size_bytes": 0,
        "file_count": 0,
        "is_symlink": False,
        "excluded_reason": reason,
    }


def _is_inside_data_dir(abs_path: str) -> bool:
    if not abs_path:
        return False
    try:
        data_root = os.path.abspath(DATA_DIR)
        target = os.path.abspath(abs_path)
        return os.path.commonpath([data_root, target]) == data_root
    except Exception:
        return False


def _resolve_static_or_media_url(raw_url: str) -> str:
    url = str(raw_url or "").strip()
    if not url:
        return ""

    if url.startswith("/media/"):
        relative = url[len("/media/") :].lstrip("/").replace("/", os.sep)
        candidate = os.path.abspath(os.path.join(DATA_DIR, relative))
        return candidate if _is_inside_data_dir(candidate) else ""

    if url.startswith("/static/"):
        relative = url[len("/static/") :].lstrip("/").replace("/", os.sep)
        candidate = os.path.abspath(os.path.join(STATIC_DIR, relative))
        return candidate if _is_inside_data_dir(candidate) else ""

    return ""


def _resolve_data_candidate(raw_path: str) -> str:
    value = str(raw_path or "").strip()
    if not value:
        return ""

    if value.startswith(("http://", "https://", "blob:", "data:")):
        return ""

    url_path = _resolve_static_or_media_url(value)
    if url_path:
        return url_path

    if os.path.isabs(value):
        try:
            candidate = os.path.abspath(os.path.expandvars(os.path.expanduser(value)))
        except Exception:
            return ""
        return candidate if _is_inside_data_dir(candidate) else ""

    relative_candidate = resolve_data_relative_path(value)
    return relative_candidate if relative_candidate and _is_inside_data_dir(relative_candidate) else ""


def get_path_usage(abs_path: str) -> Dict[str, Any]:
    path = str(abs_path or "").strip()
    if not path:
        return _empty_usage("missing")

    try:
        normalized = os.path.abspath(os.path.expandvars(os.path.expanduser(path)))
    except Exception:
        return _empty_usage("invalid_path")

    if not _is_inside_data_dir(normalized):
        return _empty_usage("outside_data_dir")

    now = time.monotonic()
    cache_key = os.path.normcase(normalized)
    with _usage_cache_lock:
        cached = _usage_cache.get(cache_key)
        if cached and (now - cached[0]) <= _USAGE_CACHE_TTL_SECONDS:
            return dict(cached[1])

    usage = _calculate_path_usage(normalized)
    with _usage_cache_lock:
        _usage_cache[cache_key] = (now, dict(usage))
    return usage


def _calculate_path_usage(abs_path: str) -> Dict[str, Any]:
    if not os.path.exists(abs_path):
        return _empty_usage("missing")

    if os.path.islink(abs_path):
        usage = _empty_usage("symlink")
        usage["is_symlink"] = True
        return usage

    if os.path.isfile(abs_path):
        try:
            return {
                "size_bytes": int(os.path.getsize(abs_path)),
                "file_count": 1,
                "is_symlink": False,
                "excluded_reason": "",
            }
        except OSError:
            return _empty_usage("unreadable")

    if not os.path.isdir(abs_path):
        return _empty_usage("unsupported_path")

    file_count = 0
    total_size = 0
    skipped_symlink = False
    for dirpath, dirnames, filenames in os.walk(abs_path, followlinks=False):
        safe_dirnames = []
        for dirname in dirnames:
            child_dir = os.path.join(dirpath, dirname)
            if os.path.islink(child_dir):
                skipped_symlink = True
                continue
            safe_dirnames.append(dirname)
        dirnames[:] = safe_dirnames

        for filename in filenames:
            file_path = os.path.join(dirpath, filename)
            if os.path.islink(file_path):
                skipped_symlink = True
                continue
            if not os.path.isfile(file_path):
                continue
            try:
                total_size += int(os.path.getsize(file_path))
                file_count += 1
            except OSError:
                continue

    return {
        "size_bytes": total_size,
        "file_count": file_count,
        "is_symlink": False,
        "excluded_reason": "contains_symlink" if skipped_symlink else "",
    }


def _payload_from_item(item: Any) -> Dict[str, Any]:
    if isinstance(item, dict):
        return dict(item)
    payload: Dict[str, Any] = {}
    if hasattr(item, "to_dict"):
        try:
            payload = dict(item.to_dict() or {})
        except Exception:
            payload = {}
    for key in (
        "storage_size_bytes",
        "storage_size_label",
        "storage_file_count",
        "storage_size_scope",
        "storage_is_soft_ref",
        "storage_excluded_reason",
    ):
        value = getattr(item, key, None)
        if value is not None:
            payload[key] = value
    return payload


def _apply_storage_fields(item: Any, fields: Dict[str, Any]) -> Any:
    if isinstance(item, dict):
        item.update(fields)
        return item
    for key, value in fields.items():
        try:
            setattr(item, key, value)
        except Exception:
            pass
    return item


def _dedupe_parent_paths(paths: Iterable[str]) -> List[str]:
    normalized_paths: List[str] = []
    seen = set()
    for raw_path in paths or []:
        path = str(raw_path or "").strip()
        if not path:
            continue
        try:
            normalized = os.path.abspath(path)
        except Exception:
            continue
        if not _is_inside_data_dir(normalized):
            continue
        if not os.path.exists(normalized):
            continue
        key = os.path.normcase(normalized)
        if key in seen:
            continue
        seen.add(key)
        normalized_paths.append(normalized)

    normalized_paths.sort(key=lambda item: len(os.path.normcase(item)))
    deduped: List[str] = []
    for candidate in normalized_paths:
        candidate_key = os.path.normcase(candidate)
        covered = False
        for existing in deduped:
            existing_key = os.path.normcase(existing)
            try:
                if os.path.commonpath([existing_key, candidate_key]) == existing_key:
                    covered = True
                    break
            except Exception:
                continue
        if not covered:
            deduped.append(candidate)
    return deduped


def _combine_path_usage(paths: Sequence[str], fallback_reason: str = "missing") -> Dict[str, Any]:
    safe_paths = _dedupe_parent_paths(paths)
    if not safe_paths:
        return _empty_usage(fallback_reason)

    total_size = 0
    total_files = 0
    reasons = []
    symlink_skipped = False
    for path in safe_paths:
        usage = get_path_usage(path)
        total_size += int(usage.get("size_bytes") or 0)
        total_files += int(usage.get("file_count") or 0)
        reason = str(usage.get("excluded_reason") or "").strip()
        if reason:
            reasons.append(reason)
        symlink_skipped = symlink_skipped or bool(usage.get("is_symlink"))

    return {
        "size_bytes": total_size,
        "file_count": total_files,
        "is_symlink": symlink_skipped,
        "excluded_reason": ",".join(dict.fromkeys(reasons)),
    }


def _storage_fields_from_usage(
    usage: Dict[str, Any],
    *,
    path_kind: str = "",
    scope: str = "managed",
    reason: str = "",
) -> Dict[str, Any]:
    size_bytes = int(usage.get("size_bytes") or 0)
    excluded_reason = reason or str(usage.get("excluded_reason") or "").strip()
    return {
        "storage_size_bytes": size_bytes,
        "storage_size_label": format_storage_size(size_bytes),
        "storage_file_count": int(usage.get("file_count") or 0),
        "storage_path_kind": str(path_kind or "").strip(),
        "storage_size_scope": scope,
        "storage_is_soft_ref": scope == "soft_ref",
        "storage_excluded_reason": excluded_reason,
    }


def _comic_local_paths(payload: Dict[str, Any]) -> Tuple[List[str], str]:
    path_kind = str(payload.get("storage_path_kind") or "").strip()
    paths: List[str] = []

    stored_relative = str(payload.get("storage_path_relative") or "").strip()
    if stored_relative:
        paths.append(resolve_data_relative_path(stored_relative))

    comic_id = str(payload.get("id") or "").strip()
    if comic_id:
        try:
            host_dir = infer_existing_host_comic_dir(
                comic_id,
                payload,
                comic_root=COMIC_DIR,
                local_root=LOCAL_PICTURES_DIR,
            )
            if host_dir:
                paths.append(host_dir)
        except Exception:
            pass

        try:
            from utils.file_parser import file_parser

            comic_dir = file_parser._get_comic_dir(comic_id)
            if comic_dir:
                paths.append(comic_dir)
        except Exception:
            pass

    return paths, path_kind


def _comic_preview_paths(payload: Dict[str, Any]) -> Tuple[List[str], str]:
    path_kind = str(payload.get("storage_path_kind") or "").strip() or "preview_cache_dir"
    paths: List[str] = []
    stored_relative = str(payload.get("storage_path_relative") or "").strip()
    if stored_relative:
        paths.append(resolve_data_relative_path(stored_relative))

    comic_id = str(payload.get("id") or "").strip()
    if comic_id:
        try:
            paths.append(recommendation_cache_manager._get_comic_cache_dir(comic_id))
        except Exception:
            pass
    return paths, path_kind


def _video_asset_paths(payload: Dict[str, Any]) -> List[str]:
    paths: List[str] = []
    for field_name in (
        "cover_path",
        "cover_path_local",
        "preview_video_local",
        "local_video_path",
    ):
        paths.append(_resolve_data_candidate(payload.get(field_name)))

    for url in payload.get("thumbnail_images_local") or []:
        paths.append(_resolve_data_candidate(url))
    return paths


def _video_local_paths(payload: Dict[str, Any]) -> Tuple[List[str], str]:
    path_kind = str(payload.get("storage_path_kind") or "").strip()
    paths: List[str] = []

    stored_relative = str(payload.get("storage_path_relative") or "").strip()
    if stored_relative:
        paths.append(resolve_data_relative_path(stored_relative))

    local_asset_dir = str(payload.get("local_asset_dir_name") or "").strip()
    if local_asset_dir:
        paths.append(_resolve_data_candidate(local_asset_dir))

    paths.extend(_video_asset_paths(payload))
    paths.append(_resolve_data_candidate(payload.get("local_source_path")))
    return paths, path_kind


def _video_preview_paths(payload: Dict[str, Any]) -> Tuple[List[str], str]:
    path_kind = str(payload.get("storage_path_kind") or "").strip() or "preview_asset_dir"
    paths: List[str] = []
    stored_relative = str(payload.get("storage_path_relative") or "").strip()
    if stored_relative:
        paths.append(resolve_data_relative_path(stored_relative))
    paths.extend(_video_asset_paths(payload))
    return paths, path_kind


def _has_external_source(payload: Dict[str, Any]) -> bool:
    for field_name in ("local_source_path", "import_source"):
        raw_value = str(payload.get(field_name) or "").strip()
        if not raw_value or raw_value.startswith(("http://", "https://", "/media/", "/static/")):
            continue
        if os.path.isabs(raw_value):
            try:
                if not _is_inside_data_dir(os.path.abspath(os.path.expandvars(os.path.expanduser(raw_value)))):
                    return True
            except Exception:
                return True
        elif str(payload.get("storage_path_kind") or "").strip().lower() == "source":
            return True
    return False


def calculate_content_storage_usage(
    item: Any,
    *,
    content_type: str,
    source: str,
) -> Dict[str, Any]:
    payload = _payload_from_item(item)
    content_key = str(content_type or "").strip().lower()
    source_key = str(source or "local").strip().lower()
    storage_mode = str(payload.get("storage_mode") or "").strip().lower()

    if storage_mode == "soft_ref":
        return _storage_fields_from_usage(
            _empty_usage("soft_ref"),
            path_kind=str(payload.get("storage_path_kind") or "").strip() or "soft_ref",
            scope="soft_ref",
            reason="soft_ref",
        )

    if content_key == "comic" and source_key == "preview":
        paths, path_kind = _comic_preview_paths(payload)
    elif content_key == "comic":
        paths, path_kind = _comic_local_paths(payload)
    elif content_key == "video" and source_key == "preview":
        paths, path_kind = _video_preview_paths(payload)
    else:
        paths, path_kind = _video_local_paths(payload)

    usage = _combine_path_usage(paths)
    if source_key == "local" and int(usage.get("size_bytes") or 0) <= 0 and _has_external_source(payload):
        return _storage_fields_from_usage(usage, path_kind=path_kind or "source", scope="external", reason="external_source")
    scope = "managed" if int(usage.get("size_bytes") or 0) > 0 or paths else "missing"
    return _storage_fields_from_usage(usage, path_kind=path_kind, scope=scope)


def annotate_content_storage_usage(
    items: Sequence[Any],
    *,
    content_type: str,
    source: str,
) -> Sequence[Any]:
    for item in items or []:
        fields = calculate_content_storage_usage(item, content_type=content_type, source=source)
        _apply_storage_fields(item, fields)
    return items


def annotate_comic_storage_usage(items: Sequence[Any], *, source: str = "local") -> Sequence[Any]:
    return annotate_content_storage_usage(items, content_type="comic", source=source)


def annotate_video_storage_usage(items: Sequence[Any], *, source: str = "local") -> Sequence[Any]:
    return annotate_content_storage_usage(items, content_type="video", source=source)


def _module_usage(paths: Sequence[str]) -> Dict[str, Any]:
    usage = _combine_path_usage(paths, fallback_reason="")
    return usage


def _module_payload(
    *,
    key: str,
    label: str,
    description: str,
    paths: Sequence[str],
    color: str,
    cache_type: str = "",
) -> Dict[str, Any]:
    usage = _module_usage(paths)
    size_bytes = int(usage.get("size_bytes") or 0)
    return {
        "key": key,
        "label": label,
        "description": description,
        "size_bytes": size_bytes,
        "size_label": format_storage_size(size_bytes),
        "file_count": int(usage.get("file_count") or 0),
        "color": color,
        "cache_type": cache_type,
        "clearable": bool(cache_type),
        "excluded_reason": str(usage.get("excluded_reason") or ""),
    }


def _is_path_covered(candidate: str, roots: Sequence[str]) -> bool:
    try:
        candidate_abs = os.path.normcase(os.path.abspath(candidate))
    except Exception:
        return False
    for root in roots or []:
        try:
            root_abs = os.path.normcase(os.path.abspath(root))
            if os.path.commonpath([root_abs, candidate_abs]) == root_abs:
                return True
        except Exception:
            continue
    return False


def _unknown_data_root_paths(covered_roots: Sequence[str]) -> List[str]:
    if not os.path.isdir(DATA_DIR):
        return []

    paths: List[str] = []
    try:
        entries = list(os.scandir(DATA_DIR))
    except OSError:
        return []

    for entry in entries:
        if _is_path_covered(entry.path, covered_roots):
            continue
        paths.append(entry.path)
    return paths


def _item_title(payload: Dict[str, Any]) -> str:
    return str(
        payload.get("title")
        or payload.get("title_jp")
        or payload.get("code")
        or payload.get("id")
        or ""
    ).strip()


def _build_ranked_items(
    items: Sequence[Any],
    *,
    content_type: str,
    source: str,
    limit: int,
) -> List[Dict[str, Any]]:
    annotated = list(annotate_content_storage_usage(list(items or []), content_type=content_type, source=source))
    ranked = sorted(
        annotated,
        key=lambda item: int(_payload_from_item(item).get("storage_size_bytes") or 0),
        reverse=True,
    )
    results = []
    for item in ranked[: max(1, int(limit or 10))]:
        payload = _payload_from_item(item)
        size_bytes = int(payload.get("storage_size_bytes") or 0)
        results.append(
            {
                "id": str(payload.get("id") or ""),
                "title": _item_title(payload),
                "size_bytes": size_bytes,
                "size_label": format_storage_size(size_bytes),
                "file_count": int(payload.get("storage_file_count") or 0),
                "content_type": content_type,
                "source": source,
                "path_kind": str(payload.get("storage_path_kind") or ""),
                "excluded_reason": str(payload.get("storage_excluded_reason") or ""),
                "is_soft_ref": bool(payload.get("storage_is_soft_ref")),
                "platform": str(payload.get("platform") or payload.get("plugin_name") or payload.get("plugin_id") or ""),
                "cover_path": str(payload.get("cover_path_local") or payload.get("cover_path") or ""),
            }
        )
    return results


def _safe_repo_items(factory) -> List[Any]:
    try:
        return [item for item in factory().get_all() if not bool(getattr(item, "is_deleted", False))]
    except Exception as exc:
        error_logger.error(f"读取存储概览数据失败: {exc}")
        return []


def _load_storage_overview_items() -> Tuple[List[Any], List[Any], List[Any], List[Any]]:
    return (
        _safe_repo_items(ComicJsonRepository),
        _safe_repo_items(RecommendationJsonRepository),
        _safe_repo_items(VideoJsonRepository),
        _safe_repo_items(VideoRecommendationJsonRepository),
    )


def build_storage_ranking(category: str, limit: int = 12) -> Dict[str, Any]:
    normalized_category = str(category or "").strip().lower()
    local_comics, preview_comics, local_videos, preview_videos = _load_storage_overview_items()
    category_map = {
        "local_comics": (local_comics, "comic", "local"),
        "local_videos": (local_videos, "video", "local"),
        "preview_comics": (preview_comics, "comic", "preview"),
        "preview_videos": (preview_videos, "video", "preview"),
    }
    if normalized_category not in category_map:
        normalized_category = "local_comics"

    items, content_type, source = category_map[normalized_category]
    return {
        "category": normalized_category,
        "items": _build_ranked_items(items, content_type=content_type, source=source, limit=limit),
        "total": len(items),
    }


def build_storage_overview() -> Dict[str, Any]:
    modules = [
        _module_payload(
            key="local_comics",
            label="本地漫画",
            description="data/comic 内的漫画图片与章节文件，跳过软连接目标",
            paths=[COMIC_DIR],
            color="#59a0ff",
        ),
        _module_payload(
            key="local_videos",
            label="本地视频",
            description="data/video 内的视频源文件、截图和本地预览资源",
            paths=[VIDEO_DIR],
            color="#00a875",
        ),
        _module_payload(
            key="comic_preview_cache",
            label="漫画预览缓存",
            description="预览库已缓存的漫画页面，可安全清理后重新缓存",
            paths=[COMIC_RECOMMENDATION_CACHE_DIR],
            color="#f59a22",
            cache_type="comic_preview_cache",
        ),
        _module_payload(
            key="video_preview_page_cache",
            label="视频预览缓存",
            description="预览库视频的本地封面、截图与预览视频缓存",
            paths=[VIDEO_RECOMMENDATION_CACHE_DIR],
            color="#de5b6d",
            cache_type="video_preview_page_cache",
        ),
        _module_payload(
            key="cache",
            label="临时数据缓存",
            description="订阅、封面和运行期临时缓存，可安全清理",
            paths=[CACHE_ROOT_DIR],
            color="#7a88ff",
            cache_type="cache",
        ),
        _module_payload(
            key="metadata_static",
            label="元数据与封面",
            description="数据库、日志、静态封面等应用运行资料",
            paths=[META_DIR, STATIC_DIR, LOGS_DIR],
            color="#8b98ad",
        ),
    ]

    covered_roots = [
        COMIC_DIR,
        VIDEO_DIR,
        COMIC_RECOMMENDATION_CACHE_DIR,
        VIDEO_RECOMMENDATION_CACHE_DIR,
        CACHE_ROOT_DIR,
        META_DIR,
        STATIC_DIR,
        LOGS_DIR,
    ]
    unknown_usage = _combine_path_usage(_unknown_data_root_paths(covered_roots), fallback_reason="")
    module_total = sum(int(module.get("size_bytes") or 0) for module in modules)
    module_file_count = sum(int(module.get("file_count") or 0) for module in modules)
    other_size = int(unknown_usage.get("size_bytes") or 0)
    other_file_count = int(unknown_usage.get("file_count") or 0)
    total_size = module_total + other_size
    total_file_count = module_file_count + other_file_count
    if other_size > 0 or other_file_count > 0:
        modules.append(
            {
                "key": "other",
                "label": "其他文件",
                "description": "data 目录内未归入常规模块的文件",
                "size_bytes": other_size,
                "size_label": format_storage_size(other_size),
                "file_count": other_file_count,
                "color": "#6e7b98",
                "cache_type": "",
                "clearable": False,
                "excluded_reason": "",
            }
        )

    return {
        "total": {
            "size_bytes": total_size,
            "size_label": format_storage_size(total_size),
            "file_count": total_file_count,
        },
        "modules": modules,
        "rankings": {},
        "notes": [
            "统计只计算 data 目录内的真实文件；软连接及其目标文件不会计入。",
            "缓存模块可以清理，本地漫画/视频模块只提供查看和排序，不会删除真实媒体文件。",
        ],
    }
