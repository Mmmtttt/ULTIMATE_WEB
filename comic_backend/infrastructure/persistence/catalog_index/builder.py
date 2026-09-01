from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any, Dict, Iterable, List, Tuple

from core.storage_layout import get_meta_dir


CATALOG_DOCUMENTS: Tuple[Tuple[str, str, str, str], ...] = (
    ("comic_local", "comics_database.json", "comics", "comic:local"),
    ("comic_preview", "recommendations_database.json", "recommendations", "comic:preview"),
    ("video_local", "videos_database.json", "videos", "video:local"),
    ("video_preview", "video_recommendations_database.json", "video_recommendations", "video:preview"),
    ("tags", "tags_database.json", "tags", "tags"),
)

CONTENT_DOCUMENT_BY_FILE: Dict[str, Dict[str, str]] = {
    "comics_database.json": {
        "logical_name": "comic_local",
        "media_type": "comic",
        "source": "local",
        "data_key": "comics",
    },
    "recommendations_database.json": {
        "logical_name": "comic_preview",
        "media_type": "comic",
        "source": "preview",
        "data_key": "recommendations",
    },
    "videos_database.json": {
        "logical_name": "video_local",
        "media_type": "video",
        "source": "local",
        "data_key": "videos",
    },
    "video_recommendations_database.json": {
        "logical_name": "video_preview",
        "media_type": "video",
        "source": "preview",
        "data_key": "video_recommendations",
    },
}


def content_document_spec_for_file(file_name: str) -> Dict[str, str] | None:
    return CONTENT_DOCUMENT_BY_FILE.get(os.path.basename(str(file_name or "")).lower())


def _document_path(file_name: str) -> str:
    return os.path.join(get_meta_dir(), file_name)


def document_stats() -> Dict[str, Dict[str, Any]]:
    stats: Dict[str, Dict[str, Any]] = {}
    for logical_name, file_name, _data_key, _scope in CATALOG_DOCUMENTS:
        path = _document_path(file_name)
        try:
            stat = os.stat(path)
            stats[logical_name] = {
                "path": path,
                "size_bytes": int(stat.st_size),
                "mtime_ns": int(stat.st_mtime_ns),
            }
        except FileNotFoundError:
            stats[logical_name] = {
                "path": path,
                "size_bytes": 0,
                "mtime_ns": 0,
            }
    return stats


def load_document(file_name: str) -> Dict[str, Any]:
    path = _document_path(file_name)
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as fp:
        return json.load(fp)


def _normalize_text(value: Any) -> str:
    return str(value or "").strip()


