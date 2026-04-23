from __future__ import annotations

from typing import Any, Dict, Optional

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

    def _resolve_manifest(self, adapter_name: Optional[str] = None):
        resolved_adapter = self._resolve_adapter_name(adapter_name)
        if not resolved_adapter:
            return None
        manifest = self._gateway.get_manifest_by_config_key(resolved_adapter)
        if manifest is not None:
            return manifest
        return self._gateway.get_manifest_by_lookup(resolved_adapter)

    def get_adapter(self, adapter_name: Optional[str] = None):
        resolved_adapter = self._resolve_adapter_name(adapter_name)
        manifest = self._resolve_manifest(resolved_adapter)
        if manifest is None:
            raise ValueError(f"unsupported adapter: {resolved_adapter}")
        return self._gateway.get_client(manifest.plugin_id)

    def get_album_by_id(self, album_id: str, adapter_name: Optional[str] = None) -> Dict[str, Any]:
        manifest = self._resolve_manifest(adapter_name)
        if manifest is not None:
            return self._gateway.execute_plugin(
                manifest.plugin_id,
                "catalog.detail",
                params={"album_id": album_id},
            )
        raise ValueError(f"unsupported adapter: {self._resolve_adapter_name(adapter_name)}")

    def search_albums(
        self,
        keyword: str,
        page: int = 1,
        max_pages: int = 1,
        adapter_name: Optional[str] = None,
        fast_mode: bool = False,
    ) -> Dict[str, Any]:
        manifest = self._resolve_manifest(adapter_name)
        if manifest is not None:
            return self._gateway.execute_plugin(
                manifest.plugin_id,
                "catalog.search",
                params={
                    "keyword": keyword,
                    "page": page,
                    "max_pages": max_pages,
                    "fast_mode": fast_mode,
                },
            )

        raise ValueError(f"unsupported adapter: {self._resolve_adapter_name(adapter_name)}")

    def get_favorites(self, adapter_name: Optional[str] = None) -> Dict[str, Any]:
        manifest = self._resolve_manifest(adapter_name)
        if manifest is not None:
            return self._gateway.execute_plugin(
                manifest.plugin_id,
                "collection.favorites",
                params={},
            )
        raise ValueError(f"unsupported adapter: {self._resolve_adapter_name(adapter_name)}")

    def list_available_adapters(self) -> list:
        discovered = []
        for manifest in self._gateway.list_manifests():
            config_key = str(manifest.config_key or "").strip()
            if config_key:
                discovered.append(config_key)
        return sorted(set(self._config_store.list_config_keys()) | set(discovered))

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
