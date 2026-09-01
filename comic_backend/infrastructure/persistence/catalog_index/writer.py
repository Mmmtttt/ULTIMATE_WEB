from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Dict, List

from infrastructure.logger import app_logger, error_logger

from .builder import (
    build_index_item,
    build_tag_map,
    content_document_spec_for_file,
    document_stats,
    rebuild_index,
)
from .connection import catalog_index_connection, get_catalog_index_path
from .schema import catalog_search_available


def sync_after_json_write(file_name: str, old_data: Dict[str, Any] | None, new_data: Dict[str, Any] | None) -> Dict[str, Any]:
    if not _index_sync_enabled():
        return {"synced": False, "reason": "disabled"}

    normalized_file_name = os.path.basename(str(file_name or "")).lower()
    if normalized_file_name == "tags_database.json":
        return _rebuild_for_tag_change()

    spec = content_document_spec_for_file(normalized_file_name)
    if spec is None:
        return {"synced": False, "reason": "unsupported_file"}

    if not os.path.exists(get_catalog_index_path()):
        return {"synced": False, "reason": "index_missing"}

    old_items = _normalize_items((old_data or {}).get(spec["data_key"]))
    new_items = _normalize_items((new_data or {}).get(spec["data_key"]))
    return _sync_content_document(spec, old_items, new_items)


def _index_sync_enabled() -> bool:
    value = str(os.environ.get("CATALOG_INDEX_ENABLED", "1")).strip().lower()
    return value not in {"0", "false", "no", "off"}


def _normalize_items(value: Any) -> List[Dict[str, Any]]:
    return [dict(item or {}) for item in (value or []) if isinstance(item, dict)]


def _item_id(item: Dict[str, Any]) -> str:
    return str(item.get("id") or "").strip()


def _rebuild_for_tag_change() -> Dict[str, Any]:
    started_at = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    try:
        with catalog_index_connection() as conn:
            result = rebuild_index(conn)
        result.update({"synced": True, "mode": "full_rebuild", "reason": "tags_changed", "started_at": started_at})
        return result
    except Exception as exc:
        error_logger.warning(f"标签变化后重建 catalog index 失败: {exc}")
        return {"synced": False, "reason": "rebuild_failed", "error": str(exc)}


def _sync_content_document(spec: Dict[str, str], old_items: List[Dict[str, Any]], new_items: List[Dict[str, Any]]) -> Dict[str, Any]:
    old_by_id = {_item_id(item): (index, item) for index, item in enumerate(old_items) if _item_id(item)}
    new_by_id = {_item_id(item): (index, item) for index, item in enumerate(new_items) if _item_id(item)}

    removed_ids = sorted(set(old_by_id) - set(new_by_id))
    changed_items: List[tuple[int, Dict[str, Any]]] = []
    for item_id, (index, item) in new_by_id.items():
        old_entry = old_by_id.get(item_id)
        if old_entry is None or old_entry[0] != index or old_entry[1] != item:
            changed_items.append((index, item))

    if not removed_ids and not changed_items:
        return _update_document_meta(spec)

    tag_map = build_tag_map()
    media_type = spec["media_type"]
    source = spec["source"]
    item_key_prefix = f"{media_type}:{source}:"

    try:
        with catalog_index_connection() as conn:
            with conn:
                search_available = catalog_search_available(conn)
                for item_id in removed_ids:
                    item_key = f"{item_key_prefix}{item_id}"
                    conn.execute("DELETE FROM catalog_author WHERE item_key = ?", (item_key,))
                    conn.execute("DELETE FROM catalog_list WHERE item_key = ?", (item_key,))
                    conn.execute("DELETE FROM catalog_tag WHERE item_key = ?", (item_key,))
                    if search_available:
                        conn.execute("DELETE FROM catalog_item_search WHERE item_key = ?", (item_key,))
                    conn.execute("DELETE FROM catalog_item WHERE item_key = ?", (item_key,))

                for index, raw in changed_items:
                    item = build_index_item(media_type, source, index, raw, tag_map)
                    if not item["item_id"]:
                        continue
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO catalog_item (
                            item_key, media_type, source, source_order, item_id,
                            title, title_jp, title_sort_key, creator, actors_text, code, desc,
                            search_text, score, current_unit, total_units,
                            create_time, last_access_time, date, is_deleted,
                            cover_path, cover_path_local, custom_order, payload_json
                        ) VALUES (
                            :item_key, :media_type, :source, :source_order, :item_id,
                            :title, :title_jp, :title_sort_key, :creator, :actors_text, :code, :desc,
                            :search_text, :score, :current_unit, :total_units,
                            :create_time, :last_access_time, :date, :is_deleted,
                            :cover_path, :cover_path_local, :custom_order, :payload_json
                        )
                        """,
                        item,
                    )
                    conn.execute("DELETE FROM catalog_author WHERE item_key = ?", (item["item_key"],))
                    conn.execute("DELETE FROM catalog_list WHERE item_key = ?", (item["item_key"],))
                    conn.execute("DELETE FROM catalog_tag WHERE item_key = ?", (item["item_key"],))
                    if search_available:
                        conn.execute("DELETE FROM catalog_item_search WHERE item_key = ?", (item["item_key"],))
                        conn.execute(
                            "INSERT INTO catalog_item_search(item_key, search_text) VALUES (?, ?)",
                            (item["item_key"], item["search_text"]),
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

                _write_document_meta(conn, spec)

        result = {
            "synced": True,
            "mode": "incremental",
            "logical_name": spec["logical_name"],
            "changed_count": len(changed_items),
            "removed_count": len(removed_ids),
        }
        app_logger.info(f"Catalog index 增量同步完成: {result}")
        return result
    except Exception as exc:
        error_logger.warning(f"Catalog index 增量同步失败: {exc}")
        return {"synced": False, "reason": "sync_failed", "error": str(exc)}


def _update_document_meta(spec: Dict[str, str]) -> Dict[str, Any]:
    try:
        with catalog_index_connection() as conn:
            with conn:
                _write_document_meta(conn, spec)
        return {
            "synced": True,
            "mode": "meta_only",
            "logical_name": spec["logical_name"],
            "changed_count": 0,
            "removed_count": 0,
        }
    except Exception as exc:
        error_logger.warning(f"Catalog index 元数据同步失败: {exc}")
        return {"synced": False, "reason": "meta_sync_failed", "error": str(exc)}


def _write_document_meta(conn, spec: Dict[str, str]) -> None:
    stat = document_stats().get(spec["logical_name"])
    if not stat:
        return
    conn.execute(
        """
        INSERT OR REPLACE INTO catalog_index_meta(logical_name, path, size_bytes, mtime_ns, indexed_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            spec["logical_name"],
            stat["path"],
            stat["size_bytes"],
            stat["mtime_ns"],
            datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        ),
    )
