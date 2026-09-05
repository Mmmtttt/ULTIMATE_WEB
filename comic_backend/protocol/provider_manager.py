from __future__ import annotations

import importlib
import importlib.util
import os
import platform
import sys
from typing import Any, Dict, Optional

from .base import PluginManifest, ProtocolProvider
from .credential_guard import get_manifest_credential_status
from .registry import PluginRegistry, get_plugin_registry
from .runtime_config import ProtocolConfigStore


class ProviderManager:
    def __init__(self, registry: Optional[PluginRegistry] = None):
        self.registry = registry or get_plugin_registry()
        self._providers: Dict[str, ProtocolProvider] = {}
        self._config_store = ProtocolConfigStore()
        self._plugin_runtime_paths: Dict[str, list[str]] = {}

    @staticmethod
    def _runtime_tokens() -> Dict[str, str]:
        machine = str(platform.machine() or "").strip().lower() or "unknown"
        system_name = str(platform.system() or "").strip().lower() or sys.platform.lower()
        python_tag = f"py{sys.version_info.major}{sys.version_info.minor}"
        return {
            "platform": system_name,
            "machine": machine,
            "platform_tag": f"{system_name}-{machine}",
            "python_tag": python_tag,
            "python_version": f"{sys.version_info.major}.{sys.version_info.minor}",
        }

    def _resolve_runtime_paths(self, manifest: PluginManifest) -> list[str]:
        manifest_dir = os.path.abspath(os.path.dirname(manifest.path))
        runtime = dict(getattr(manifest, "runtime", {}) or {})
        python_paths = runtime.get("python_paths") or []
        vendor_templates = runtime.get("vendor_path_templates") or []
        if not isinstance(python_paths, list):
            python_paths = []
        if not isinstance(vendor_templates, list):
            vendor_templates = []

        resolved: list[str] = [manifest_dir]
        tokens = self._runtime_tokens()

        def _append_relative_path(raw_value: Any) -> None:
            template = str(raw_value or "").strip()
            if not template:
                return
            try:
                template = template.format(**tokens)
            except Exception:
                return
            candidate = os.path.abspath(os.path.join(manifest_dir, template))
            if os.path.isdir(candidate):
                resolved.append(candidate)

        for entry in python_paths:
            _append_relative_path(entry)
        for entry in vendor_templates:
            _append_relative_path(entry)

        deduped: list[str] = []
        seen = set()
        for path in resolved:
            normalized = os.path.abspath(str(path or "").strip())
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            deduped.append(normalized)
        return deduped

    def _ensure_plugin_runtime_paths(self, manifest: PluginManifest) -> list[str]:
        plugin_id = str(manifest.plugin_id or "").strip()
        cached = self._plugin_runtime_paths.get(plugin_id)
        if cached is not None:
            return list(cached)

        resolved = self._resolve_runtime_paths(manifest)
        for path in reversed(resolved):
            if path in sys.path:
                sys.path.remove(path)
            sys.path.insert(0, path)
        self._plugin_runtime_paths[plugin_id] = list(resolved)
        return list(resolved)

    def _drop_plugin_runtime_paths(self, plugin_id: str) -> None:
        cached = self._plugin_runtime_paths.pop(str(plugin_id or "").strip(), None)
        for path in reversed(list(cached or [])):
            while path in sys.path:
                sys.path.remove(path)

    def _load_provider_class(self, manifest: PluginManifest):
        self._ensure_plugin_runtime_paths(manifest)
        entrypoint = manifest.entrypoint
        module_ref, _, class_name = entrypoint.partition(":")
        if not module_ref or not class_name:
            raise ValueError(f"invalid entrypoint: {entrypoint}")

        is_file_entrypoint = (
            module_ref.startswith(".")
            or module_ref.endswith(".py")
            or "/" in module_ref
            or "\\" in module_ref
        )

        if is_file_entrypoint:
            module_path = module_ref
            if not os.path.isabs(module_path):
                module_path = os.path.abspath(os.path.join(os.path.dirname(manifest.path), module_path))
            module_name = f"_ultimate_plugin_{manifest.plugin_id.replace('.', '_').replace('-', '_')}"
            spec = importlib.util.spec_from_file_location(module_name, module_path)
            if spec is None or spec.loader is None:
                raise ImportError(f"cannot load provider module from {module_path}")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        else:
            module = importlib.import_module(module_ref)

        provider_cls = getattr(module, class_name, None)
        if provider_cls is None:
            raise ImportError(f"provider class not found: {entrypoint}")
        return provider_cls

    def get_provider(self, plugin_id: str) -> ProtocolProvider:
        plugin_key = str(plugin_id or "").strip()
        provider = self._providers.get(plugin_key)
        if provider is not None:
            return provider

        manifest = self.registry.get_manifest(plugin_key)
        provider_cls = self._load_provider_class(manifest)
        provider = provider_cls(manifest=manifest.raw, manifest_path=manifest.path)
        if not isinstance(provider, ProtocolProvider):
            # Some test/runtime entrypoints may import the same provider base through
            # different module roots, so prefer capability-based validation here.
            required_methods = ("execute", "normalize_config", "serialize_public_config")
            if not all(callable(getattr(provider, method_name, None)) for method_name in required_methods):
                raise TypeError(f"{plugin_key} provider must inherit ProtocolProvider")
        self._providers[plugin_key] = provider
        return provider

    def reset_provider(self, plugin_id: str) -> None:
        plugin_key = str(plugin_id or "").strip()
        if plugin_key:
            self._providers.pop(plugin_key, None)
            self._drop_plugin_runtime_paths(plugin_key)

    def reset_all_providers(self) -> None:
        self._providers.clear()
        for plugin_id in list(self._plugin_runtime_paths.keys()):
            self._drop_plugin_runtime_paths(plugin_id)

    def _get_runtime_config(self, manifest: PluginManifest) -> Dict[str, Any]:
        config_key = str(getattr(manifest, "effective_config_key", "") or manifest.config_key or "").strip()
        if not config_key:
            return {}
        return self._config_store.get_plugin_config(config_key, reload=True)

    @staticmethod
    def _capability_requires_enabled(capability: str) -> bool:
        normalized = str(capability or "").strip()
        if not normalized or normalized == "health.query.status":
            return False
        return normalized.startswith((
            "catalog.",
            "collection.",
            "person.",
            "taxonomy.",
            "asset.",
        ))

    def _ensure_plugin_enabled_for_capability(
        self,
        manifest: PluginManifest,
        config: Dict[str, Any],
        capability: str,
    ) -> None:
        if not self._capability_requires_enabled(capability):
            return
        status = get_manifest_credential_status(manifest, config)
        if not bool(status.get("configured", False)):
            raise RuntimeError(str(status.get("message") or "平台未启用或配置不完整，不能执行查询"))

    def execute(self, plugin_id: str, capability: str, params: Optional[Dict[str, Any]] = None, context: Optional[Dict[str, Any]] = None):
        manifest = self.registry.get_manifest(plugin_id)
        provider = self.get_provider(plugin_id)
        config = self._get_runtime_config(manifest)
        normalized_capability = str(capability or "").strip()
        self._ensure_plugin_enabled_for_capability(manifest, config, normalized_capability)
        return provider.execute(
            normalized_capability,
            dict(params or {}),
            dict(context or {}),
            config,
        )

    def get_client(self, plugin_id: str, *args, **kwargs):
        manifest = self.registry.get_manifest(plugin_id)
        provider = self.get_provider(plugin_id)
        config = self._get_runtime_config(manifest)
        status = get_manifest_credential_status(manifest, config)
        if not bool(status.get("configured", False)):
            raise RuntimeError(str(status.get("message") or "平台未启用或配置不完整，不能创建客户端"))
        return provider.build_client(config, *args, **kwargs)

    def normalize_config(self, plugin_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        provider = self.get_provider(plugin_id)
        return provider.normalize_config(dict(payload or {}))

    def serialize_public_config(self, plugin_id: str, config: Dict[str, Any]) -> Dict[str, Any]:
        provider = self.get_provider(plugin_id)
        return provider.serialize_public_config(dict(config or {}))

    def get_query_status(self, plugin_id: str) -> Dict[str, Any]:
        manifest = self.registry.get_manifest(plugin_id)
        provider = self.get_provider(plugin_id)
        config = self._get_runtime_config(manifest)
        credential_status = get_manifest_credential_status(manifest, config)
        if not bool(credential_status.get("configured", False)):
            return credential_status
        return provider.get_query_status(config)


_provider_manager_singleton: Optional[ProviderManager] = None


def get_provider_manager() -> ProviderManager:
    global _provider_manager_singleton
    if _provider_manager_singleton is None:
        _provider_manager_singleton = ProviderManager()
    return _provider_manager_singleton
