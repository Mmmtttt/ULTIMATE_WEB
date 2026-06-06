from __future__ import annotations

import math
from typing import Any, Callable, Dict, Iterable, List, Sequence


def read_value(item: Any, *field_names: str) -> Any:
    for field_name in field_names:
        if isinstance(item, dict):
            value = item.get(field_name)
        else:
            value = getattr(item, field_name, None)
        if value not in (None, ""):
            return value
    return None


def normalize_string_list(values: Iterable[Any] | None) -> List[str]:
    normalized: List[str] = []
    for value in values or []:
        text = str(value or "").strip()
        if text:
            normalized.append(text)
    return normalized


def append_search_candidate(parts: List[str], value: Any) -> None:
    if isinstance(value, (list, tuple, set)):
        for item in value:
            append_search_candidate(parts, item)
        return
    if isinstance(value, dict):
        append_search_candidate(parts, value.get("name"))
        append_search_candidate(parts, value.get("title"))
        append_search_candidate(parts, value.get("code"))
        return

    text = str(value or "").strip().lower()
    if text:
        parts.append(text)


def build_search_haystack(item: Any, *, tag_map: Dict[str, str] | None = None) -> str:
    parts: List[str] = []
    append_search_candidate(parts, read_value(item, "id"))
    append_search_candidate(parts, read_value(item, "code"))
    append_search_candidate(parts, read_value(item, "title"))
    append_search_candidate(parts, read_value(item, "title_jp"))
    append_search_candidate(parts, read_value(item, "author", "creator", "actor"))
    append_search_candidate(parts, read_value(item, "desc"))
    append_search_candidate(parts, read_value(item, "actors", "authors"))

    tag_ids = read_value(item, "tag_ids") or []
    append_search_candidate(parts, tag_ids)
    if isinstance(tag_map, dict) and tag_ids:
        append_search_candidate(parts, [tag_map.get(tag_id, tag_id) for tag_id in tag_ids])

    return "\n".join(parts)


def matches_keyword(item: Any, keyword: str = "", *, tag_map: Dict[str, str] | None = None) -> bool:
    normalized = str(keyword or "").strip().lower()
    if not normalized:
        return True

    tokens = [token for token in normalized.split() if token]
    if not tokens:
        return True

    haystack = build_search_haystack(item, tag_map=tag_map)
    return all(token in haystack for token in tokens)


def extract_item_authors(item: Any) -> List[str]:
    values: List[str] = []

    def push(raw: Any) -> None:
        text = str(raw or "").strip()
        if text:
            values.append(text)

    push(read_value(item, "author"))
    push(read_value(item, "creator"))
    push(read_value(item, "actor"))

    actors = read_value(item, "actors") or []
    authors = read_value(item, "authors") or []
    for raw in actors:
        push(raw)
    for raw in authors:
        push(raw)

    deduped: List[str] = []
    seen = set()
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        deduped.append(value)
    return deduped


def extract_available_authors(items: Sequence[Any] | None) -> List[str]:
    author_set = set()
    for item in items or []:
        for author in extract_item_authors(item):
            author_set.add(author)
    return sorted(author_set)


def normalize_page(value: Any, default: int = 1) -> int:
    try:
        page = int(value)
    except (TypeError, ValueError):
        page = default
    return max(1, page)


def normalize_page_size(value: Any, default: int = 24, maximum: int = 120) -> int:
    try:
        size = int(value)
    except (TypeError, ValueError):
        size = default
    size = max(1, size)
    return min(size, maximum)


def paginate_items(items: Sequence[Any] | None, page: int, page_size: int) -> Dict[str, Any]:
    safe_items = list(items or [])
    normalized_page = normalize_page(page, 1)
    normalized_page_size = normalize_page_size(page_size)
    total = len(safe_items)
    total_pages = max(1, math.ceil(total / normalized_page_size))
    current_page = min(normalized_page, total_pages)
    start = (current_page - 1) * normalized_page_size
    end = start + normalized_page_size
    return {
        "items": safe_items[start:end],
        "total": total,
        "page": current_page,
        "page_size": normalized_page_size,
        "total_pages": total_pages,
    }


def build_paginated_payload(
    items: Sequence[Any] | None,
    *,
    page: int,
    page_size: int,
    serializer: Callable[[Any], Dict[str, Any]],
    extra: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    pagination = paginate_items(items, page, page_size)
    payload = {
        "items": [serializer(item) for item in pagination["items"]],
        "total": pagination["total"],
        "page": pagination["page"],
        "page_size": pagination["page_size"],
        "total_pages": pagination["total_pages"],
    }
    if extra:
        payload.update(extra)
    return payload
