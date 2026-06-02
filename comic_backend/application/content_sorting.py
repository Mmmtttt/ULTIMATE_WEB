from __future__ import annotations

import random
import re
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


_NATURAL_TOKEN_RE = re.compile(r"(\d+)")


def _read_value(item: Any, *field_names: str) -> Any:
    for field_name in field_names:
        if isinstance(item, dict):
            value = item.get(field_name)
        else:
            value = getattr(item, field_name, None)
        if value not in (None, ""):
            return value
    return None


def _normalize_int(value: Any) -> Optional[int]:
    try:
        normalized = int(value)
    except (TypeError, ValueError):
        return None
    return normalized if normalized >= 0 else None


def natural_text_key(value: Any) -> Tuple[Any, ...]:
    text = str(value or "").strip().casefold()
    if not text:
        return ((1, ""),)

    key: List[Any] = []
    for chunk in _NATURAL_TOKEN_RE.split(text):
        if not chunk:
            continue
        if chunk.isdigit():
            key.append((0, int(chunk)))
        else:
            key.append((1, chunk))
    return tuple(key)


def _title_key(item: Any) -> Tuple[Any, ...]:
    return natural_text_key(
        _read_value(item, "title", "title_jp", "code", "id")
    )


def _id_key(item: Any) -> str:
    return str(_read_value(item, "id") or "").strip()


def _create_time_key(item: Any) -> str:
    return str(_read_value(item, "create_time") or "").strip()


def _string_field_key(item: Any, *field_names: str) -> str:
    return str(_read_value(item, *field_names) or "").strip()


def _score_key(item: Any) -> float:
    try:
        return float(_read_value(item, "score") or 0)
    except (TypeError, ValueError):
        return 0.0


def _read_status_key(item: Any) -> Tuple[int, float]:
    try:
        current_unit = int(_read_value(item, "current_page", "current_unit") or 0)
    except (TypeError, ValueError):
        current_unit = 0
    try:
        total_units = int(_read_value(item, "total_page", "total_units") or 0)
    except (TypeError, ValueError):
        total_units = 0

    is_read = 1 if total_units > 0 and current_unit >= total_units else 0
    return is_read, -_score_key(item)


def sort_custom_items(items: Sequence[Any]) -> List[Any]:
    safe_items = list(items or [])
    if not safe_items:
        return []

    with_order: List[Any] = []
    without_order: List[Any] = []
    for item in safe_items:
        if _normalize_int(_read_value(item, "custom_order")) is None:
            without_order.append(item)
        else:
            with_order.append(item)

    with_order.sort(
        key=lambda item: (
            _normalize_int(_read_value(item, "custom_order")) or 0,
            _title_key(item),
            _id_key(item),
        )
    )
    without_order.sort(
        key=lambda item: (
            _create_time_key(item),
            _title_key(item),
            _id_key(item),
        ),
        reverse=True,
    )
    return with_order + without_order


def sort_content_items(
    items: Sequence[Any],
    sort_type: str = "",
    sort_order: str = "desc",
) -> List[Any]:
    safe_items = list(items or [])
    normalized_sort_type = str(sort_type or "").strip().lower()
    reverse = str(sort_order or "desc").strip().lower() != "asc"

    if not normalized_sort_type or normalized_sort_type == "default":
        return safe_items

    if normalized_sort_type == "random":
        shuffled = list(safe_items)
        random.shuffle(shuffled)
        return shuffled

    if normalized_sort_type == "custom":
        return sort_custom_items(safe_items)

    if normalized_sort_type in {"name", "title"}:
        return sorted(
            safe_items,
            key=lambda item: (_title_key(item), _id_key(item)),
            reverse=reverse,
        )

    if normalized_sort_type == "create_time":
        return sorted(
            safe_items,
            key=lambda item: (_string_field_key(item, "create_time"), _title_key(item), _id_key(item)),
            reverse=reverse,
        )

    if normalized_sort_type == "score":
        return sorted(
            safe_items,
            key=lambda item: (_score_key(item), _title_key(item), _id_key(item)),
            reverse=reverse,
        )

    if normalized_sort_type in {"access_time", "read_time"}:
        return sorted(
            safe_items,
            key=lambda item: (
                _string_field_key(item, "last_access_time", "last_read_time"),
                _title_key(item),
                _id_key(item),
            ),
            reverse=reverse,
        )

    if normalized_sort_type == "date":
        return sorted(
            safe_items,
            key=lambda item: (_string_field_key(item, "date"), _title_key(item), _id_key(item)),
            reverse=reverse,
        )

    if normalized_sort_type == "read_status":
        return sorted(
            safe_items,
            key=lambda item: (_read_status_key(item), _title_key(item), _id_key(item)),
            reverse=reverse,
        )

    return safe_items


def normalize_custom_order_records(
    records: Sequence[Dict[str, Any]],
    preferred_ids: Optional[Iterable[str]] = None,
) -> Tuple[List[Dict[str, Any]], bool]:
    normalized_records = [
        dict(item or {})
        for item in (records or [])
        if isinstance(item, dict)
    ]
    if not normalized_records:
        return [], False

    record_by_id: Dict[str, Dict[str, Any]] = {}
    for record in normalized_records:
        record_id = str(record.get("id") or "").strip()
        if record_id:
            record_by_id[record_id] = record

    ordered_records: List[Dict[str, Any]]
    if preferred_ids is not None:
        ordered_records = []
        consumed_ids = set()
        for raw_id in preferred_ids:
            record_id = str(raw_id or "").strip()
            if not record_id or record_id in consumed_ids:
                continue
            record = record_by_id.get(record_id)
            if record is None:
                continue
            ordered_records.append(record)
            consumed_ids.add(record_id)

        remaining_records = [
            record
            for record in normalized_records
            if str(record.get("id") or "").strip() not in consumed_ids
        ]
        ordered_records.extend(sort_custom_items(remaining_records))
    else:
        ordered_records = sort_custom_items(normalized_records)

    changed = False
    for index, record in enumerate(ordered_records):
        if _normalize_int(record.get("custom_order")) != index:
            record["custom_order"] = index
            changed = True

    return ordered_records, changed
