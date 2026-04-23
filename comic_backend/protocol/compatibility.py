from __future__ import annotations

from typing import Any, Optional

from .gateway import get_protocol_gateway


def _default_query_status() -> dict:
    return {
        "configured": True,
        "message": "",
        "missing_fields": [],
    }


def _normalize_lookup_name(name: Any) -> str:
    return str(getattr(name, "value", name) or "").strip().lower()


def _manifest_matches_name(manifest, lookup: str) -> bool:
    if manifest is None or not lookup:
        return False

    list_lookup_names = getattr(manifest, "list_lookup_names", None)
    if callable(list_lookup_names):
        candidates = {
            str(item or "").strip().lower()
            for item in list_lookup_names()
            if str(item or "").strip()
        }
    else:
        identity = dict(getattr(manifest, "identity", {}) or {})
        candidates = {
            str(getattr(manifest, "plugin_id", "") or "").strip().lower(),
            str(getattr(manifest, "config_key", "") or "").strip().lower(),
            str(getattr(manifest, "name", "") or "").strip().lower(),
            str(identity.get("platform_label") or "").strip().lower(),
            str(identity.get("host_id_prefix") or "").strip().lower(),
        }
        candidates.update(
            str(item or "").strip().lower()
            for item in (getattr(manifest, "identity_aliases", []) or [])
            if str(item or "").strip()
        )
    candidates.discard("")
    return lookup in candidates


def _find_manifest_by_name(
    name: Any,
    *,
    media_type: Optional[str] = None,
    capability: Optional[str] = None,
):
    lookup = _normalize_lookup_name(name)
    if not lookup:
        return None

    gateway = get_protocol_gateway()
    registry = getattr(gateway, "registry", None)

    direct_resolvers = []
    if registry is not None:
        direct_resolvers.extend(
            [
                lambda: registry.find_by_lookup_name(
                    lookup,
                    media_type=media_type,
                    capability=capability,
                ),
                lambda: registry.find_by_config_key(lookup),
            ]
        )
    else:
        direct_resolvers.extend(
            [
                lambda: gateway.get_manifest_by_lookup(
                    lookup,
                    media_type=media_type,
                    capability=capability,
                ),
                lambda: gateway.get_manifest_by_config_key(lookup),
            ]
        )

    for resolve in direct_resolvers:
        try:
            manifest = resolve()
        except Exception:
            manifest = None
        if manifest is None:
            continue
        if media_type:
            manifest_media_types = {
                str(item or "").strip().lower()
                for item in (getattr(manifest, "media_types", []) or [])
                if str(item or "").strip()
            }
            if str(media_type or "").strip().lower() not in manifest_media_types:
                continue
        if capability and not bool(getattr(manifest, "has_capability", lambda *_args, **_kwargs: False)(capability)):
            continue
        return manifest

    for manifest in gateway.list_manifests(media_type=media_type, capability=capability):
        if _manifest_matches_name(manifest, lookup):
            return manifest
    return None


def get_plugin_id_for_adapter_name(adapter_name: str) -> Optional[str]:
    manifest = _find_manifest_by_name(adapter_name)
    return str(getattr(manifest, "plugin_id", "") or "").strip() or None


def get_plugin_id_for_comic_platform(platform: Any) -> Optional[str]:
    manifest = _find_manifest_by_name(platform, media_type="comic")
    return str(getattr(manifest, "plugin_id", "") or "").strip() or None


def get_plugin_id_for_platform(platform: Any) -> Optional[str]:
    manifest = _find_manifest_by_name(platform)
    return str(getattr(manifest, "plugin_id", "") or "").strip() or None


def get_plugin_id_for_video_platform(platform_name: str) -> Optional[str]:
    manifest = _find_manifest_by_name(platform_name, media_type="video")
    return str(getattr(manifest, "plugin_id", "") or "").strip() or None


def get_query_status_for_adapter_name(adapter_name: str) -> dict:
    plugin_id = get_plugin_id_for_adapter_name(adapter_name)
    if not plugin_id:
        return _default_query_status()
    return get_protocol_gateway().get_query_status(plugin_id)


def get_query_status_for_platform(platform: Any) -> dict:
    plugin_id = get_plugin_id_for_platform(platform)
    if not plugin_id:
        return _default_query_status()
    return get_protocol_gateway().get_query_status(plugin_id)


def get_query_status_for_comic_platform(platform: Any) -> dict:
    plugin_id = get_plugin_id_for_comic_platform(platform)
    if not plugin_id:
        return _default_query_status()
    return get_protocol_gateway().get_query_status(plugin_id)


def get_query_status_for_video_platform(platform_name: str) -> dict:
    plugin_id = get_plugin_id_for_video_platform(platform_name)
    if not plugin_id:
        return _default_query_status()
    return get_protocol_gateway().get_query_status(plugin_id)


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


def get_missav_client(*args, **kwargs):
    return get_playback_proxy_client(*args, **kwargs)


def get_playback_proxy_client(*args, **kwargs):
    gateway = get_protocol_gateway()
    for manifest in gateway.list_manifests(media_type="video", capability="playback.proxy.stream"):
        plugin_id = str(getattr(manifest, "plugin_id", "") or "").strip()
        if not plugin_id:
            continue
        try:
            return gateway.get_client(plugin_id, *args, **kwargs)
        except Exception:
            continue
    raise ValueError("unsupported video proxy client")


def get_preview_request_client(*args, **kwargs):
    return get_playback_proxy_client(*args, **kwargs)
