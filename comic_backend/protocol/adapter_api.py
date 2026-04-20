from __future__ import annotations

from typing import Any, Dict, Optional

from .compatibility import get_plugin_id_for_adapter_name
from .gateway import ProtocolGateway, get_protocol_gateway
from .runtime_config import ProtocolConfigStore


class ProtocolAdapterAPI:
    """Host-facing adapter facade backed by the protocol layer."""

    def __init__(self, gateway: Optional[ProtocolGateway] = None, config_store: Optional[ProtocolConfigStore] = None):
        self._gateway = gateway or get_protocol_gateway()
        self._config_store = config_store or ProtocolConfigStore()

    def get_config_manager(self):
        return self._config_store

    def reset_config_manager(self):
        self._config_store = ProtocolConfigStore()

    def _resolve_adapter_name(self, adapter_name: Optional[str] = None) -> str:
        resolved = adapter_name if adapter_name is not None else self._config_store.get_default_adapter()
        return str(resolved or "").strip()

    def get_adapter(self, adapter_name: Optional[str] = None):
        resolved_adapter = self._resolve_adapter_name(adapter_name)
        adapter_config = self._config_store.get_adapter_config(resolved_adapter)
        plugin_id = get_plugin_id_for_adapter_name(resolved_adapter)
        if plugin_id:
            return self._gateway.get_legacy_client(plugin_id)

        from third_party.adapter_factory import AdapterFactory
        from third_party.credential_guard import ensure_adapter_query_ready

        ensure_adapter_query_ready(resolved_adapter, adapter_config)
        return AdapterFactory.get_adapter(resolved_adapter, adapter_config)

    def get_album_by_id(self, album_id: str, adapter_name: Optional[str] = None) -> Dict[str, Any]:
        resolved_adapter = self._resolve_adapter_name(adapter_name)
        plugin_id = get_plugin_id_for_adapter_name(resolved_adapter)
        if plugin_id:
            return self._gateway.execute_plugin(
                plugin_id,
                "catalog.detail",
                params={"album_id": album_id},
            )

        adapter = self.get_adapter(resolved_adapter)
        return adapter.get_album_by_id(album_id)

    def search_albums(
        self,
        keyword: str,
        page: int = 1,
        max_pages: int = 1,
        adapter_name: Optional[str] = None,
        fast_mode: bool = False,
    ) -> Dict[str, Any]:
        resolved_adapter = self._resolve_adapter_name(adapter_name)
        plugin_id = get_plugin_id_for_adapter_name(resolved_adapter)
        if plugin_id:
            return self._gateway.execute_plugin(
                plugin_id,
                "catalog.search",
                params={
                    "keyword": keyword,
                    "page": page,
                    "max_pages": max_pages,
                    "fast_mode": fast_mode,
                },
            )

        adapter = self.get_adapter(resolved_adapter)
        return adapter.search_albums(keyword, page, max_pages, fast_mode)

    def get_favorites(self, adapter_name: Optional[str] = None) -> Dict[str, Any]:
        resolved_adapter = self._resolve_adapter_name(adapter_name)
        plugin_id = get_plugin_id_for_adapter_name(resolved_adapter)
        if plugin_id:
            return self._gateway.execute_plugin(
                plugin_id,
                "collection.favorites",
                params={},
            )

        adapter = self.get_adapter(resolved_adapter)
        return adapter.get_favorites()

    def list_available_adapters(self) -> list:
        discovered = []
        for manifest in self._gateway.list_manifests():
            config_key = str(manifest.config_key or "").strip()
            if config_key:
                discovered.append(config_key)
        return sorted(set(self._config_store.list_legacy_config_keys()) | set(discovered))

    def get_adapter_config(self, adapter_name: str) -> Dict[str, Any]:
        return self._config_store.get_adapter_config(adapter_name)

    def set_adapter_config(self, adapter_name: str, config: Dict[str, Any]):
        self._config_store.set_adapter_config(adapter_name, config)

    def get_default_adapter(self) -> str:
        return self._config_store.get_default_adapter()

    def set_default_adapter(self, adapter_name: str):
        self._config_store.set_default_adapter(adapter_name)

    def reset_adapter(self, adapter_name: str):
        self._config_store.reset_runtime_caches([adapter_name])
        self.reset_config_manager()


_adapter_api_singleton: Optional[ProtocolAdapterAPI] = None


def get_protocol_adapter_api() -> ProtocolAdapterAPI:
    global _adapter_api_singleton
    if _adapter_api_singleton is None:
        _adapter_api_singleton = ProtocolAdapterAPI()
    return _adapter_api_singleton


def get_config_manager():
    return get_protocol_adapter_api().get_config_manager()


def reset_config_manager():
    return get_protocol_adapter_api().reset_config_manager()


def get_adapter(adapter_name: Optional[str] = None):
    return get_protocol_adapter_api().get_adapter(adapter_name)


def get_album_by_id(album_id: str, adapter_name: Optional[str] = None) -> Dict[str, Any]:
    return get_protocol_adapter_api().get_album_by_id(album_id, adapter_name)


def search_albums(
    keyword: str,
    page: int = 1,
    max_pages: int = 1,
    adapter_name: Optional[str] = None,
    fast_mode: bool = False,
) -> Dict[str, Any]:
    return get_protocol_adapter_api().search_albums(
        keyword,
        page=page,
        max_pages=max_pages,
        adapter_name=adapter_name,
        fast_mode=fast_mode,
    )


def get_favorites(adapter_name: Optional[str] = None) -> Dict[str, Any]:
    return get_protocol_adapter_api().get_favorites(adapter_name)


def list_available_adapters() -> list:
    return get_protocol_adapter_api().list_available_adapters()


def get_adapter_config(adapter_name: str) -> Dict[str, Any]:
    return get_protocol_adapter_api().get_adapter_config(adapter_name)


def set_adapter_config(adapter_name: str, config: Dict[str, Any]):
    return get_protocol_adapter_api().set_adapter_config(adapter_name, config)


def get_default_adapter() -> str:
    return get_protocol_adapter_api().get_default_adapter()


def set_default_adapter(adapter_name: str):
    return get_protocol_adapter_api().set_default_adapter(adapter_name)


def reset_adapter(adapter_name: str):
    return get_protocol_adapter_api().reset_adapter(adapter_name)

