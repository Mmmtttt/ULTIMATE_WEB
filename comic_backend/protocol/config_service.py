from __future__ import annotations

from typing import Dict, List, Tuple

from infrastructure.logger import app_logger

from .gateway import get_protocol_gateway
from .runtime_config import ProtocolConfigStore


class PluginConfigService:
    def __init__(self):
        self._config_store = ProtocolConfigStore()
        self._gateway = get_protocol_gateway()

    @staticmethod
    def _unwrap_payload(payload: dict) -> dict:
        raw = dict(payload or {})
        if isinstance(raw.get("config"), dict):
            return dict(raw.get("config") or {})
        raw.pop("adapter", None)
        return raw

    def _collect_configurable_plugins(self):
        manifests = self._gateway.list_manifests()
        return [
            manifest
            for manifest in manifests
            if manifest.config_key and manifest.list_configuration_fields()
        ]

    @staticmethod
    def _build_helper_url(config_key: str, helper_key: str) -> str:
        normalized_config_key = str(config_key or "").strip().lower()
        normalized_helper_key = str(helper_key or "").strip()
        return f"/api/v1/config/plugin-helpers/{normalized_config_key}/{normalized_helper_key}/"

    def build_response(self) -> dict:
        self._config_store.reload()
        manifests = self._gateway.list_manifests()
        configurable = self._collect_configurable_plugins()

        adapter_order: List[str] = []
        schema: Dict[str, dict] = {}
        adapters: Dict[str, dict] = {}
        helper_urls: Dict[str, str] = {}

        for manifest in configurable:
            config_key = manifest.config_key
            adapter_order.append(config_key)

            fields = manifest.list_configuration_fields()
            helper_definitions = manifest.list_helpers()
            actions = []
            for action in manifest.list_configuration_actions():
                normalized_action = dict(action or {})
                helper_key = str(
                    normalized_action.get("helper_key") or ""
                ).strip()
                action_kind = str(normalized_action.get("kind") or "").strip().lower()
                if (
                    helper_key
                    and helper_key in helper_definitions
                    and action_kind == "open_url"
                    and not str(normalized_action.get("url") or "").strip()
                ):
                    normalized_action["url"] = self._build_helper_url(config_key, helper_key)
                actions.append(normalized_action)

            schema[config_key] = {
                "label": manifest.configuration.get("label") or manifest.name,
                "fields": fields,
                "actions": actions,
            }

            raw_config = self._config_store.get_plugin_config(config_key) or {}
            adapters[config_key] = self._gateway.provider_manager.serialize_public_config(manifest.plugin_id, raw_config)

            for helper_key in helper_definitions:
                helper_urls[helper_key] = self._build_helper_url(config_key, helper_key)

            for helper_key, helper_value in (manifest.configuration.get("helper_urls") or {}).items():
                helper_key = str(helper_key or "").strip()
                helper_value = str(helper_value or "").strip()
                if helper_key and helper_value:
                    helper_urls[helper_key] = helper_value

            for action in actions:
                helper_key = str(action.get("helper_key") or "").strip()
                helper_value = str(action.get("url") or "").strip()
                action_kind = str(action.get("kind") or "").strip().lower()
                if helper_key and helper_value and action_kind == "open_url":
                    helper_urls[helper_key] = helper_value

        response = {
            "default_adapter": self._config_store.get_default_config_key(),
            "adapter_order": adapter_order,
            "schema": schema,
            "adapters": adapters,
            "helper_urls": helper_urls,
            "plugins": [manifest.to_public_descriptor() for manifest in manifests],
            "configurable_plugins": [manifest.to_public_descriptor() for manifest in configurable],
        }
        response.update(adapters)
        return response

    def _resolve_updates(self, payload: dict) -> List[Tuple[str, dict]]:
        raw = dict(payload or {})
        if isinstance(raw.get("adapters"), dict):
            items = list((raw.get("adapters") or {}).items())
        else:
            adapter_name = str(raw.get("adapter") or "").strip()
            if not adapter_name:
                raise ValueError("缺少参数: adapter")
            items = [(adapter_name, raw)]

        resolved: List[Tuple[str, dict]] = []
        for config_key, value in items:
            normalized_key = str(config_key or "").strip()
            manifest = self._gateway.get_manifest_by_config_key(normalized_key)
            if manifest is None:
                raise ValueError(f"不支持的适配器: {normalized_key}")
            resolved.append((manifest.plugin_id, self._unwrap_payload(value)))
        return resolved

    def save_updates(self, payload: dict) -> dict:
        updates = self._resolve_updates(payload)
        updated_keys: List[str] = []

        for plugin_id, adapter_payload in updates:
            manifest = self._gateway.registry.get_manifest(plugin_id)
            config_key = manifest.config_key
            normalized_payload = self._gateway.provider_manager.normalize_config(plugin_id, adapter_payload)
            self._config_store.set_plugin_config(config_key, normalized_payload)
            updated_keys.append(config_key)

        self._config_store.reset_runtime_caches(updated_keys)
        app_logger.info(f"protocol config saved: {updated_keys}")
        return {
            "updated_adapters": updated_keys,
            "message": "配置保存成功",
        }


_config_service_singleton: PluginConfigService | None = None


def get_plugin_config_service() -> PluginConfigService:
    global _config_service_singleton
    if _config_service_singleton is None:
        _config_service_singleton = PluginConfigService()
    return _config_service_singleton
