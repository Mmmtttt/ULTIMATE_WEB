from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

from core.platform import Platform
from infrastructure.logger import error_logger

from .compatibility import get_plugin_id_for_platform
from .gateway import ProtocolGateway, get_protocol_gateway

if TYPE_CHECKING:
    from third_party.base_adapter import BaseAdapter
else:
    BaseAdapter = Any


class PlatformService:
    """Protocol-backed compatibility service for comic/video platform actions."""

    _instance = None
    _adapters: Dict[Platform, BaseAdapter] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, gateway: Optional[ProtocolGateway] = None):
        if not hasattr(self, "_initialized"):
            self._gateway = gateway or get_protocol_gateway()
            self._initialized = True

    def get_adapter(self, platform: Platform) -> BaseAdapter:
        plugin_id = get_plugin_id_for_platform(platform)
        if not plugin_id:
            raise ValueError(f"未知平台: {platform}")
        return self._gateway.get_legacy_client(plugin_id)

    def download_album(
        self,
        platform: Platform,
        album_id: str,
        download_dir: str,
        show_progress: bool = False,
        **kwargs,
    ) -> Tuple[Dict[str, Any], bool]:
        try:
            plugin_id = get_plugin_id_for_platform(platform)
            result = self._gateway.execute_plugin(
                plugin_id,
                "asset.bundle.fetch",
                params={
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
        platform: Platform,
        album_id: str,
        save_path: str,
        show_progress: bool = False,
    ) -> Tuple[Dict[str, Any], bool]:
        try:
            plugin_id = get_plugin_id_for_platform(platform)
            result = self._gateway.execute_plugin(
                plugin_id,
                "asset.cover.fetch",
                params={
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
        platform: Platform,
        album_id: str,
        author: str = None,
        title: str = None,
        base_dir: str = None,
    ) -> str:
        plugin_id = get_plugin_id_for_platform(platform)
        return self._gateway.execute_plugin(
            plugin_id,
            "storage.comic_dir.resolve",
            params={
                "album_id": album_id,
                "author": author,
                "title": title,
                "base_dir": base_dir,
            },
        )

    def get_cover_url(self, platform: Platform, album_id: str) -> Optional[str]:
        return self.get_adapter(platform).get_cover_url(album_id)

    def get_image_url(self, platform: Platform, album_id: str, page: int) -> Optional[str]:
        return self.get_adapter(platform).get_image_url(album_id, page)

    def get_preview_image_urls(self, platform: Platform, album_id: str, preview_pages: List[int]) -> List[str]:
        plugin_id = get_plugin_id_for_platform(platform)
        return self._gateway.execute_plugin(
            plugin_id,
            "asset.preview.resolve",
            params={
                "album_id": album_id,
                "preview_pages": preview_pages,
            },
        )

    def get_album_by_id(self, platform: Platform, album_id: str) -> Dict[str, Any]:
        plugin_id = get_plugin_id_for_platform(platform)
        return self._gateway.execute_plugin(
            plugin_id,
            "catalog.detail",
            params={"album_id": album_id},
        )

    def search_albums(
        self,
        platform: Platform,
        keyword: str,
        max_pages: int = 1,
        fast_mode: bool = False,
    ) -> Dict[str, Any]:
        plugin_id = get_plugin_id_for_platform(platform)
        return self._gateway.execute_plugin(
            plugin_id,
            "catalog.search",
            params={
                "keyword": keyword,
                "page": 1,
                "max_pages": max_pages,
                "fast_mode": fast_mode,
            },
        )

    def get_favorites(self, platform: Platform) -> Dict[str, Any]:
        plugin_id = get_plugin_id_for_platform(platform)
        return self._gateway.execute_plugin(
            plugin_id,
            "collection.favorites",
            params={},
        )

    def get_favorites_basic(self, platform: Platform) -> Dict[str, Any]:
        plugin_id = get_plugin_id_for_platform(platform)
        capability = "collection.favorites_basic" if platform != Platform.JAVDB else "collection.favorites"
        return self._gateway.execute_plugin(plugin_id, capability, params={})

    def get_user_lists(self, platform: Platform) -> Dict[str, Any]:
        plugin_id = get_plugin_id_for_platform(platform)
        return self._gateway.execute_plugin(
            plugin_id,
            "collection.list",
            params={},
        )

    def get_list_detail(self, platform: Platform, list_id: str) -> Dict[str, Any]:
        plugin_id = get_plugin_id_for_platform(platform)
        return self._gateway.execute_plugin(
            plugin_id,
            "collection.detail",
            params={"list_id": list_id},
        )


def get_platform_service() -> PlatformService:
    return PlatformService()
