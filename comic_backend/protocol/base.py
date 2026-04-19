from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass(frozen=True)
class PluginManifest:
    raw: Dict[str, Any]
    path: str

    @property
    def protocol_version(self) -> str:
        return str(self.raw.get("protocol_version") or "").strip()

    @property
    def plugin(self) -> Dict[str, Any]:
        return dict(self.raw.get("plugin") or {})

    @property
    def plugin_id(self) -> str:
        return str(self.plugin.get("id") or "").strip()

    @property
    def name(self) -> str:
        return str(self.plugin.get("name") or self.plugin_id).strip()

    @property
    def version(self) -> str:
        return str(self.plugin.get("version") or "").strip()

    @property
    def entrypoint(self) -> str:
        return str(self.plugin.get("entrypoint") or "").strip()

    @property
    def config_key(self) -> str:
        return str(self.plugin.get("config_key") or "").strip()

    @property
    def media_types(self) -> List[str]:
        return [str(item or "").strip() for item in (self.raw.get("media_types") or []) if str(item or "").strip()]

    @property
    def capability_entries(self) -> List[Dict[str, Any]]:
        return [dict(item or {}) for item in (self.raw.get("capabilities") or []) if isinstance(item, dict)]

    @property
    def capability_keys(self) -> List[str]:
        keys: List[str] = []
        for item in self.capability_entries:
            key = str(item.get("key") or "").strip()
            if key:
                keys.append(key)
        return keys

    @property
    def configuration(self) -> Dict[str, Any]:
        return dict(self.raw.get("configuration") or {})

    @property
    def compatibility(self) -> Dict[str, Any]:
        return dict(self.raw.get("compatibility") or {})

    @property
    def legacy_platforms(self) -> List[str]:
        return [
            str(item or "").strip()
            for item in (self.compatibility.get("legacy_platforms") or [])
            if str(item or "").strip()
        ]

    @property
    def order(self) -> int:
        try:
            return int(self.configuration.get("order", 100))
        except Exception:
            return 100

    def has_capability(self, capability: str) -> bool:
        return str(capability or "").strip() in set(self.capability_keys)

    def list_configuration_fields(self) -> List[Dict[str, Any]]:
        fields: List[Dict[str, Any]] = []
        sections = self.configuration.get("sections") or []
        for section in sections:
            if not isinstance(section, dict):
                continue
            for field in section.get("fields") or []:
                if isinstance(field, dict):
                    fields.append(dict(field))
        return fields


class ProtocolProvider:
    def __init__(self, manifest: Dict[str, Any], manifest_path: str):
        self.manifest = dict(manifest or {})
        self.manifest_path = str(manifest_path or "")

    def normalize_config(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return dict(payload or {})

    def serialize_public_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        return dict(config or {})

    def get_query_status(self, config: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "configured": True,
            "message": "",
            "missing_fields": [],
        }

    def get_legacy_client(self, config: Dict[str, Any], *args, **kwargs):
        raise NotImplementedError

    def execute(self, capability: str, params: Dict[str, Any], context: Dict[str, Any], config: Dict[str, Any]):
        raise NotImplementedError

