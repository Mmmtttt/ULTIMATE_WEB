from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Iterable, Optional

from .base import PluginManifest
from .gateway import get_protocol_gateway


def _deep_merge(base: Any, override: Any) -> Any:
    if isinstance(base, dict) and isinstance(override, dict):
        merged = {key: deepcopy(value) for key, value in base.items()}
        for key, value in override.items():
            merged[key] = _deep_merge(merged.get(key), value)
        return merged
    if override is None:
        return deepcopy(base)
    return deepcopy(override)


def resolve_manifest(
    plugin_id: str | None = None,
    platform_name: str | None = None,
    media_type: str | None = None,
    capability: str | None = None,
) -> Optional[PluginManifest]:
    gateway = get_protocol_gateway()

    if plugin_id:
        try:
            manifest = gateway.registry.get_manifest(str(plugin_id or "").strip())
        except Exception:
            manifest = None
    else:
        manifest = gateway.get_manifest_by_legacy_platform(
            str(platform_name or "").strip(),
            media_type=media_type,
            capability=capability,
        )

    if manifest is None:
        return None

    if media_type:
        manifest_media_types = {str(item or "").strip().lower() for item in manifest.media_types}
        if str(media_type or "").strip().lower() not in manifest_media_types:
            return None

    if capability and not manifest.has_capability(capability):
        return None

    return manifest


def build_item_display(manifest: PluginManifest, item: Dict[str, Any] | None = None) -> Dict[str, Any]:
    raw_item = dict(item or {})
    default_display = dict((manifest.presentation or {}).get("media_card") or {})
    item_display = dict(raw_item.get("display") or {})
    merged = _deep_merge(default_display, item_display)
    return merged if isinstance(merged, dict) else {}


def annotate_item(
    item: Dict[str, Any] | None,
    *,
    plugin_id: str | None = None,
    platform_name: str | None = None,
    media_type: str | None = None,
    capability: str | None = None,
) -> Dict[str, Any]:
    annotated = dict(item or {})
    manifest = resolve_manifest(
        plugin_id=plugin_id,
        platform_name=platform_name,
        media_type=media_type,
        capability=capability,
    )
    if manifest is None:
        return annotated

    display = build_item_display(manifest, annotated)
    if display:
        annotated["display"] = display

    annotated.setdefault("plugin_id", manifest.plugin_id)
    annotated.setdefault("plugin_name", manifest.name)

    display_badge = dict(display.get("badge") or {})
    badge_label = str(display_badge.get("label") or "").strip()
    identity_label = str((manifest.identity or {}).get("platform_label") or "").strip()
    if not annotated.get("platform"):
        annotated["platform"] = badge_label or identity_label or manifest.name

    return annotated


def annotate_items(
    items: Iterable[Dict[str, Any]] | None,
    *,
    plugin_id: str | None = None,
    platform_name: str | None = None,
    media_type: str | None = None,
    capability: str | None = None,
) -> list[Dict[str, Any]]:
    return [
        annotate_item(
            item,
            plugin_id=plugin_id,
            platform_name=platform_name,
            media_type=media_type,
            capability=capability,
        )
        for item in (items or [])
    ]
