from __future__ import annotations

import json
import os
from typing import Dict, Iterable, Optional

from core.constants import (
    DATA_DIR,
    THIRD_PARTY_CONFIG_PATH,
    normalize_to_data_dir,
)


class ProtocolConfigStore:
    """Protocol-native access to third_party_config.json."""

    def __init__(self, config_path: Optional[str] = None):
        self.config_path = os.path.abspath(str(config_path or THIRD_PARTY_CONFIG_PATH).strip())
        self._config: Dict[str, object] = {}
        self._loaded = False

    @staticmethod
    def _get_protocol_gateway():
        from .gateway import get_protocol_gateway

        return get_protocol_gateway()

    @classmethod
    def _list_protocol_manifests(cls):
        try:
            return [
                manifest
                for manifest in cls._get_protocol_gateway().list_manifests()
                if str(getattr(manifest, "config_key", "") or "").strip()
            ]
        except Exception:
            return []

    @staticmethod
    def _resolve_binding_field_name(binding: Dict[str, object]) -> str:
        return str(
            binding.get("config_field")
            or binding.get("field")
            or ""
        ).strip()

    @classmethod
    def _resolve_binding_default_abs_path(cls, manifest, binding: Dict[str, object]) -> str:
        relative_dir = str(binding.get("relative_dir") or "").strip().replace("\\", "/").strip("/")
        if not relative_dir:
            return ""

        identity = dict(getattr(manifest, "identity", {}) or {})
        host_prefix = str(
            binding.get("host_prefix")
            or identity.get("host_id_prefix")
            or identity.get("platform_label")
            or getattr(manifest, "config_key", "")
            or ""
        ).strip()
        if not host_prefix:
            return ""

        resolved_relative = relative_dir.format(
            host_prefix=host_prefix,
            config_key=str(getattr(manifest, "config_key", "") or "").strip(),
            plugin_id=str(getattr(manifest, "plugin_id", "") or "").strip(),
        ).replace("/", os.sep)
        return os.path.abspath(os.path.join(DATA_DIR, resolved_relative))

    @classmethod
    def _normalize_bound_path(cls, path_value: str, manifest, binding: Dict[str, object]) -> str:
        default_abs = cls._resolve_binding_default_abs_path(manifest, binding)
        if not default_abs:
            return str(path_value or "").strip()

        if path_value is None or str(path_value).strip() == "":
            return default_abs

        default_relative = ""
        try:
            data_root = os.path.abspath(DATA_DIR)
            if os.path.commonpath([data_root, default_abs]) == data_root:
                default_relative = os.path.relpath(default_abs, data_root).replace("\\", "/")
        except Exception:
            pass

        normalized = normalize_to_data_dir(path_value, default_relative)
        try:
            normalized_abs = os.path.abspath(normalized)
            data_root = os.path.abspath(DATA_DIR)
            if os.path.commonpath([data_root, normalized_abs]) == data_root:
                return default_abs
            normalized = normalized_abs
        except Exception:
            pass
        return normalized

    @classmethod
    def _build_manifest_default_config(cls, manifest) -> Dict[str, object]:
        config_key = str(getattr(manifest, "config_key", "") or "").strip()
        if not config_key:
            return {}

        defaults: Dict[str, object] = {}
        try:
            gateway = cls._get_protocol_gateway()
            defaults = gateway.provider_manager.normalize_config(manifest.plugin_id, {})
        except Exception:
            defaults = {}

        normalized_defaults = dict(defaults or {})
        for binding in manifest.list_data_dir_bindings():
            field_name = cls._resolve_binding_field_name(binding)
            default_abs = cls._resolve_binding_default_abs_path(manifest, binding)
            if field_name and default_abs:
                normalized_defaults.setdefault(field_name, default_abs)
        return normalized_defaults

    @classmethod
    def _get_default_adapter_key(cls) -> str:
        manifests = cls._list_protocol_manifests()
        for manifest in manifests:
            config_key = str(getattr(manifest, "config_key", "") or "").strip()
            media_types = {
                str(item or "").strip().lower()
                for item in (getattr(manifest, "media_types", []) or [])
                if str(item or "").strip()
            }
            if config_key and "comic" in media_types:
                return config_key

        if manifests:
            return str(getattr(manifests[0], "config_key", "") or "").strip()
        return "jmcomic"

    def _merge_protocol_defaults(self) -> bool:
        changed = False
        if not isinstance(self._config, dict):
            self._config = {}
            changed = True

        adapters = self._config.get("adapters")
        if not isinstance(adapters, dict):
            adapters = {}
            self._config["adapters"] = adapters
            changed = True

        current_default = str(self._config.get("default_adapter") or "").strip()
        if not current_default:
            self._config["default_adapter"] = self._get_default_adapter_key()
            changed = True

        for manifest in self._list_protocol_manifests():
            config_key = str(getattr(manifest, "config_key", "") or "").strip()
            if not config_key:
                continue

            existing_config = adapters.get(config_key)
            if not isinstance(existing_config, dict):
                existing_config = {}
                adapters[config_key] = existing_config
                changed = True

            defaults = self._build_manifest_default_config(manifest)
            merged = dict(existing_config)
            for field_name, field_value in defaults.items():
                if field_name not in merged:
                    merged[field_name] = field_value

            if merged != existing_config:
                adapters[config_key] = merged
                changed = True

        return changed

    def _normalize_storage_config_paths(self) -> bool:
        changed = False
        adapters = self._config.get("adapters", {})
        if not isinstance(adapters, dict):
            return False

        for manifest in self._list_protocol_manifests():
            config_key = str(getattr(manifest, "config_key", "") or "").strip()
            adapter_config = adapters.get(config_key)
            if not config_key or not isinstance(adapter_config, dict):
                continue

            for binding in manifest.list_data_dir_bindings():
                field_name = self._resolve_binding_field_name(binding)
                if not field_name:
                    continue
                normalized_path = self._normalize_bound_path(
                    adapter_config.get(field_name),
                    manifest,
                    binding,
                )
                if adapter_config.get(field_name) != normalized_path:
                    adapter_config[field_name] = normalized_path
                    changed = True

        return changed

    def _save_config(self) -> None:
        directory = os.path.dirname(self.config_path) or "."
        os.makedirs(directory, exist_ok=True)
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(self._config, f, ensure_ascii=False, indent=2)

    def _get_default_config(self) -> Dict[str, object]:
        self._config = {
            "default_adapter": "",
            "adapters": {},
        }
        self._merge_protocol_defaults()
        return dict(self._config)

    def _load_config(self) -> None:
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    self._config = json.load(f)
                changed = self._merge_protocol_defaults()
                if self._normalize_storage_config_paths():
                    changed = True
                if changed:
                    self._save_config()
            except Exception:
                self._config = self._get_default_config()
                self._save_config()
        else:
            self._config = self._get_default_config()
            self._save_config()
        self._loaded = True

    def _ensure_loaded(self) -> None:
        if not self._loaded:
            self._load_config()

    def reload(self):
        self._load_config()

    def get_plugin_config(self, config_key: str, reload: bool = False) -> Dict:
        if reload:
            self.reload()
        else:
            self._ensure_loaded()
        adapters = self._config.get("adapters", {})
        if not isinstance(adapters, dict):
            return {}
        return dict(adapters.get(str(config_key or "").strip(), {}) or {})

    def get_adapter_config(self, adapter_name: str, reload: bool = False) -> Dict:
        return self.get_plugin_config(adapter_name, reload=reload)

    def set_plugin_config(self, config_key: str, payload: Dict):
        self._ensure_loaded()
        normalized_key = str(config_key or "").strip()
        if not normalized_key:
            return

        adapters = self._config.setdefault("adapters", {})
        if not isinstance(adapters, dict):
            adapters = {}
            self._config["adapters"] = adapters

        existing_config = adapters.get(normalized_key, {})
        if not isinstance(existing_config, dict):
            existing_config = {}

        normalized_config = dict(existing_config)
        normalized_config.update(dict(payload or {}))

        manifest = None
        for candidate in self._list_protocol_manifests():
            if str(getattr(candidate, "config_key", "") or "").strip() == normalized_key:
                manifest = candidate
                break

        if manifest is not None:
            defaults = self._build_manifest_default_config(manifest)
            merged = dict(defaults)
            merged.update(normalized_config)
            normalized_config = merged
            for binding in manifest.list_data_dir_bindings():
                field_name = self._resolve_binding_field_name(binding)
                if not field_name:
                    continue
                normalized_config[field_name] = self._normalize_bound_path(
                    normalized_config.get(field_name),
                    manifest,
                    binding,
                )

        adapters[normalized_key] = normalized_config
        self._save_config()

    def set_adapter_config(self, adapter_name: str, payload: Dict):
        self.set_plugin_config(adapter_name, payload)

    def get_default_config_key(self) -> str:
        self._ensure_loaded()
        return str(self._config.get("default_adapter") or "").strip() or self._get_default_adapter_key()

    def get_default_adapter(self) -> str:
        return self.get_default_config_key()

    def set_default_config_key(self, config_key: str):
        self._ensure_loaded()
        self._config["default_adapter"] = str(config_key or "").strip()
        self._save_config()

    def set_default_adapter(self, adapter_name: str):
        self.set_default_config_key(adapter_name)

    @staticmethod
    def list_config_keys():
        store = ProtocolConfigStore()
        store._ensure_loaded()
        configured = set()
        adapters = store._config.get("adapters", {})
        if isinstance(adapters, dict):
            configured = {str(key or "").strip() for key in adapters.keys() if str(key or "").strip()}

        discovered = {
            str(getattr(manifest, "config_key", "") or "").strip()
            for manifest in store._list_protocol_manifests()
            if str(getattr(manifest, "config_key", "") or "").strip()
        }
        return sorted(configured | discovered)

    @staticmethod
    def reset_runtime_caches(config_keys: Optional[Iterable[str]] = None):
        from .gateway import get_protocol_gateway

        gateway = get_protocol_gateway()
        if config_keys is None:
            targets = {
                str(getattr(manifest, "config_key", "") or "").strip()
                for manifest in gateway.list_manifests()
                if str(getattr(manifest, "config_key", "") or "").strip()
            }
        else:
            targets = {str(item or "").strip() for item in config_keys if str(item or "").strip()}

        for config_key in targets:
            manifest = gateway.get_manifest_by_config_key(config_key)
            if manifest is None:
                continue
            gateway.provider_manager.reset_provider(manifest.plugin_id)

        try:
            from .adapter_api import reset_config_manager

            reset_config_manager()
        except Exception:
            pass


def get_protocol_config_store() -> ProtocolConfigStore:
    return ProtocolConfigStore()
