from __future__ import annotations

from typing import Dict, List, Tuple

from infrastructure.logger import app_logger
from third_party.adapter_factory import AdapterConfig, AdapterFactory
from third_party.external_api import reset_config_manager

from .gateway import get_protocol_gateway


class PluginConfigService:
    def __init__(self):
        self._config_manager = AdapterConfig()
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

    def build_response(self) -> dict:
        self._config_manager.reload_config()
        configurable = self._collect_configurable_plugins()

        adapter_order: List[str] = []
        schema: Dict[str, dict] = {}
        adapters: Dict[str, dict] = {}
        helper_urls: Dict[str, str] = {}

        for manifest in configurable:
            config_key = manifest.config_key
            adapter_order.append(config_key)

            fields = manifest.list_configuration_fields()
            schema[config_key] = {
                "label": manifest.configuration.get("label") or manifest.name,
                "fields": fields,
                "actions": list(manifest.configuration.get("actions") or []),
            }

            raw_config = self._config_manager.get_adapter_config(config_key) or {}
            adapters[config_key] = self._gateway.provider_manager.serialize_public_config(manifest.plugin_id, raw_config)

            for helper_key, helper_value in (manifest.configuration.get("helper_urls") or {}).items():
                helper_key = str(helper_key or "").strip()
                helper_value = str(helper_value or "").strip()
                if helper_key and helper_value:
                    helper_urls[helper_key] = helper_value

        response = {
            "default_adapter": self._config_manager.get_default_adapter(),
            "adapter_order": adapter_order,
            "schema": schema,
            "adapters": adapters,
            "helper_urls": helper_urls,
            "plugins": [
                {
                    "plugin_id": manifest.plugin_id,
                    "config_key": manifest.config_key,
                    "name": manifest.name,
                    "media_types": manifest.media_types,
                    "capabilities": manifest.capability_keys,
                }
                for manifest in configurable
            ],
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
            self._config_manager.set_adapter_config(config_key, normalized_payload)
            if config_key in set(AdapterFactory.list_adapters()):
                AdapterFactory.reset_instance(config_key)
            updated_keys.append(config_key)

        reset_config_manager()
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

