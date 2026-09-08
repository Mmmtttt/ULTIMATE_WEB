from __future__ import annotations

from typing import Any, Dict, List

from core.utils import get_preview_pages, normalize_total_page


def extract_remote_total_page(meta_data: dict) -> int:
    if not isinstance(meta_data, dict):
        return 0

    albums = meta_data.get("albums") or []
    if not albums:
        return 0

    first_album = albums[0] if isinstance(albums[0], dict) else {}
    for value in (
        first_album.get("pages"),
        first_album.get("pages_count"),
        first_album.get("page_count"),
        first_album.get("total_page"),
    ):
        pages = normalize_total_page(value, default=0)
        if pages > 0:
            return pages
    return 0


def first_remote_album(meta_data: dict) -> Dict[str, Any]:
    if not isinstance(meta_data, dict):
        return {}
    albums = meta_data.get("albums") or []
    if not albums or not isinstance(albums[0], dict):
        return {}
    return dict(albums[0])


def build_update_check_payload(
    *,
    content_id: str,
    id_key: str,
    db_total_page: int,
    known_page_count: int,
    remote_total_page: int,
    known_page_key: str,
) -> Dict[str, Any]:
    normalized_db_total = normalize_total_page(db_total_page, default=0)
    normalized_known_pages = normalize_total_page(known_page_count, default=0)
    normalized_remote_total = normalize_total_page(remote_total_page, default=0)
    return {
        id_key: content_id,
        "db_total_page": normalized_db_total,
        known_page_key: normalized_known_pages,
        "remote_total_page": normalized_remote_total,
        "has_update": normalized_remote_total > max(normalized_db_total, normalized_known_pages),
        "can_update": True,
    }


def apply_remote_album_metadata(
    target: Any,
    remote_meta: dict,
    *,
    include_preview_pages: bool = False,
) -> List[str]:
    album = first_remote_album(remote_meta)
    if not album:
        return []

    changed_fields: List[str] = []
    field_map = {
        "title": album.get("title"),
        "title_jp": album.get("title_jp"),
        "author": album.get("author"),
        "creator": album.get("author"),
        "desc": album.get("desc") or album.get("description"),
        "cover_path": album.get("cover_url") or album.get("cover_path"),
    }
    for field_name, raw_value in field_map.items():
        if not hasattr(target, field_name):
            continue
        value = str(raw_value or "").strip()
        if value and getattr(target, field_name, "") != value:
            setattr(target, field_name, value)
            changed_fields.append(field_name)

    remote_total_page = extract_remote_total_page(remote_meta)
    if remote_total_page > 0 and hasattr(target, "total_page"):
        if normalize_total_page(getattr(target, "total_page", 0), default=0) != remote_total_page:
            target.total_page = remote_total_page
            if hasattr(target, "current_page"):
                target.current_page = min(max(1, getattr(target, "current_page", 1)), remote_total_page)
            changed_fields.append("total_page")

    if include_preview_pages and remote_total_page > 0 and hasattr(target, "preview_pages"):
        next_preview_pages = get_preview_pages(remote_total_page)
        if getattr(target, "preview_pages", []) != next_preview_pages:
            target.preview_pages = next_preview_pages
            changed_fields.append("preview_pages")

    return changed_fields
