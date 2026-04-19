from __future__ import annotations

from typing import Optional

from core.platform import Platform

from .gateway import get_protocol_gateway


COMIC_PLATFORM_PLUGIN_MAP = {
    Platform.JM: "comic.jmcomic",
    Platform.PK: "comic.picacomic",
}

GENERAL_PLATFORM_PLUGIN_MAP = {
    Platform.JM: "comic.jmcomic",
    Platform.PK: "comic.picacomic",
    Platform.JAVDB: "video.javdb",
}

VIDEO_PLATFORM_PLUGIN_MAP = {
    "javdb": "video.javdb",
    "javbus": "video.javbus",
}

ADAPTER_PLUGIN_MAP = {
    "jmcomic": "comic.jmcomic",
    "picacomic": "comic.picacomic",
    "javdb": "video.javdb",
}

MISSAV_PLUGIN_ID = "video.missav"


def _default_query_status() -> dict:
    return {
        "configured": True,
        "message": "",
        "missing_fields": [],
    }


def get_plugin_id_for_adapter_name(adapter_name: str) -> Optional[str]:
    return ADAPTER_PLUGIN_MAP.get(str(adapter_name or "").strip().lower())


def get_plugin_id_for_comic_platform(platform: Platform) -> Optional[str]:
    try:
        return COMIC_PLATFORM_PLUGIN_MAP.get(platform)
    except Exception:
        return None


def get_plugin_id_for_platform(platform: Platform) -> Optional[str]:
    try:
        return GENERAL_PLATFORM_PLUGIN_MAP.get(platform)
    except Exception:
        return None


def get_plugin_id_for_video_platform(platform_name: str) -> Optional[str]:
    return VIDEO_PLATFORM_PLUGIN_MAP.get(str(platform_name or "").strip().lower())


def get_query_status_for_adapter_name(adapter_name: str) -> dict:
    plugin_id = get_plugin_id_for_adapter_name(adapter_name)
    if not plugin_id:
        return _default_query_status()
    return get_protocol_gateway().get_query_status(plugin_id)


def get_query_status_for_platform(platform: Platform) -> dict:
    plugin_id = get_plugin_id_for_platform(platform)
    if not plugin_id:
        return _default_query_status()
    return get_protocol_gateway().get_query_status(plugin_id)


def get_query_status_for_comic_platform(platform: Platform) -> dict:
    plugin_id = get_plugin_id_for_comic_platform(platform)
    if not plugin_id:
        return _default_query_status()
    return get_protocol_gateway().get_query_status(plugin_id)


def get_query_status_for_video_platform(platform_name: str) -> dict:
    plugin_id = get_plugin_id_for_video_platform(platform_name)
    if not plugin_id:
        return _default_query_status()
    return get_protocol_gateway().get_query_status(plugin_id)


def get_legacy_adapter_for_config_key(adapter_name: str, *args, **kwargs):
    plugin_id = get_plugin_id_for_adapter_name(adapter_name)
    if not plugin_id:
        raise ValueError(f"unsupported adapter: {adapter_name}")
    return get_protocol_gateway().get_legacy_client(plugin_id, *args, **kwargs)


def get_legacy_adapter_for_comic_platform(platform: Platform, *args, **kwargs):
    plugin_id = get_plugin_id_for_comic_platform(platform)
    if not plugin_id:
        raise ValueError(f"unsupported comic platform: {platform}")
    return get_protocol_gateway().get_legacy_client(plugin_id, *args, **kwargs)


def get_legacy_video_adapter(platform_name: str, *args, **kwargs):
    plugin_id = get_plugin_id_for_video_platform(platform_name)
    if not plugin_id:
        raise ValueError(f"unsupported video platform: {platform_name}")
    return get_protocol_gateway().get_legacy_client(plugin_id, *args, **kwargs)


def get_legacy_missav_client(*args, **kwargs):
    return get_protocol_gateway().get_legacy_client(MISSAV_PLUGIN_ID, *args, **kwargs)
