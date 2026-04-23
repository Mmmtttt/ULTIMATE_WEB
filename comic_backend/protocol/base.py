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
    def helpers(self) -> Dict[str, Any]:
        return dict(self.raw.get("helpers") or {})

    @property
    def storage(self) -> Dict[str, Any]:
        return dict(self.raw.get("storage") or {})

    @property
    def compatibility(self) -> Dict[str, Any]:
        return dict(self.raw.get("compatibility") or {})

    @property
    def identity(self) -> Dict[str, Any]:
        return dict(self.raw.get("identity") or {})

    @property
    def presentation(self) -> Dict[str, Any]:
        return dict(self.raw.get("presentation") or {})

    @property
    def actions(self) -> List[Dict[str, Any]]:
        return [dict(item or {}) for item in (self.raw.get("actions") or []) if isinstance(item, dict)]

    @property
    def resource_policy(self) -> Dict[str, Any]:
        return dict(self.raw.get("resource_policy") or {})

    @property
    def collections(self) -> Dict[str, Any]:
        return dict(self.raw.get("collections") or {})

    @property
    def legacy_platforms(self) -> List[str]:
        return [
            str(item or "").strip()
            for item in (self.compatibility.get("legacy_platforms") or [])
            if str(item or "").strip()
        ]

    @property
    def legacy_adapter_name(self) -> str:
        return str(self.compatibility.get("legacy_adapter_name") or "").strip()

    @property
    def order(self) -> int:
        try:
            return int(self.configuration.get("order", 100))
        except Exception:
            return 100

    @property
    def collection_list_mode(self) -> str:
        return str(self.collections.get("list_mode") or "").strip().lower()

    def has_capability(self, capability: str) -> bool:
        return str(capability or "").strip() in set(self.capability_keys)

    def get_capability_entry(self, capability: str) -> Dict[str, Any]:
        lookup = str(capability or "").strip()
        if not lookup:
            return {}
        for item in self.capability_entries:
            key = str(item.get("key") or "").strip()
            if key == lookup:
                return dict(item)
        return {}

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

    def list_configuration_actions(self) -> List[Dict[str, Any]]:
        actions: List[Dict[str, Any]] = []

        for action in self.actions:
            scope = str(action.get("scope") or "").strip().lower()
            if scope in {"config", "configuration", "settings"}:
                actions.append(dict(action))

        for action in (self.configuration.get("actions") or []):
            if not isinstance(action, dict):
                continue
            normalized = dict(action)
            normalized.setdefault("scope", "configuration")
            actions.append(normalized)

        return actions

    def list_helpers(self) -> Dict[str, Dict[str, Any]]:
        helpers: Dict[str, Dict[str, Any]] = {}
        for helper_key, helper_value in (self.helpers or {}).items():
            normalized_key = str(helper_key or "").strip()
            if not normalized_key or not isinstance(helper_value, dict):
                continue
            helpers[normalized_key] = dict(helper_value)
        return helpers

    def get_helper(self, helper_key: str) -> Dict[str, Any]:
        lookup = str(helper_key or "").strip()
        if not lookup:
            return {}
        return dict(self.list_helpers().get(lookup) or {})

    def list_data_dir_bindings(self) -> List[Dict[str, Any]]:
        bindings: List[Dict[str, Any]] = []
        for item in (self.storage.get("data_dir_bindings") or []):
            if isinstance(item, dict):
                bindings.append(dict(item))
        return bindings

    def list_virtual_lists(self) -> List[Dict[str, Any]]:
        virtual_lists: List[Dict[str, Any]] = []
        for item in (self.collections.get("virtual_lists") or []):
            if isinstance(item, dict):
                virtual_lists.append(dict(item))
        return virtual_lists

    def to_public_descriptor(self) -> Dict[str, Any]:
        return {
            "plugin_id": self.plugin_id,
            "config_key": self.config_key,
            "name": self.name,
            "version": self.version,
            "media_types": self.media_types,
            "capabilities": self.capability_keys,
            "legacy_platforms": self.legacy_platforms,
            "legacy_adapter_name": self.legacy_adapter_name,
            "identity": self.identity,
            "presentation": self.presentation,
            "actions": self.actions,
            "collections": self.collections,
            "resource_policy": self.resource_policy,
            "order": self.order,
        }


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
