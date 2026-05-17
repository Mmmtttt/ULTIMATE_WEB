from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

from core.enums import ContentType


def normalize_tag_content_type(value: Any, default: ContentType = ContentType.COMIC) -> ContentType:
    if isinstance(value, ContentType):
        return value
    normalized = str(value or "").strip().lower()
    if normalized == ContentType.VIDEO.value:
        return ContentType.VIDEO
    if normalized == ContentType.COMIC.value:
        return ContentType.COMIC
    return default


def get_content_type_label(content_type: Any) -> str:
    normalized = normalize_tag_content_type(content_type)
    return "视频" if normalized == ContentType.VIDEO else "漫画"


def validate_tag_ids_for_content_type(
    tag_repo: Any,
    tag_ids: Iterable[Any],
    expected_content_type: ContentType,
) -> Tuple[List[str], Optional[str]]:
    normalized_ids: List[str] = []
    seen: set[str] = set()

    for raw_tag_id in tag_ids or []:
        tag_id = str(raw_tag_id or "").strip()
        if not tag_id or tag_id in seen:
            continue
        seen.add(tag_id)

        tag = tag_repo.get_by_id(tag_id)
        if not tag:
            return [], f"标签不存在: {tag_id}"

        actual_content_type = normalize_tag_content_type(getattr(tag, "content_type", None))
        if actual_content_type != expected_content_type:
            tag_name = str(getattr(tag, "name", "") or "").strip()
            display_name = f"{tag_name} ({tag_id})" if tag_name else tag_id
            return [], (
                f"标签类型不匹配: {display_name} 属于{get_content_type_label(actual_content_type)}标签，"
                f"不能绑定到{get_content_type_label(expected_content_type)}内容"
            )

        normalized_ids.append(tag_id)

    return normalized_ids, None


def filter_tag_ids_by_type_lookup(
    tag_ids: Iterable[Any],
    expected_content_type: ContentType,
    type_lookup: Dict[str, Any] | None = None,
    *,
    drop_unknown: bool = False,
) -> List[str]:
    lookup = type_lookup if isinstance(type_lookup, dict) else {}
    normalized_ids: List[str] = []
    seen: set[str] = set()

    for raw_tag_id in tag_ids or []:
        tag_id = str(raw_tag_id or "").strip()
        if not tag_id or tag_id in seen:
            continue
        seen.add(tag_id)
        if drop_unknown and tag_id not in lookup:
            continue
        actual = normalize_tag_content_type(lookup.get(tag_id), default=expected_content_type)
        if actual != expected_content_type:
            continue
        normalized_ids.append(tag_id)

    return normalized_ids


def filter_tag_ids_by_resolver(
    tag_ids: Iterable[Any],
    expected_content_type: ContentType,
    resolve_type: Callable[[str], Any],
) -> List[str]:
    normalized_ids: List[str] = []
    seen: set[str] = set()

    for raw_tag_id in tag_ids or []:
        tag_id = str(raw_tag_id or "").strip()
        if not tag_id or tag_id in seen:
            continue
        seen.add(tag_id)
        actual = normalize_tag_content_type(resolve_type(tag_id), default=expected_content_type)
        if actual != expected_content_type:
            continue
        normalized_ids.append(tag_id)

    return normalized_ids
