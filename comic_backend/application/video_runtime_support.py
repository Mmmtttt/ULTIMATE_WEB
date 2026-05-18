from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from application.config_app_service import ConfigAppService
from protocol.host_service import ProtocolVideoClient, get_protocol_host_service


_config_service = ConfigAppService()


def _get_video_service_cls():
    from application.video_app_service import VideoAppService

    return VideoAppService


def get_default_video_platform_name() -> str:
    return get_protocol_host_service().get_default_video_platform_name()


def resolve_video_manifest_or_error(
    platform_name: str = "",
    *,
    capability: Optional[str] = "catalog.search",
):
    return get_protocol_host_service().resolve_video_manifest(platform_name, capability=capability)


def execute_video_plugin_capability(
    platform_name: str,
    capability: str,
    params: Optional[Dict[str, Any]] = None,
    *args,
    **kwargs,
):
    return get_protocol_host_service().execute_video_capability(
        platform_name,
        capability,
        params,
        *args,
        **kwargs,
    )


def get_video_platform_query_status(platform_name: str = "") -> Dict[str, Any]:
    return get_protocol_host_service().get_video_query_status(platform_name)


def resolve_video_lookup_context(
    *,
    video_id: str = "",
    code: str = "",
    platform_name: str = "",
) -> Tuple[str, str, Any]:
    return get_protocol_host_service().resolve_video_lookup_context(
        video_id=video_id,
        code=code,
        platform_name=platform_name,
    )


def build_video_host_id(platform_name: str, original_id: str) -> str:
    return get_protocol_host_service().build_video_host_id(platform_name, original_id)


def get_video_adapter(platform_name: str = "", *args, capability: str = "catalog.search", **kwargs) -> ProtocolVideoClient:
    return get_protocol_host_service().get_video_client(
        platform_name,
        *args,
        capability=capability,
        **kwargs,
    )


def get_playback_proxy_client(*args, **kwargs):
    return get_protocol_host_service().get_playback_proxy_client(*args, **kwargs)


def get_preview_request_client(*args, **kwargs):
    return get_protocol_host_service().get_preview_request_client(*args, **kwargs)


def sanitize_preview_video_value(raw_url: str) -> str:
    return _get_video_service_cls()._sanitize_preview_video_url(raw_url)


def to_proxy_image_url(
    url: str,
    *,
    asset_kind: str = "image",
    video_id: str = "",
    platform_name: str = "",
    content_id: str = "",
) -> str:
    return _get_video_service_cls().to_frontend_asset_url(
        url,
        asset_kind=asset_kind,
        video_id=video_id,
        platform_name=platform_name,
        content_id=content_id,
        proxy_base_path="/api/v1/video/proxy2",
    )


def platform_allows_preview_video_download(platform: str = "", video_id: str = "") -> bool:
    return _get_video_service_cls()._video_platform_allows_preview_download(
        video_id=video_id,
        platform_name=platform,
    )


def _get_preview_import_auto_download_enabled() -> bool:
    try:
        result = _config_service.get_config()
        if not result.success or not isinstance(result.data, dict):
            return True
        return bool(result.data.get("auto_download_preview_assets_for_preview_import", False))
    except Exception:
        return True


def _should_auto_download_preview_assets(source: str = "local") -> bool:
    return str(source or "").strip().lower() != "preview" or _get_preview_import_auto_download_enabled()


def schedule_video_asset_cache(
    *,
    video_id: str,
    source: str,
    cover_url: str = "",
    preview_video: str = "",
    thumbnail_images=None,
    allow_cover: bool = True,
    allow_preview_video: bool = True,
    video_service: Optional[Any] = None,
) -> None:
    if not video_id:
        return

    video_service_cls = _get_video_service_cls()
    service = video_service or video_service_cls()
    cover = str(cover_url or "").strip()
    preview = sanitize_preview_video_value(preview_video or "")
    thumbs = [str(item or "").strip() for item in (thumbnail_images or []) if str(item or "").strip()]
    auto_download_enabled = _should_auto_download_preview_assets(source)
    allow_preview_video = bool(allow_preview_video) and platform_allows_preview_video_download(video_id=video_id)

    if allow_cover and cover:
        service.cache_cover_to_static_async(video_id, cover, source=source)

    if not auto_download_enabled:
        return

    if thumbs:
        service.cache_thumbnail_images_async(video_id, thumbs, source=source)

    if allow_preview_video and preview:
        service.cache_preview_video_async(video_id, preview, source=source)
