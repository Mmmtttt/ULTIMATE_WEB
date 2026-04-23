"""
Compatibility wrapper around the protocol-backed platform service.
"""

from typing import Any, List, Tuple

from infrastructure.logger import app_logger
from protocol.gateway import get_protocol_gateway
from protocol.platform_meta import (
    resolve_manifest_host_prefix,
    resolve_manifest_platform_label,
    resolve_platform_manifest,
    split_prefixed_id,
)
from protocol.platform_service import get_platform_service as get_protocol_platform_service

BaseAdapter = Any


class PlatformService:
    """Backward-compatible facade that delegates to protocol.platform_service."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._delegate = get_protocol_platform_service()
        self._registered_aliases = {}
        self._initialized = True
        app_logger.info("应用平台服务初始化完成（协议包装）")

    @staticmethod
    def _normalize_platform_name(platform: Any) -> str:
        return str(getattr(platform, "value", platform) or "").strip().lower()

    def register_platform(self, platform: Any, adapter_name: str):
        normalized_platform = self._normalize_platform_name(platform)
        normalized_adapter = str(adapter_name or "").strip()
        if normalized_platform and normalized_adapter:
            self._registered_aliases[normalized_platform] = normalized_adapter
            app_logger.info(f"注册平台兼容别名: {normalized_platform} -> {normalized_adapter}")

    def _resolve_delegate_platform(self, platform: Any) -> str:
        normalized_platform = self._normalize_platform_name(platform)
        return str(self._registered_aliases.get(normalized_platform) or platform or "").strip()

    def _split_comic_id(self, comic_id: str) -> Tuple[str, str]:
        platform_name, original_id, _manifest = split_prefixed_id(comic_id, media_type="comic")
        normalized_platform = str(platform_name or "").strip()
        normalized_original_id = str(original_id or "").strip()
        if not normalized_platform or not normalized_original_id:
            raise ValueError(f"无法从漫画ID识别平台: {comic_id}")
        return normalized_platform, normalized_original_id

    def get_adapter(self, platform: Any) -> BaseAdapter:
        return self._delegate.get_adapter(self._resolve_delegate_platform(platform))

    def get_adapter_by_comic_id(self, comic_id: str) -> BaseAdapter:
        platform, _original_id = self._split_comic_id(comic_id)
        return self.get_adapter(platform)

    def get_platform_prefix(self, platform: Any) -> str:
        normalized_platform = self._normalize_platform_name(platform)
        manifest = resolve_platform_manifest(normalized_platform, media_type="comic")
        return resolve_manifest_host_prefix(manifest, fallback=normalized_platform.upper())

    def get_comic_dir(
        self,
        comic_id: str,
        author: str = None,
        title: str = None,
        base_dir: str = None,
    ) -> str:
        platform, original_id = self._split_comic_id(comic_id)
        return self._delegate.get_comic_dir(
            self._resolve_delegate_platform(platform),
            original_id,
            author=author,
            title=title,
            base_dir=base_dir,
        )

    def get_cover_url(self, comic_id: str):
        platform, original_id = self._split_comic_id(comic_id)
        return self._delegate.get_cover_url(
            self._resolve_delegate_platform(platform),
            original_id,
        )

    def get_image_url(self, comic_id: str, page: int):
        platform, original_id = self._split_comic_id(comic_id)
        return self._delegate.get_image_url(
            self._resolve_delegate_platform(platform),
            original_id,
            page,
        )

    def get_preview_image_urls(self, comic_id: str, preview_pages: List[int]):
        platform, original_id = self._split_comic_id(comic_id)
        return self._delegate.get_preview_image_urls(
            self._resolve_delegate_platform(platform),
            original_id,
            preview_pages,
        )

    def download_album(
        self,
        comic_id: str,
        download_dir: str,
        show_progress: bool = False,
        **kwargs,
    ):
        platform, original_id = self._split_comic_id(comic_id)
        return self._delegate.download_album(
            self._resolve_delegate_platform(platform),
            original_id,
            download_dir=download_dir,
            show_progress=show_progress,
            **kwargs,
        )

    def download_cover(
        self,
        comic_id: str,
        save_path: str,
        show_progress: bool = False,
    ):
        platform, original_id = self._split_comic_id(comic_id)
        return self._delegate.download_cover(
            self._resolve_delegate_platform(platform),
            original_id,
            save_path=save_path,
            show_progress=show_progress,
        )

    def get_album_by_id(self, comic_id: str):
        platform, original_id = self._split_comic_id(comic_id)
        return self._delegate.get_album_by_id(
            self._resolve_delegate_platform(platform),
            original_id,
        )

    def search_albums(
        self,
        platform: Any,
        keyword: str,
        max_pages: int = 1,
    ):
        return self._delegate.search_albums(
            self._resolve_delegate_platform(platform),
            keyword,
            max_pages=max_pages,
        )

    def get_favorites(self, platform: Any):
        return self._delegate.get_favorites(self._resolve_delegate_platform(platform))

    def list_available_platforms(self) -> List[str]:
        platforms: List[str] = []
        for manifest in get_protocol_gateway().list_manifests(media_type="comic"):
            label = resolve_manifest_platform_label(manifest)
            if not label:
                continue
            if label not in platforms:
                platforms.append(label)
        return platforms


platform_service = PlatformService()


def get_platform_service() -> PlatformService:
    return platform_service
