from __future__ import annotations

import importlib
import importlib.util
import os
from typing import Any, Dict, Optional

from .base import PluginManifest, ProtocolProvider
from .registry import PluginRegistry, get_plugin_registry
from .runtime_config import ProtocolConfigStore


class ProviderManager:
    def __init__(self, registry: Optional[PluginRegistry] = None):
        self.registry = registry or get_plugin_registry()
        self._providers: Dict[str, ProtocolProvider] = {}
        self._config_store = ProtocolConfigStore()

    def _load_provider_class(self, manifest: PluginManifest):
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

    def reset_all_providers(self) -> None:
        self._providers.clear()

    def _get_runtime_config(self, manifest: PluginManifest) -> Dict[str, Any]:
        config_key = str(manifest.config_key or "").strip()
        if not config_key:
            return {}
        return self._config_store.get_plugin_config(config_key, reload=True)

    def execute(self, plugin_id: str, capability: str, params: Optional[Dict[str, Any]] = None, context: Optional[Dict[str, Any]] = None):
        manifest = self.registry.get_manifest(plugin_id)
        provider = self.get_provider(plugin_id)
        config = self._get_runtime_config(manifest)
        return provider.execute(
            str(capability or "").strip(),
            dict(params or {}),
            dict(context or {}),
            config,
        )

    def get_client(self, plugin_id: str, *args, **kwargs):
        manifest = self.registry.get_manifest(plugin_id)
        provider = self.get_provider(plugin_id)
        config = self._get_runtime_config(manifest)
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
        return provider.get_query_status(config)


_provider_manager_singleton: Optional[ProviderManager] = None


def get_provider_manager() -> ProviderManager:
    global _provider_manager_singleton
    if _provider_manager_singleton is None:
        _provider_manager_singleton = ProviderManager()
    return _provider_manager_singleton
