from __future__ import annotations

import json
import math
import os
import time
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Sequence

from infrastructure.logger import app_logger, error_logger

from .builder import document_stats, rebuild_index
from .connection import catalog_index_connection, get_catalog_index_path
from .schema import catalog_search_available


SUPPORTED_SORT_TYPES = {
    "",
    "default",
    "create_time",
    "score",
    "page_count",
    "total_page",
    "pages",
    "access_time",
    "read_time",
    "date",
    "custom",
}


@dataclass
class CatalogQueryResult:
    items: List[Dict[str, Any]]
    total: int
    page: int
    page_size: int
    total_pages: int
    available_authors: List[str]
    rebuilt: bool
    elapsed_ms: float
    search_index: str


class CatalogIndex:
    @staticmethod
    def enabled() -> bool:
        value = str(os.environ.get("CATALOG_INDEX_ENABLED", "1")).strip().lower()
        return value not in {"0", "false", "no", "off"}

    @staticmethod
    def search_enabled() -> bool:
        value = str(os.environ.get("CATALOG_SEARCH_INDEX_ENABLED", "1")).strip().lower()
        return value not in {"0", "false", "no", "off"}

    @staticmethod
    def can_query(sort_type: str | None) -> bool:
        normalized = str(sort_type or "").strip().lower()
        return normalized in SUPPORTED_SORT_TYPES

    def status(self) -> Dict[str, Any]:
        path = get_catalog_index_path()
        with catalog_index_connection() as conn:
            stale = self._is_stale(conn)
            search_available = self.search_enabled() and catalog_search_available(conn)
            rows = conn.execute(
                """
                SELECT media_type, source, COUNT(*) AS total
                FROM catalog_item
                GROUP BY media_type, source
                ORDER BY media_type, source
                """
            ).fetchall()
            return {
                "enabled": self.enabled(),
                "path": path,
                "exists": os.path.exists(path),
                "stale": stale,
                "search_index": "fts5_trigram_like" if search_available else "like_scan",
                "counts": [dict(row) for row in rows],
            }

    def rebuild(self) -> Dict[str, Any]:
        with catalog_index_connection() as conn:
            return rebuild_index(conn)

    def query_local_items(
        self,
        *,
        media_type: str,
        source: str = "local",
        sort_type: str | None = "",
        sort_order: str = "desc",
        min_score: float | None = None,
        max_score: float | None = None,
        include_deleted: bool = False,
        keyword: str = "",
        include_tags: Iterable[Any] | None = None,
        exclude_tags: Iterable[Any] | None = None,
        authors: Iterable[Any] | None = None,
        list_ids: Iterable[Any] | None = None,
        unread_only: bool = False,
        page: int = 1,
        page_size: int = 24,
        include_available_authors: bool = False,
    ) -> CatalogQueryResult | None:
        if not self.enabled() or not self.can_query(sort_type):
            return None

        started = time.perf_counter()
        normalized_page = normalize_page(page, 1)
        normalized_page_size = normalize_page_size(page_size)
        rebuilt = False

        with catalog_index_connection() as conn:
            if self._is_stale(conn):
                rebuild_index(conn)
                rebuilt = True

            search_available = self.search_enabled() and catalog_search_available(conn)
            where, params, search_index = self._build_where(
                media_type=media_type,
                source=source,
                include_deleted=include_deleted,
                min_score=min_score,
                max_score=max_score,
                keyword=keyword,
                include_tags=include_tags,
                exclude_tags=exclude_tags,
                authors=authors,
                list_ids=list_ids,
                unread_only=unread_only,
                search_available=search_available,
            )
            total = int(conn.execute(f"SELECT COUNT(*) FROM catalog_item i WHERE {where}", params).fetchone()[0])
            total_pages = max(1, math.ceil(total / normalized_page_size))
            current_page = min(normalized_page, total_pages)
            offset = (current_page - 1) * normalized_page_size
            order_by = self._build_order_by(sort_type, sort_order)

            item_rows = conn.execute(
                f"""
                SELECT payload_json
                FROM catalog_item i
                WHERE {where}
                ORDER BY {order_by}
                LIMIT ? OFFSET ?
                """,
                [*params, normalized_page_size, offset],
            ).fetchall()
            items = [json.loads(row["payload_json"]) for row in item_rows]
            available_authors = self._load_available_authors(conn, where, params) if include_available_authors else []

        elapsed_ms = (time.perf_counter() - started) * 1000
        if rebuilt:
            app_logger.info(f"Catalog index rebuilt before query: media_type={media_type}, elapsed_ms={elapsed_ms:.2f}")
        return CatalogQueryResult(
            items=items,
            total=total,
            page=current_page,
            page_size=normalized_page_size,
            total_pages=total_pages,
            available_authors=available_authors,
            rebuilt=rebuilt,
            elapsed_ms=elapsed_ms,
            search_index=search_index,
        )

    def _is_stale(self, conn) -> bool:
        try:
            rows = conn.execute(
                "SELECT logical_name, size_bytes, mtime_ns FROM catalog_index_meta"
            ).fetchall()
            indexed = {row["logical_name"]: (int(row["size_bytes"]), int(row["mtime_ns"])) for row in rows}
            current = document_stats()
            for logical_name, stat in current.items():
                if indexed.get(logical_name) != (int(stat["size_bytes"]), int(stat["mtime_ns"])):
                    return True
            return not indexed
        except Exception as exc:
            error_logger.warning(f"检查 catalog index 状态失败，将重建: {exc}")
            return True

    def _build_where(
        self,
        *,
        media_type: str,
        source: str,
        include_deleted: bool,
        min_score: float | None,
        max_score: float | None,
        keyword: str,
        include_tags: Iterable[Any] | None,
        exclude_tags: Iterable[Any] | None,
        authors: Iterable[Any] | None,
        list_ids: Iterable[Any] | None,
        unread_only: bool,
        search_available: bool,
    ) -> tuple[str, List[Any], str]:
        clauses: List[str] = ["i.media_type = ?", "i.source = ?"]
        params: List[Any] = [media_type, source]

        if not include_deleted:
            clauses.append("i.is_deleted = 0")
        if min_score is not None:
            clauses.append("i.score IS NOT NULL AND i.score >= ?")
            params.append(float(min_score))
        if max_score is not None:
            clauses.append("i.score IS NOT NULL AND i.score <= ?")
            params.append(float(max_score))
        if unread_only:
            clauses.append("i.current_unit = 1")

        normalized_include_tags = normalize_string_list(include_tags)
        if normalized_include_tags:
            placeholders = ",".join("?" for _ in normalized_include_tags)
            clauses.append(
                "i.item_key IN ("
                "SELECT ct.item_key FROM catalog_tag ct "
                f"WHERE ct.tag_id IN ({placeholders}) "
                "GROUP BY ct.item_key HAVING COUNT(DISTINCT ct.tag_id) = ?"
                ")"
            )
            params.extend(normalized_include_tags)
            params.append(len(set(normalized_include_tags)))

        for tag_id in normalize_string_list(exclude_tags):
            clauses.append(
                "NOT EXISTS (SELECT 1 FROM catalog_tag ct WHERE ct.item_key = i.item_key AND ct.tag_id = ?)"
            )
            params.append(tag_id)

        normalized_authors = normalize_string_list(authors)
        if normalized_authors:
            placeholders = ",".join("?" for _ in normalized_authors)
            clauses.append(
                f"i.item_key IN (SELECT ca.item_key FROM catalog_author ca WHERE ca.name IN ({placeholders}))"
            )
            params.extend(normalized_authors)

        normalized_list_ids = normalize_string_list(list_ids)
        if normalized_list_ids:
            placeholders = ",".join("?" for _ in normalized_list_ids)
            clauses.append(
                f"i.item_key IN (SELECT cl.item_key FROM catalog_list cl WHERE cl.list_id IN ({placeholders}))"
            )
            params.extend(normalized_list_ids)

        tokens = [token for token in str(keyword or "").strip().lower().split() if token]
        use_search_index = should_use_fts_search(
            tokens,
            search_available=search_available,
            include_tags=normalized_include_tags,
            authors=normalized_authors,
            list_ids=normalized_list_ids,
        )
        for token in tokens:
            if use_search_index:
                clauses.append(
                    "i.item_key IN ("
                    "SELECT cs.item_key FROM catalog_item_search cs "
                    "WHERE cs.search_text LIKE ?"
                    ")"
                )
            else:
                clauses.append("i.search_text LIKE ?")
            params.append(f"%{token}%")

        if not tokens:
            search_index = "none"
        elif use_search_index:
            search_index = "fts5_trigram_like"
        else:
            search_index = "like_scan"
        return " AND ".join(clauses), params, search_index

    def _build_order_by(self, sort_type: str | None, sort_order: str) -> str:
        normalized_sort_type = str(sort_type or "").strip().lower()
        direction = "ASC" if str(sort_order or "desc").strip().lower() == "asc" else "DESC"

        if normalized_sort_type in {"", "default"}:
            return "i.source_order ASC"
        if normalized_sort_type == "score":
            return f"COALESCE(i.score, 0) {direction}, i.title {direction}, i.item_id {direction}"
        if normalized_sort_type == "create_time":
            return f"i.create_time {direction}, i.title {direction}, i.item_id {direction}"
        if normalized_sort_type in {"access_time", "read_time"}:
            return f"i.last_access_time {direction}, i.title {direction}, i.item_id {direction}"
        if normalized_sort_type in {"page_count", "total_page", "pages"}:
            return f"i.total_units {direction}, i.title {direction}, i.item_id {direction}"
        if normalized_sort_type == "date":
            return f"i.date {direction}, i.title {direction}, i.item_id {direction}"
        if normalized_sort_type == "custom":
            return "CASE WHEN i.custom_order IS NULL THEN 1 ELSE 0 END ASC, i.custom_order ASC, i.create_time DESC, i.title ASC, i.item_id ASC"
        return "i.source_order ASC"

    def _load_available_authors(self, conn, where: str, params: Sequence[Any]) -> List[str]:
        rows = conn.execute(
            f"""
            SELECT DISTINCT ca.name
            FROM catalog_author ca
            JOIN catalog_item i ON i.item_key = ca.item_key
            WHERE {where} AND ca.name <> ''
            ORDER BY ca.name ASC
            """,
            list(params),
        ).fetchall()
        return [str(row["name"]) for row in rows]


def normalize_string_list(values: Iterable[Any] | None) -> List[str]:
    normalized: List[str] = []
    for value in values or []:
        text = str(value or "").strip()
        if text:
            normalized.append(text)
    return normalized


def should_use_fts_search(
    tokens: Sequence[str],
    *,
    search_available: bool,
    include_tags: Sequence[str],
    authors: Sequence[str],
    list_ids: Sequence[str],
) -> bool:
    if not search_available or not tokens:
        return False
    if include_tags or authors or list_ids:
        return False
    return all(len(token) >= 3 for token in tokens)


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
