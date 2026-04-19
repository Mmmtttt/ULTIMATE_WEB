from __future__ import annotations

from typing import Any, Dict, Optional

from .provider_manager import ProviderManager, get_provider_manager
from .registry import PluginRegistry, get_plugin_registry


class ProtocolGateway:
    def __init__(self, registry: Optional[PluginRegistry] = None, provider_manager: Optional[ProviderManager] = None):
        self.registry = registry or get_plugin_registry()
        self.provider_manager = provider_manager or get_provider_manager()

    def execute_plugin(self, plugin_id: str, capability: str, params: Optional[Dict[str, Any]] = None, context: Optional[Dict[str, Any]] = None) -> Any:
        return self.provider_manager.execute(plugin_id, capability, params=params, context=context)

    def get_legacy_client(self, plugin_id: str, *args, **kwargs):
        return self.provider_manager.get_legacy_client(plugin_id, *args, **kwargs)

    def get_query_status(self, plugin_id: str) -> Dict[str, Any]:
        return self.provider_manager.get_query_status(plugin_id)

    def list_manifests(self, media_type: Optional[str] = None, capability: Optional[str] = None):
        return self.registry.list_manifests(media_type=media_type, capability=capability)

    def get_manifest_by_config_key(self, config_key: str):
        return self.registry.find_by_config_key(config_key)

    def get_manifest_by_legacy_platform(self, platform_name: str):
        return self.registry.find_by_legacy_platform(platform_name)


_gateway_singleton: Optional[ProtocolGateway] = None


def get_protocol_gateway() -> ProtocolGateway:
    global _gateway_singleton
    if _gateway_singleton is None:
        _gateway_singleton = ProtocolGateway()
    return _gateway_singleton

