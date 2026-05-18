from __future__ import annotations

import json
import os
import sys
from copy import deepcopy
from typing import Any, Dict, List, Optional

from infrastructure.logger import app_logger, error_logger

from .base import PluginManifest
from core.constants import BACKEND_ROOT, PROJECT_ROOT

_HOST_OVERLAY_FILENAME = "ultimate-host.json"
_SNAPSHOT_ENV_KEYS = (
    "ULTIMATE_PROTOCOL_SNAPSHOT_PATH",
    "BACKEND_PROTOCOL_SNAPSHOT_PATH",
)
_PLUGIN_ROOT_ENV_KEYS = (
    "ULTIMATE_PLUGIN_ROOTS",
    "BACKEND_PLUGIN_ROOTS",
)
_SNAPSHOT_FILENAME = "mobile_protocol_snapshot.json"
_METADATA_ONLY_ENTRYPOINT = "protocol.snapshot_provider:MetadataOnlyProvider"


def _deep_merge(base: Any, override: Any) -> Any:
    if isinstance(base, dict) and isinstance(override, dict):
        merged = {key: deepcopy(value) for key, value in base.items()}
        for key, value in override.items():
            merged[key] = _deep_merge(merged.get(key), value)
        return merged
    if override is None:
        return deepcopy(base)
    return deepcopy(override)


