from __future__ import annotations

from typing import Any, Dict

from protocol.base import ProtocolProvider
from lib.javbus_adapter import JavbusAdapter as PluginJavbusAdapter


class JavbusProvider(ProtocolProvider):
    def normalize_config(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        normalized = dict(payload or {})
        normalized.setdefault("enabled", True)
        return normalized

    def get_query_status(self, config: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "configured": bool((config or {}).get("enabled", False)),
            "message": "" if (config or {}).get("enabled", False) else "JAVBUS 平台未启用",
            "missing_fields": [],
        }

    def _get_adapter(self, params: Dict[str, Any]):
        return PluginJavbusAdapter(params.get("existing_tags") or [])

    def execute(self, capability: str, params: Dict[str, Any], context: Dict[str, Any], config: Dict[str, Any]):
        adapter = self._get_adapter(params or {})
        if capability == "catalog.search":
            return adapter.search_videos(
                str(params.get("keyword") or ""),
                page=int(params.get("page", 1) or 1),
                max_pages=int(params.get("max_pages", 1) or 1),
            )
        if capability == "catalog.detail":
            return adapter.get_video_detail(str(params.get("video_id") or ""))
        if capability == "person.search":
            return adapter.search_actor(str(params.get("actor_name") or ""))
        if capability == "person.works":
            return adapter.get_actor_works(
                str(params.get("actor_id") or ""),
                page=int(params.get("page", 1) or 1),
                max_pages=int(params.get("max_pages", 1) or 1),
            )
        if capability == "health.query.status":
            return self.get_query_status(config or {})
        raise ValueError(f"unsupported capability: {capability}")
