from __future__ import annotations

import os
from typing import Any, Dict, Optional, Tuple

from .gateway import get_protocol_gateway


_LEGACY_PLATFORM_PREFIXES = (
    ("JAVBUS", "JAVBUS"),
    ("JAVDB", "JAVDB"),
    ("JM", "JM"),
    ("PK", "PK"),
)


def resolve_platform_manifest(
    platform_name: str,
    media_type: Optional[str] = None,
    capability: Optional[str] = None,
):
    normalized_name = str(platform_name or "").strip()
    normalized_media_type = str(media_type or "").strip().lower()
    if not normalized_name:
        return None

    gateway = get_protocol_gateway()
    manifest = gateway.get_manifest_by_legacy_platform(
        normalized_name,
        media_type=normalized_media_type or None,
        capability=capability,
    )
    if manifest is not None:
        return manifest

    manifest = gateway.get_manifest_by_config_key(normalized_name)
    if manifest is None:
        return None

    if normalized_media_type:
        manifest_media_types = {
            str(item or "").strip().lower()
            for item in (manifest.media_types or [])
            if str(item or "").strip()
        }
        if normalized_media_type not in manifest_media_types:
            return None
    return manifest


def get_default_platform_manifest(
    media_type: Optional[str] = None,
    capability: Optional[str] = None,
):
    manifests = list(
        get_protocol_gateway().list_manifests(
            media_type=str(media_type or "").strip().lower() or None,
            capability=capability,
        )
    )
    return manifests[0] if manifests else None


def get_default_platform_label(
    media_type: Optional[str] = None,
    capability: Optional[str] = None,
    fallback: str = "",
) -> str:
    manifest = get_default_platform_manifest(media_type=media_type, capability=capability)
    return resolve_manifest_platform_label(manifest, fallback=fallback)


def resolve_manifest_platform_label(manifest, fallback: str = "") -> str:
    identity = dict(getattr(manifest, "identity", {}) or {})
    for candidate in (
        identity.get("platform_label"),
        identity.get("host_id_prefix"),
        *(getattr(manifest, "legacy_platforms", []) or []),
        getattr(manifest, "config_key", ""),
        getattr(manifest, "name", ""),
    ):
        normalized = str(candidate or "").strip()
        if normalized:
            return normalized.upper()
    return str(fallback or "").strip().upper()


def resolve_manifest_host_prefix(manifest, fallback: str = "") -> str:
    identity = dict(getattr(manifest, "identity", {}) or {})
    host_prefix = str(identity.get("host_id_prefix") or "").strip().upper()
    if host_prefix:
        return host_prefix
    return resolve_manifest_platform_label(manifest, fallback=fallback)


def resolve_manifest_media_type(manifest) -> str:
    media_types = {
        str(item or "").strip().lower()
        for item in (getattr(manifest, "media_types", []) or [])
        if str(item or "").strip()
    }
    if "video" in media_types:
        return "video"
    return "comic"


def build_prefixed_id(host_prefix: str, original_id: str) -> str:
    normalized_prefix = str(host_prefix or "").strip().upper()
    normalized_original_id = str(original_id or "").strip()
    if not normalized_prefix or not normalized_original_id:
        return normalized_original_id
    if normalized_original_id.upper().startswith(normalized_prefix):
        return normalized_original_id
    return f"{normalized_prefix}{normalized_original_id}"


def build_platform_root_dir(root_dir: str, manifest=None, platform_name: str = "") -> str:
    host_prefix = resolve_manifest_host_prefix(manifest, fallback=platform_name)
    if not host_prefix:
        return os.path.abspath(root_dir)
    return os.path.abspath(os.path.join(root_dir, host_prefix))


def get_capability_default_params(manifest, capability: str) -> Dict[str, Any]:
    if manifest is None or not hasattr(manifest, "get_capability_entry"):
        return {}
    entry = dict(manifest.get_capability_entry(capability) or {})
    raw_params = entry.get("default_params") or {}
    return dict(raw_params) if isinstance(raw_params, dict) else {}


def _split_legacy_prefixed_id(content_id: str) -> Tuple[str, str]:
    normalized_id = str(content_id or "").strip()
    upper_id = normalized_id.upper()
    for prefix, platform_label in _LEGACY_PLATFORM_PREFIXES:
        if upper_id.startswith(prefix):
            return platform_label, normalized_id[len(prefix):]
    return "", normalized_id


def split_prefixed_id(content_id: str, media_type: Optional[str] = None) -> Tuple[str, str, Any]:
    normalized_id = str(content_id or "").strip()
    normalized_media_type = str(media_type or "").strip().lower()
    if not normalized_id:
        return "", "", None

    if normalized_id.upper().startswith("LOCAL"):
        manifest = get_default_platform_manifest(media_type=normalized_media_type or "comic")
        platform_label = resolve_manifest_platform_label(manifest, fallback="")
        return platform_label, normalized_id, manifest

    manifests = list(get_protocol_gateway().list_manifests(media_type=normalized_media_type or None))
    prefix_entries = []
    for manifest in manifests:
        prefix = resolve_manifest_host_prefix(manifest)
        if prefix:
            prefix_entries.append((len(prefix), prefix.upper(), manifest))

    prefix_entries.sort(key=lambda item: item[0], reverse=True)
    upper_id = normalized_id.upper()
    for _length, prefix, manifest in prefix_entries:
        if upper_id.startswith(prefix):
            return (
                resolve_manifest_platform_label(manifest, fallback=prefix),
                normalized_id[len(prefix):],
                manifest,
            )

    platform_name, original_id = _split_legacy_prefixed_id(normalized_id)
    manifest = resolve_platform_manifest(platform_name, media_type=normalized_media_type or None) if platform_name else None
    return platform_name, str(original_id or "").strip(), manifest
