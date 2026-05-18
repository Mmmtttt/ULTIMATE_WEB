from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from core.utils import get_current_time
from infrastructure.persistence.json_storage import JsonStorage


class JsonDocumentRepository:
    def __init__(
        self,
        file_path: str,
        root_key: str,
        count_key: str = "",
        root_type: str = "list",
    ):
        self._storage = JsonStorage(file_path)
        self._root_key = str(root_key or "").strip()
        self._count_key = str(count_key or "").strip()
        normalized_root_type = str(root_type or "list").strip().lower()
        if normalized_root_type not in {"list", "dict"}:
            raise ValueError("root_type must be 'list' or 'dict'")
        self._root_type = normalized_root_type

    def _empty_root(self) -> Any:
        return {} if self._root_type == "dict" else []

    def _normalize_root(self, value: Any) -> Any:
        if self._root_type == "dict":
            return value if isinstance(value, dict) else {}
        return value if isinstance(value, list) else []

    def read_document(self) -> Dict:
        payload = self._storage.read()
        if not isinstance(payload, dict):
            payload = {}
        payload[self._root_key] = self._normalize_root(payload.get(self._root_key, self._empty_root()))
        return payload

    def _normalize_document(self, payload: Dict) -> Dict:
        document = dict(payload or {})
        root_value = self._normalize_root(document.get(self._root_key, self._empty_root()))
        document[self._root_key] = root_value
        if self._count_key and isinstance(root_value, list):
            document[self._count_key] = len(root_value)
        return document

    def write_document(self, payload: Dict) -> bool:
        return self._storage.write(self._normalize_document(payload))

    def atomic_update_document(self, update_func: Callable[[Dict], Optional[Dict]]) -> bool:
        def update_doc(payload: Dict) -> Optional[Dict]:
            document = self.read_document() if payload is None else self._normalize_document(payload)
            updated_document = update_func(document)
            if updated_document is None:
                return None
            return self._normalize_document(updated_document)

        return self._storage.atomic_update(update_doc)

    def read_items(self) -> List[dict]:
        if self._root_type != "list":
            raise TypeError("read_items is only available for list repositories")
        return list(self.read_document().get(self._root_key, []))

    def write_items(self, items: List[dict]) -> bool:
        if self._root_type != "list":
            raise TypeError("write_items is only available for list repositories")
        normalized_items = [dict(item or {}) for item in (items or []) if isinstance(item, dict)]

        def update_doc(payload: Dict) -> Dict:
            payload = dict(payload or {})
            payload[self._root_key] = normalized_items
            if self._count_key:
                payload[self._count_key] = len(normalized_items)
            payload["last_updated"] = get_current_time()
            return payload

        return self._storage.atomic_update(update_doc)

    def update_items(self, update_func: Callable[[List[dict]], Optional[List[dict]]]) -> bool:
        if self._root_type != "list":
            raise TypeError("update_items is only available for list repositories")
        def update_doc(payload: Dict) -> Optional[Dict]:
            payload = dict(payload or {})
            items = payload.get(self._root_key, [])
            if not isinstance(items, list):
                items = []
            updated_items = update_func(list(items))
            if updated_items is None:
                return None
            normalized_items = [dict(item or {}) for item in updated_items if isinstance(item, dict)]
            payload[self._root_key] = normalized_items
            if self._count_key:
                payload[self._count_key] = len(normalized_items)
            payload["last_updated"] = get_current_time()
            return payload

        return self._storage.atomic_update(update_doc)
