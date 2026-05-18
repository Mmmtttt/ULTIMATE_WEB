from __future__ import annotations

from typing import Any, Dict, Optional

from .gateway import ProtocolGateway, get_protocol_gateway
from .host_service import ProtocolHostService, get_protocol_host_service
from .runtime_config import ProtocolConfigStore


class ProtocolAdapterAPI:
    """Host-facing adapter facade backed by the protocol layer."""

    def __init__(self, gateway: Optional[ProtocolGateway] = None, config_store: Optional[ProtocolConfigStore] = None):
        self._gateway = gateway or get_protocol_gateway()
        self._config_store = config_store or ProtocolConfigStore()
        self._host_service = ProtocolHostService(self._gateway, self._config_store)

    def get_config_manager(self):
        return self._config_store

    def reset_config_manager(self):
        self._config_store = ProtocolConfigStore()

    def _resolve_adapter_name(self, adapter_name: Optional[str] = None) -> str:
        return self._host_service.resolve_adapter_name(adapter_name)

    def _resolve_manifest(self, adapter_name: Optional[str] = None):
        return self._host_service.resolve_comic_adapter_manifest(adapter_name)

    def get_adapter(self, adapter_name: Optional[str] = None):
        return self._host_service.get_comic_adapter_client(adapter_name)

    def get_album_by_id(self, album_id: str, adapter_name: Optional[str] = None) -> Dict[str, Any]:
        return self._host_service.execute_comic_adapter(
            "catalog.detail",
            {"album_id": album_id},
            adapter_name=adapter_name,
        )

    def search_albums(
        self,
        keyword: str,
        page: int = 1,
        max_pages: int = 1,
        adapter_name: Optional[str] = None,
        fast_mode: bool = False,
    ) -> Dict[str, Any]:
        return self._host_service.execute_comic_adapter(
            "catalog.search",
            {
                "keyword": keyword,
                "page": page,
                "max_pages": max_pages,
                "fast_mode": fast_mode,
            },
            adapter_name=adapter_name,
        )

    def get_favorites(self, adapter_name: Optional[str] = None) -> Dict[str, Any]:
        return self._host_service.execute_comic_adapter(
            "collection.favorites",
            {},
            adapter_name=adapter_name,
        )

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
