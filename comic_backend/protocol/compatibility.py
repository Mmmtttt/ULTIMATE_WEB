from __future__ import annotations

from typing import Any, Optional

from .gateway import get_protocol_gateway
from .host_service import get_protocol_host_service


def get_plugin_id_for_adapter_name(adapter_name: str) -> Optional[str]:
    return get_protocol_host_service().get_plugin_id(adapter_name, media_type="comic")


def get_plugin_id_for_comic_platform(platform: Any) -> Optional[str]:
    return get_protocol_host_service().get_plugin_id(platform, media_type="comic")


def get_plugin_id_for_platform(platform: Any) -> Optional[str]:
    return get_protocol_host_service().get_plugin_id(platform)


def get_plugin_id_for_video_platform(platform_name: str) -> Optional[str]:
    return get_protocol_host_service().get_plugin_id(platform_name, media_type="video")


def get_query_status_for_adapter_name(adapter_name: str) -> dict:
    return get_protocol_host_service().get_query_status(adapter_name, media_type="comic")


def get_query_status_for_platform(platform: Any) -> dict:
    return get_protocol_host_service().get_query_status(platform)


def get_query_status_for_comic_platform(platform: Any) -> dict:
    return get_protocol_host_service().get_query_status(platform, media_type="comic")


def get_query_status_for_video_platform(platform_name: str) -> dict:
    return get_protocol_host_service().get_query_status(platform_name, media_type="video")


def get_client_for_config_key(config_key: str, *args, **kwargs):
    plugin_id = get_plugin_id_for_adapter_name(config_key)
    if not plugin_id:
        raise ValueError(f"unsupported adapter: {config_key}")
    return get_protocol_gateway().get_client(plugin_id, *args, **kwargs)


def get_client_for_comic_platform(platform: Any, *args, **kwargs):
    plugin_id = get_plugin_id_for_comic_platform(platform)
    if not plugin_id:
        raise ValueError(f"unsupported comic platform: {platform}")
    return get_protocol_gateway().get_client(plugin_id, *args, **kwargs)


def get_video_client(platform_name: str, *args, **kwargs):
    plugin_id = get_plugin_id_for_video_platform(platform_name)
    if not plugin_id:
        raise ValueError(f"unsupported video platform: {platform_name}")
    return get_protocol_gateway().get_client(plugin_id, *args, **kwargs)


def get_playback_proxy_client(*args, **kwargs):
    gateway = get_protocol_gateway()
    manifests = list(gateway.list_manifests(media_type="video", capability="playback.proxy.stream"))
    if not manifests:
        raise ValueError("unsupported video proxy client")
    plugin_id = str(getattr(manifests[0], "plugin_id", "") or "").strip()
    return gateway.get_client(plugin_id, *args, **kwargs)


def get_preview_request_client(*args, **kwargs):
    gateway = get_protocol_gateway()
    manifests = list(gateway.list_manifests(media_type="video", capability="transport.http.request"))
    if not manifests:
        return get_playback_proxy_client(*args, **kwargs)
    plugin_id = str(getattr(manifests[0], "plugin_id", "") or "").strip()
    return gateway.get_client(plugin_id, *args, **kwargs)