def _normalize_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _normalize_score(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _normalize_custom_order(value: Any) -> int | None:
    try:
        normalized = int(value)
    except (TypeError, ValueError):
        return None
    return normalized if normalized >= 0 else None


def _normalize_string_list(values: Iterable[Any] | None) -> List[str]:
    normalized: List[str] = []
    seen = set()
    for raw in values or []:
        value = _normalize_text(raw)
        if not value or value in seen:
            continue
        seen.add(value)
        normalized.append(value)
    return normalized


def _append_search_part(parts: List[str], value: Any) -> None:
    if isinstance(value, dict):
        for key in ("id", "name", "title", "code"):
            _append_search_part(parts, value.get(key))
        return
    if isinstance(value, (list, tuple, set)):
        for item in value:
            _append_search_part(parts, item)
        return
    text = _normalize_text(value).lower()
    if text:
        parts.append(text)


def _build_tag_map() -> Dict[str, str]:
    payload = load_document("tags_database.json")
    tag_map: Dict[str, str] = {}
    for item in payload.get("tags") or []:
        tag_id = _normalize_text(item.get("id"))
        tag_name = _normalize_text(item.get("name"))
        if tag_id:
            tag_map[tag_id] = tag_name or tag_id
    return tag_map


def build_tag_map() -> Dict[str, str]:
    return _build_tag_map()


def _extract_item(media_type: str, source: str, index: int, raw: Dict[str, Any], tag_map: Dict[str, str]) -> Dict[str, Any]:
    item_id = _normalize_text(raw.get("id"))
    title = _normalize_text(raw.get("title"))
    title_jp = _normalize_text(raw.get("title_jp"))
    creator = _normalize_text(raw.get("author") or raw.get("creator"))
    actors = _normalize_string_list(raw.get("actors") or [])
    tag_ids = _normalize_string_list(raw.get("tag_ids") or [])
    list_ids = _normalize_string_list(raw.get("list_ids") or [])
    current_unit = _normalize_int(raw.get("current_page", raw.get("current_unit", 1)), 1)
    total_units = _normalize_int(raw.get("total_page", raw.get("total_units", 0)), 0)

    search_parts: List[str] = []
    for value in (
        item_id,
        raw.get("code"),
        title,
        title_jp,
        creator,
        raw.get("desc"),
        actors,
        tag_ids,
        [tag_map.get(tag_id, tag_id) for tag_id in tag_ids],
    ):
        _append_search_part(search_parts, value)

    author_names = _normalize_string_list([creator, *actors])

    score = _normalize_score(raw.get("score"))
    if (media_type == "comic" or source == "preview") and score is None:
        score = 8.0

    return {
        "item_key": f"{media_type}:{source}:{item_id}",
        "media_type": media_type,
        "source": source,
        "source_order": index,
        "item_id": item_id,
        "title": title,
        "title_jp": title_jp,
        "creator": creator,
        "actors_text": "\n".join(actors),
        "code": _normalize_text(raw.get("code")),
        "desc": _normalize_text(raw.get("desc")),
        "search_text": "\n".join(search_parts),
        "score": score,
        "current_unit": current_unit,
        "total_units": total_units,
        "create_time": _normalize_text(raw.get("create_time")),
        "last_access_time": _normalize_text(raw.get("last_read_time") or raw.get("last_access_time")),
        "date": _normalize_text(raw.get("date")),
        "is_deleted": 1 if bool(raw.get("is_deleted", False)) else 0,
        "cover_path": _normalize_text(raw.get("cover_path")),
        "cover_path_local": _normalize_text(raw.get("cover_path_local")),
        "custom_order": _normalize_custom_order(raw.get("custom_order")),
        "payload_json": json.dumps(raw, ensure_ascii=False, separators=(",", ":")),
        "tag_ids": tag_ids,
        "list_ids": list_ids,
        "author_names": author_names,
    }


def build_index_item(media_type: str, source: str, index: int, raw: Dict[str, Any], tag_map: Dict[str, str]) -> Dict[str, Any]:
    return _extract_item(media_type, source, index, raw, tag_map)


def rebuild_index(conn) -> Dict[str, Any]:
    tag_map = _build_tag_map()
    documents = [
        ("comic", "local", "comics_database.json", "comics"),
        ("comic", "preview", "recommendations_database.json", "recommendations"),
        ("video", "local", "videos_database.json", "videos"),
        ("video", "preview", "video_recommendations_database.json", "video_recommendations"),
    ]
    indexed_at = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    inserted_count = 0

    with conn:
        conn.execute("DELETE FROM catalog_author")
        conn.execute("DELETE FROM catalog_list")
        conn.execute("DELETE FROM catalog_tag")
        conn.execute("DELETE FROM catalog_item")

        for media_type, source, file_name, data_key in documents:
            payload = load_document(file_name)
            for index, raw in enumerate(payload.get(data_key) or []):
                if not isinstance(raw, dict):
                    continue
                item = _extract_item(media_type, source, index, raw, tag_map)
                if not item["item_id"]:
                    continue
                conn.execute(
                    """
                    INSERT OR REPLACE INTO catalog_item (
                        item_key, media_type, source, source_order, item_id,
                        title, title_jp, creator, actors_text, code, desc,
                        search_text, score, current_unit, total_units,
                        create_time, last_access_time, date, is_deleted,
                        cover_path, cover_path_local, custom_order, payload_json
                    ) VALUES (
                        :item_key, :media_type, :source, :source_order, :item_id,
                        :title, :title_jp, :creator, :actors_text, :code, :desc,
                        :search_text, :score, :current_unit, :total_units,
                        :create_time, :last_access_time, :date, :is_deleted,
                        :cover_path, :cover_path_local, :custom_order, :payload_json
                    )
                    """,
                    item,
                )
                conn.executemany(
                    "INSERT OR IGNORE INTO catalog_tag(item_key, tag_id) VALUES (?, ?)",
                    [(item["item_key"], tag_id) for tag_id in item["tag_ids"]],
                )
                conn.executemany(
                    "INSERT OR IGNORE INTO catalog_list(item_key, list_id) VALUES (?, ?)",
                    [(item["item_key"], list_id) for list_id in item["list_ids"]],
                )
                conn.executemany(
                    "INSERT OR IGNORE INTO catalog_author(item_key, name) VALUES (?, ?)",
                    [(item["item_key"], name) for name in item["author_names"]],
                )
                inserted_count += 1

        for logical_name, stat in document_stats().items():
            conn.execute(
                """
                INSERT OR REPLACE INTO catalog_index_meta(logical_name, path, size_bytes, mtime_ns, indexed_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    logical_name,
                    stat["path"],
                    stat["size_bytes"],
                    stat["mtime_ns"],
                    indexed_at,
                ),
            )

    return {"indexed_count": inserted_count, "indexed_at": indexed_at}
