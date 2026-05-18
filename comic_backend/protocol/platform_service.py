from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
from infrastructure.logger import error_logger

from .gateway import ProtocolGateway, get_protocol_gateway
from .host_service import ProtocolHostService

BaseAdapter = Any


class PlatformService:
    """Protocol-backed compatibility service for comic/video platform actions."""

    _instance = None
    _adapters: Dict[str, BaseAdapter] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, gateway: Optional[ProtocolGateway] = None):
        if not hasattr(self, "_initialized"):
            self._gateway = gateway or get_protocol_gateway()
            self._initialized = True

    def _get_host_service(self) -> ProtocolHostService:
        host_service = getattr(self, "_host_service", None)
        gateway = getattr(self, "_gateway", None) or get_protocol_gateway()
        if host_service is None or getattr(host_service, "gateway", None) is not gateway:
            host_service = ProtocolHostService(gateway)
            self._host_service = host_service
        return host_service

    @staticmethod
    def _normalize_platform_name(platform: Any) -> str:
        return str(getattr(platform, "value", platform) or "").strip().lower()

    def _resolve_plugin_id(
        self,
        platform: Any,
        capability: Optional[str] = None,
    ) -> str:
        plugin_id = self._get_host_service().get_plugin_id(platform, capability=capability)
        if plugin_id:
            return plugin_id
        raise ValueError(f"未知平台: {platform}")

    def get_adapter(self, platform: Any) -> BaseAdapter:
        return self._get_host_service().get_comic_platform_client(platform)

    def download_album(
        self,
        platform: Any,
        album_id: str,
        download_dir: str,
        show_progress: bool = False,
        **kwargs,
    ) -> Tuple[Dict[str, Any], bool]:
        try:
            plugin_id = self._resolve_plugin_id(platform, capability="asset.bundle.fetch")
            result = self._get_host_service().execute_comic_platform(
                platform,
                "asset.bundle.fetch",
                {
                    "album_id": album_id,
                    "download_dir": download_dir,
                    "show_progress": show_progress,
                    "extra": kwargs,
                },
            )
            return dict(result.get("detail") or {}), bool(result.get("success"))
        except Exception as e:
            error_logger.error(f"下载漫画失败: {platform}, {album_id}, {e}")
            return {}, False

    def download_cover(
        self,
        platform: Any,
        album_id: str,
        save_path: str,
        show_progress: bool = False,
    ) -> Tuple[Dict[str, Any], bool]:
        try:
            plugin_id = self._resolve_plugin_id(platform, capability="asset.cover.fetch")
            result = self._get_host_service().execute_comic_platform(
                platform,
                "asset.cover.fetch",
                {
                    "album_id": album_id,
                    "save_path": save_path,
                    "show_progress": show_progress,
                },
            )
            return dict(result.get("detail") or {}), bool(result.get("success"))
        except Exception as e:
            error_logger.error(f"下载封面失败: {platform}, {album_id}, {e}")
            return {}, False

    def get_comic_dir(
        self,
        platform: Any,
        album_id: str,
        author: str = None,
        title: str = None,
        base_dir: str = None,
    ) -> str:
        return self._get_host_service().execute_comic_platform(
            platform,
            "storage.comic_dir.resolve",
            {
                "album_id": album_id,
                "author": author,
                "title": title,
                "base_dir": base_dir,
            },
        )

    def get_cover_url(self, platform: Any, album_id: str) -> Optional[str]:
        return self.get_adapter(platform).get_cover_url(album_id)

    def get_image_url(self, platform: Any, album_id: str, page: int) -> Optional[str]:
        return self.get_adapter(platform).get_image_url(album_id, page)

    def get_preview_image_urls(self, platform: Any, album_id: str, preview_pages: List[int]) -> List[str]:
        return self._get_host_service().execute_comic_platform(
            platform,
            "asset.preview.resolve",
            {
                "album_id": album_id,
                "preview_pages": preview_pages,
            },
        )

    def get_album_by_id(self, platform: Any, album_id: str) -> Dict[str, Any]:
        return self._get_host_service().execute_comic_platform(
            platform,
            "catalog.detail",
            {"album_id": album_id},
        )

    def search_albums(
        self,
        platform: Any,
        keyword: str,
        max_pages: int = 1,
        fast_mode: bool = False,
    ) -> Dict[str, Any]:
        return self._get_host_service().execute_comic_platform(
            platform,
            "catalog.search",
            {
                "keyword": keyword,
                "page": 1,
                "max_pages": max_pages,
                "fast_mode": fast_mode,
            },
        )

    def get_favorites(self, platform: Any) -> Dict[str, Any]:
        return self._host_service.execute_comic_platform(
            platform,
            "collection.favorites",
            {},
        )

    def get_favorites_basic(self, platform: Any) -> Dict[str, Any]:
        plugin_id = self._resolve_plugin_id(platform)
        capability = "collection.favorites_basic"
        if hasattr(self._gateway, "registry"):
            try:
                manifest = self._gateway.registry.get_manifest(plugin_id)
                if manifest.has_capability("collection.favorites_basic"):
                    capability = "collection.favorites_basic"
                elif manifest.has_capability("collection.favorites"):
                    capability = "collection.favorites"
                else:
                    capability = "collection.favorites"
            except Exception:
                capability = "collection.favorites"
        return self._get_host_service().execute_comic_platform(platform, capability, {})

    def get_user_lists(self, platform: Any) -> Dict[str, Any]:
        return self._get_host_service().execute_comic_platform(
            platform,
            "collection.list",
            {},
        )

    def get_list_detail(self, platform: Any, list_id: str) -> Dict[str, Any]:
        return self._get_host_service().execute_comic_platform(
            platform,
            "collection.detail",
            {"list_id": list_id},
        )


def get_platform_service() -> PlatformService:
    return PlatformService()
