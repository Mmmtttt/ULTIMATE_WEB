from __future__ import annotations

from typing import Callable, Dict, List, Optional

from core.utils import get_current_time
from infrastructure.persistence.json_storage import JsonStorage


class JsonDocumentRepository:
    def __init__(self, file_path: str, root_key: str, count_key: str = ""):
        self._storage = JsonStorage(file_path)
        self._root_key = str(root_key or "").strip()
        self._count_key = str(count_key or "").strip()

    def read_document(self) -> Dict:
        payload = self._storage.read()
        if not isinstance(payload, dict):
            payload = {}
        items = payload.get(self._root_key, [])
        if not isinstance(items, list):
            items = []
        payload[self._root_key] = items
        return payload

    def read_items(self) -> List[dict]:
        return list(self.read_document().get(self._root_key, []))

    def write_items(self, items: List[dict]) -> bool:
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
