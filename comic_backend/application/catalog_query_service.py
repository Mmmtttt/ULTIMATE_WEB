from __future__ import annotations

from typing import Any, Callable, Dict, Iterable

from application.list_query_support import normalize_page, normalize_page_size
from infrastructure.logger import error_logger
from infrastructure.persistence.catalog_index import CatalogIndex


class CatalogQueryService:
    def __init__(self, index: CatalogIndex | None = None):
        self._index = index or CatalogIndex()

    def query_local_page(
        self,
        *,
        media_type: str,
        source: str = "local",
        serializer: Callable[[Dict[str, Any]], Dict[str, Any]],
        sort_type: str | None = "",
        sort_order: str = "desc",
        min_score: float | None = None,
        max_score: float | None = None,
        keyword: str = "",
        include_tags: Iterable[Any] | None = None,
        exclude_tags: Iterable[Any] | None = None,
        authors: Iterable[Any] | None = None,
        list_ids: Iterable[Any] | None = None,
        unread_only: bool = False,
        page: int = 1,
        page_size: int = 24,
        include_available_authors: bool = False,
    ) -> Dict[str, Any] | None:
        try:
            result = self._index.query_local_items(
                media_type=media_type,
                source=source,
                sort_type=sort_type,
                sort_order=sort_order,
                min_score=min_score,
                max_score=max_score,
                keyword=keyword,
                include_tags=include_tags,
                exclude_tags=exclude_tags,
                authors=authors,
                list_ids=list_ids,
                unread_only=unread_only,
                page=page,
                page_size=page_size,
                include_available_authors=include_available_authors,
            )
            if result is None:
                return None
            return {
                "items": [serializer(item) for item in result.items],
                "total": result.total,
                "page": result.page,
                "page_size": result.page_size,
                "total_pages": result.total_pages,
                "available_authors": result.available_authors if include_available_authors else [],
                "performance": {
                    "index": "sqlite",
                    "index_rebuilt": result.rebuilt,
                    "search_index": result.search_index,
                    "elapsed_ms": round(result.elapsed_ms, 3),
                },
            }
        except Exception as exc:
            error_logger.warning(f"Catalog index query failed, fallback to JSON path: {exc}")
            return None

    @staticmethod
    def empty_page(page: int = 1, page_size: int = 24) -> Dict[str, Any]:
        normalized_page = normalize_page(page, 1)
        normalized_page_size = normalize_page_size(page_size)
        return {
            "items": [],
            "total": 0,
            "page": normalized_page,
            "page_size": normalized_page_size,
            "total_pages": 1,
            "available_authors": [],
        }
