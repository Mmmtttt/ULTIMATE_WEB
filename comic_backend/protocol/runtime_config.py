from __future__ import annotations

from typing import Dict, Iterable, Optional


class ProtocolConfigStore:
    """Protocol-facing access to the legacy third-party config file.

    The actual on-disk storage remains unchanged during migration, but host-side
    callers should go through this wrapper instead of importing legacy adapter
    infrastructure directly.
    """

    def __init__(self):
        self._manager = None

    def _get_manager(self):
        if self._manager is None:
            from third_party.adapter_factory import AdapterConfig

            self._manager = AdapterConfig()
        return self._manager

    def reload(self):
        self._get_manager().reload_config()

    def get_plugin_config(self, config_key: str, reload: bool = False) -> Dict:
        if reload:
            self.reload()
        return dict(self._get_manager().get_adapter_config(str(config_key or "").strip()) or {})

    def set_plugin_config(self, config_key: str, payload: Dict):
        self._get_manager().set_adapter_config(str(config_key or "").strip(), dict(payload or {}))

    def get_default_config_key(self) -> str:
        return str(self._get_manager().get_default_adapter() or "").strip()

    def set_default_config_key(self, config_key: str):
        self._get_manager().set_default_adapter(str(config_key or "").strip())

    @staticmethod
    def list_legacy_config_keys():
        from third_party.adapter_factory import AdapterFactory

        return list(AdapterFactory.list_adapters())

    @staticmethod
    def reset_runtime_caches(config_keys: Optional[Iterable[str]] = None):
        from third_party.adapter_factory import AdapterFactory

        available = set(AdapterFactory.list_adapters())
        if config_keys is None:
            targets = available
        else:
            targets = {str(item or "").strip() for item in config_keys if str(item or "").strip() in available}

        for config_key in targets:
            AdapterFactory.reset_instance(config_key)

        from third_party.external_api import reset_config_manager

        reset_config_manager()


def get_protocol_config_store() -> ProtocolConfigStore:
    return ProtocolConfigStore()