class PluginRegistry:
    def __init__(self, search_root: Optional[str] = None):
        self.search_root = os.path.abspath(search_root) if search_root else None
        self._manifests: Dict[str, PluginManifest] = {}
        self._loaded = False

    def _get_search_roots(self) -> List[str]:
        if self.search_root:
            return [self.search_root]

        candidates: List[str] = []

        for env_key in _PLUGIN_ROOT_ENV_KEYS:
            raw_value = str(os.environ.get(env_key, "") or "").strip()
            if not raw_value:
                continue
            for item in raw_value.split(os.pathsep):
                normalized = os.path.abspath(str(item or "").strip())
                if normalized:
                    candidates.append(normalized)

        candidates.extend(
            [
                os.path.abspath(os.path.join(PROJECT_ROOT, "plugins")),
                os.path.abspath(os.path.join(BACKEND_ROOT, "plugins")),
            ]
        )

        candidates.extend([
            os.path.abspath(os.path.join(BACKEND_ROOT, "third_party")),
            os.path.abspath(os.path.join(PROJECT_ROOT, "backend_source", "third_party")),
            os.path.abspath(os.path.join(PROJECT_ROOT, "comic_backend", "third_party")),
            os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "third_party")),
        ])

        meipass_root = str(getattr(sys, "_MEIPASS", "") or "").strip()
        if meipass_root:
            candidates.extend(
                [
                    os.path.abspath(os.path.join(meipass_root, "plugins")),
                    os.path.abspath(os.path.join(meipass_root, "comic_backend", "third_party")),
                    os.path.abspath(os.path.join(meipass_root, "third_party")),
                ]
            )

        deduped: List[str] = []
        seen = set()
        for candidate in candidates:
            normalized = os.path.abspath(str(candidate or "").strip())
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            deduped.append(normalized)
        return deduped

    def _validate_manifest(self, payload: dict, path: str) -> PluginManifest:
        manifest = PluginManifest(raw=dict(payload or {}), path=os.path.abspath(path))
        if manifest.protocol_version not in {"1.0", "1.1", "2.0"}:
            raise ValueError(f"unsupported protocol version: {manifest.protocol_version}")
        if not manifest.plugin_id:
            raise ValueError("missing plugin.id")
        if not manifest.entrypoint:
            raise ValueError("missing plugin.entrypoint")
        return manifest

    @staticmethod
    def _normalize_plugin_key(payload: dict) -> str:
        plugin = dict((payload or {}).get("plugin") or {})
        return str(plugin.get("id") or "").strip()

    def _get_snapshot_candidates(self) -> List[str]:
        candidates: List[str] = []
        for env_key in _SNAPSHOT_ENV_KEYS:
            env_value = str(os.environ.get(env_key, "") or "").strip()
            if env_value:
                candidates.append(os.path.abspath(env_value))

        candidates.extend(
            [
                os.path.abspath(os.path.join(os.path.dirname(__file__), _SNAPSHOT_FILENAME)),
                os.path.abspath(os.path.join(BACKEND_ROOT, "protocol", _SNAPSHOT_FILENAME)),
                os.path.abspath(os.path.join(PROJECT_ROOT, "backend_source", "protocol", _SNAPSHOT_FILENAME)),
                os.path.abspath(os.path.join(PROJECT_ROOT, "comic_backend", "protocol", _SNAPSHOT_FILENAME)),
            ]
        )

        deduped: List[str] = []
        seen = set()
        for candidate in candidates:
            normalized = os.path.abspath(str(candidate or "").strip())
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            deduped.append(normalized)
        return deduped

    def _load_snapshot_payloads(self) -> tuple[Dict[str, dict], str]:
        for candidate in self._get_snapshot_candidates():
            if not os.path.isfile(candidate):
                continue
            try:
                with open(candidate, "r", encoding="utf-8") as f:
                    payload = json.load(f)
                raw_manifests = payload.get("manifests") or payload.get("plugins") or []
                manifest_map: Dict[str, dict] = {}
                for item in raw_manifests:
                    if not isinstance(item, dict):
                        continue
                    plugin_key = self._normalize_plugin_key(item)
                    if not plugin_key:
                        continue
                    manifest_map[plugin_key] = dict(item)
                if manifest_map:
                    return manifest_map, candidate
            except Exception as exc:
                error_logger.error(f"load protocol snapshot failed: {candidate}, error={exc}")
        return {}, ""

    def _scan_manifest_payloads(self, filename: str) -> Dict[str, Dict[str, Any]]:
        payloads: Dict[str, Dict[str, Any]] = {}
        for search_root in self._get_search_roots():
            if not os.path.exists(search_root):
                continue
            for root, _dirs, files in os.walk(search_root):
                if filename not in files:
                    continue
                path = os.path.join(root, filename)
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        payload = json.load(f)
                    plugin_key = self._normalize_plugin_key(payload)
                    if not plugin_key:
                        raise ValueError("missing plugin.id")
                    payloads.setdefault(
                        plugin_key,
                        {
                            "payload": dict(payload),
                            "path": os.path.abspath(path),
                        },
                    )
                except Exception as exc:
                    error_logger.error(f"load protocol payload failed: {path}, error={exc}")
        return payloads

    def _build_metadata_only_manifest(self, plugin_id: str, overlay_payload: dict) -> dict:
        payload = dict(overlay_payload or {})
        plugin = dict(payload.get("plugin") or {})
        inferred_config_key = str(plugin.get("config_key") or "").strip()
        if not inferred_config_key and "." in plugin_id:
            inferred_config_key = plugin_id.rsplit(".", 1)[-1]

        payload["protocol_version"] = str(payload.get("protocol_version") or "2.0").strip() or "2.0"
        payload["plugin"] = {
            "id": plugin_id,
            "name": str(plugin.get("name") or "").strip() or plugin_id,
            "version": str(plugin.get("version") or "").strip() or "0.0.0-metadata",
            "config_key": inferred_config_key,
            "entrypoint": str(plugin.get("entrypoint") or "").strip() or _METADATA_ONLY_ENTRYPOINT,
        }
        media_types = payload.get("media_types") or []
        if not isinstance(media_types, list):
            media_types = []
        if not media_types:
            if plugin_id.startswith("video."):
                media_types = ["video"]
            elif plugin_id.startswith("comic."):
                media_types = ["comic"]
        payload["media_types"] = [
            str(item or "").strip()
            for item in media_types
            if str(item or "").strip()
        ]
        payload.setdefault("capabilities", [])
        return payload

    def refresh(self) -> None:
        manifests: Dict[str, PluginManifest] = {}
        search_roots = self._get_search_roots()
        snapshot_payloads, snapshot_path = self._load_snapshot_payloads()
        file_payloads = self._scan_manifest_payloads("ultimate-plugin.json")
        overlay_payloads = self._scan_manifest_payloads(_HOST_OVERLAY_FILENAME)

        merged_payloads: Dict[str, dict] = {plugin_id: dict(raw) for plugin_id, raw in snapshot_payloads.items()}
        merged_paths: Dict[str, str] = {
            plugin_id: snapshot_path
            for plugin_id in snapshot_payloads.keys()
            if snapshot_path
        }

        for plugin_id, item in file_payloads.items():
            payload = dict(item.get("payload") or {})
            merged_payloads[plugin_id] = _deep_merge(merged_payloads.get(plugin_id, {}), payload)
            merged_paths[plugin_id] = str(item.get("path") or "").strip() or merged_paths.get(plugin_id, "")

        for plugin_id, item in overlay_payloads.items():
            payload = dict(item.get("payload") or {})
            if plugin_id not in merged_payloads:
                merged_payloads[plugin_id] = self._build_metadata_only_manifest(plugin_id, payload)
                merged_paths[plugin_id] = str(item.get("path") or "").strip() or merged_paths.get(plugin_id, "")
                continue
            merged_payloads[plugin_id] = _deep_merge(merged_payloads.get(plugin_id, {}), payload)

        for plugin_id, payload in merged_payloads.items():
            manifest_path = merged_paths.get(plugin_id) or os.path.abspath(
                os.path.join(BACKEND_ROOT, "third_party", plugin_id.replace(".", "_"))
            )
            try:
                manifest = self._validate_manifest(payload, manifest_path)
                manifests.setdefault(manifest.plugin_id, manifest)
            except Exception as exc:
                error_logger.error(
                    f"load protocol manifest failed: plugin_id={plugin_id}, path={manifest_path}, error={exc}"
                )

        self._manifests = manifests
        self._loaded = True
        app_logger.info(
            f"protocol registry loaded plugins: {sorted(self._manifests.keys())}, "
            f"search_roots={search_roots}, snapshot={snapshot_path or 'none'}"
        )

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

    def find_by_lookup_name(
        self,
        lookup_name: str,
        media_type: Optional[str] = None,
        capability: Optional[str] = None,
    ) -> Optional[PluginManifest]:
        lookup = str(lookup_name or "").strip().lower()
        if not lookup:
            return None
        for manifest in self.list_manifests(media_type=media_type, capability=capability):
            candidates = {
                str(item or "").strip().lower()
                for item in manifest.list_lookup_names()
                if str(item or "").strip()
            }
            candidates.discard("")
            if lookup in candidates:
                return manifest
        return None


_registry_singleton: Optional[PluginRegistry] = None


def get_plugin_registry() -> PluginRegistry:
    global _registry_singleton
    if _registry_singleton is None:
        _registry_singleton = PluginRegistry()
    return _registry_singleton
