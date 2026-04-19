from __future__ import annotations

import json
import os
from typing import Dict, List, Optional

from infrastructure.logger import app_logger, error_logger

from .base import PluginManifest


class PluginRegistry:
    def __init__(self, search_root: Optional[str] = None):
        default_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "third_party"))
        self.search_root = os.path.abspath(search_root or default_root)
        self._manifests: Dict[str, PluginManifest] = {}
        self._loaded = False

    def _validate_manifest(self, payload: dict, path: str) -> PluginManifest:
        manifest = PluginManifest(raw=dict(payload or {}), path=os.path.abspath(path))
        if manifest.protocol_version != "1.0":
            raise ValueError(f"unsupported protocol version: {manifest.protocol_version}")
        if not manifest.plugin_id:
            raise ValueError("missing plugin.id")
        if not manifest.entrypoint:
            raise ValueError("missing plugin.entrypoint")
        return manifest

    def refresh(self) -> None:
        manifests: Dict[str, PluginManifest] = {}
        if not os.path.exists(self.search_root):
            self._manifests = manifests
            self._loaded = True
            return

        for root, _dirs, files in os.walk(self.search_root):
            if "ultimate-plugin.json" not in files:
                continue

            path = os.path.join(root, "ultimate-plugin.json")
            try:
                with open(path, "r", encoding="utf-8") as f:
                    payload = json.load(f)
                manifest = self._validate_manifest(payload, path)
                manifests[manifest.plugin_id] = manifest
            except Exception as exc:
                error_logger.error(f"load protocol manifest failed: {path}, error={exc}")

        self._manifests = manifests
        self._loaded = True
        app_logger.info(f"protocol registry loaded plugins: {sorted(self._manifests.keys())}")

    def _ensure_loaded(self) -> None:
        if not self._loaded:
            self.refresh()

    def list_manifests(self, media_type: Optional[str] = None, capability: Optional[str] = None) -> List[PluginManifest]:
        self._ensure_loaded()
        manifests = list(self._manifests.values())
        if media_type:
            media_key = str(media_type or "").strip().lower()
            manifests = [
                item for item in manifests
                if media_key in {str(mt or "").strip().lower() for mt in item.media_types}
            ]
        if capability:
            manifests = [item for item in manifests if item.has_capability(capability)]
        return sorted(manifests, key=lambda item: (item.order, item.plugin_id))

    def get_manifest(self, plugin_id: str) -> PluginManifest:
        self._ensure_loaded()
        plugin_key = str(plugin_id or "").strip()
        manifest = self._manifests.get(plugin_key)
        if manifest is None:
            raise KeyError(f"unknown plugin: {plugin_key}")
        return manifest

    def find_by_config_key(self, config_key: str) -> Optional[PluginManifest]:
        lookup = str(config_key or "").strip().lower()
        if not lookup:
            return None
        for manifest in self.list_manifests():
            if str(manifest.config_key or "").strip().lower() == lookup:
                return manifest
        return None

    def find_by_legacy_platform(self, platform_name: str) -> Optional[PluginManifest]:
        lookup = str(platform_name or "").strip().lower()
        if not lookup:
            return None
        for manifest in self.list_manifests():
            legacy_platforms = {str(item or "").strip().lower() for item in manifest.legacy_platforms}
            if lookup in legacy_platforms:
                return manifest
        return None


_registry_singleton: Optional[PluginRegistry] = None


def get_plugin_registry() -> PluginRegistry:
    global _registry_singleton
    if _registry_singleton is None:
        _registry_singleton = PluginRegistry()
    return _registry_singleton

