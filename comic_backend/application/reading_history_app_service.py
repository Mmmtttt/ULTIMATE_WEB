from __future__ import annotations

from typing import Any, Dict, Mapping, Optional

from core.constants import READING_HISTORY_JSON_FILE
from core.utils import get_current_time
from infrastructure.common.result import ServiceResult
from infrastructure.logger import error_logger
from infrastructure.persistence.json_storage import JsonStorage
from infrastructure.persistence.repositories.comic_repository_impl import ComicJsonRepository
from infrastructure.persistence.repositories.recommendation_repository_impl import RecommendationJsonRepository
from infrastructure.persistence.repositories.video_repository_impl import VideoJsonRepository
from infrastructure.persistence.repositories.video_recommendation_repository_impl import VideoRecommendationJsonRepository


class ReadingHistoryAppService:
    """Maintain lightweight local/preview visit history for comics and videos."""

    MAX_ITEMS_PER_TYPE = 30
    VALID_CONTENT_TYPES = {"comic", "video"}
    VALID_SOURCES = {"local", "preview"}

    def __init__(
        self,
        storage: Optional[JsonStorage] = None,
        comic_repository: Optional[Any] = None,
        recommendation_repository: Optional[Any] = None,
        video_repository: Optional[Any] = None,
        video_recommendation_repository: Optional[Any] = None,
    ):
        self._storage = storage or JsonStorage(READING_HISTORY_JSON_FILE)
        self._repositories: Mapping[tuple[str, str], Any] = {
            ("comic", "local"): comic_repository or ComicJsonRepository(),
            ("comic", "preview"): recommendation_repository or RecommendationJsonRepository(),
            ("video", "local"): video_repository or VideoJsonRepository(),
            ("video", "preview"): video_recommendation_repository or VideoRecommendationJsonRepository(),
        }

    def list_history(self, content_type: str) -> ServiceResult:
        normalized_type = self._normalize_content_type(content_type)
        if not normalized_type:
            return ServiceResult.error("content_type 必须是 comic 或 video")

        try:
            data = self._normalize_data(self._storage.read())
            entries = data["history"].get(normalized_type, [])
            items = []
            for entry in entries:
                item = self._hydrate_entry(normalized_type, entry)
                if item:
                    items.append(item)
            return ServiceResult.ok(
                {
                    "content_type": normalized_type,
                    "items": items,
                    "total": len(items),
                    "limit": self.MAX_ITEMS_PER_TYPE,
                }
            )
        except Exception as exc:
            error_logger.error(f"读取阅读记录失败: {exc}")
            return ServiceResult.error("读取阅读记录失败")

    def record_visit(self, content_type: str, content_id: str, source: str = "local") -> ServiceResult:
        normalized_type = self._normalize_content_type(content_type)
        normalized_source = self._normalize_source(source)
        normalized_id = str(content_id or "").strip()

        if not normalized_type:
            return ServiceResult.error("content_type 必须是 comic 或 video")
        if not normalized_source:
            return ServiceResult.error("source 必须是 local 或 preview")
        if not normalized_id:
            return ServiceResult.error("缺少内容 ID")

        content = self._get_content(normalized_type, normalized_source, normalized_id)
        if content is None:
            return ServiceResult.error("内容不存在，未写入阅读记录")

        visited_at = get_current_time()

        def update_data(data: Dict[str, Any]) -> Dict[str, Any]:
            normalized_data = self._normalize_data(data)
            items = list(normalized_data["history"].get(normalized_type, []))
            items = [
                item
                for item in items
                if not (
                    str(item.get("id") or "") == normalized_id
                    and str(item.get("source") or "local") == normalized_source
                )
            ]
            items.insert(
                0,
                {
                    "id": normalized_id,
                    "source": normalized_source,
                    "visited_at": visited_at,
                },
            )
            normalized_data["history"][normalized_type] = items[: self.MAX_ITEMS_PER_TYPE]
            normalized_data["last_updated"] = visited_at
            return normalized_data

        try:
            success = self._storage.atomic_update(update_data)
            if not success:
                return ServiceResult.error("写入阅读记录失败")
            item = self._hydrate_entry(
                normalized_type,
                {"id": normalized_id, "source": normalized_source, "visited_at": visited_at},
            )
            return ServiceResult.ok(item)
        except Exception as exc:
            error_logger.error(f"写入阅读记录失败: {exc}")
            return ServiceResult.error("写入阅读记录失败")

    def _normalize_content_type(self, content_type: str) -> str:
        value = str(content_type or "").strip().lower()
        return value if value in self.VALID_CONTENT_TYPES else ""

    def _normalize_source(self, source: str) -> str:
        value = str(source or "local").strip().lower()
        return value if value in self.VALID_SOURCES else ""

    def _normalize_data(self, data: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        normalized = dict(data or {})
        history = normalized.get("history")
        if not isinstance(history, dict):
            history = {}
        normalized["history"] = {
            "comic": list(history.get("comic") or []),
            "video": list(history.get("video") or []),
        }
        return normalized

    def _get_content(self, content_type: str, source: str, content_id: str) -> Optional[Any]:
        repository = self._repositories.get((content_type, source))
        if repository is None:
            return None
        return repository.get_by_id(content_id)

    def _hydrate_entry(self, content_type: str, entry: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        content_id = str(entry.get("id") or "").strip()
        source = self._normalize_source(entry.get("source") or "local")
        if not content_id or not source:
            return None

        content = self._get_content(content_type, source, content_id)
        if content is None:
            return None

        item = content.to_dict() if hasattr(content, "to_dict") else dict(content)
        item["id"] = content_id
        item["source"] = source
        item["content_type"] = content_type
        item["visited_at"] = str(entry.get("visited_at") or "")
        return item
