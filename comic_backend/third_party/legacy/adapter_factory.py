"""
适配器工厂和配置管理
支持多个第三方 API 的动态加载和切换
"""
import os
from typing import Dict, Any, Optional, Type
from .base_adapter import BaseAdapter
from .jmcomic_adapter import JMComicAdapter
from .picacomic_adapter import PicacomicAdapter
from .javdb_adapter import JavdbAdapter
from core.constants import (
    DATA_DIR,
    THIRD_PARTY_CONFIG_PATH,
    normalize_to_data_dir,
)


class AdapterFactory:
    """适配器工厂
    
    负责创建和管理不同的 API 适配器
    """
    
    _adapters: Dict[str, Type[BaseAdapter]] = {
        'jmcomic': JMComicAdapter,
        'picacomic': PicacomicAdapter,
        'javdb': JavdbAdapter,
    }
    
    _instances: Dict[str, BaseAdapter] = {}
    
    @classmethod
    def register_adapter(cls, name: str, adapter_class: Type[BaseAdapter]):
        """注册新的适配器
        
        Args:
            name: 适配器名称
            adapter_class: 适配器类
        """
        cls._adapters[name] = adapter_class
    
    @classmethod
    def get_adapter(cls, name: str, config: Optional[Dict[str, Any]] = None) -> BaseAdapter:
        """获取适配器实例（单例模式）
        
        Args:
            name: 适配器名称
            config: 配置字典
            
        Returns:
            适配器实例
            
        Raises:
            ValueError: 适配器不存在
        """
        if name not in cls._adapters:
            raise ValueError(f"未知的适配器: {name}，可用适配器: {list(cls._adapters.keys())}")
        
        adapter_class = cls._adapters[name]
        if name not in cls._instances:
            cls._instances[name] = adapter_class(config)
        elif config is not None and getattr(cls._instances[name], 'config', {}) != config:
            # 配置变更时重建实例，确保新账号/密码等配置即时生效
            cls._instances[name] = adapter_class(config)
        
        return cls._instances[name]
    
    @classmethod
    def list_adapters(cls) -> list:
        """列出所有可用的适配器
        
        Returns:
            适配器名称列表
        """
        return list(cls._adapters.keys())
    
    @classmethod
    def reset_instance(cls, name: str):
        """重置适配器实例
        
        Args:
            name: 适配器名称
        """
        if name in cls._instances:
            del cls._instances[name]


class AdapterConfig:
    """适配器配置管理
    
    管理不同 API 的配置信息
    """
    
    def __init__(self, config_path: Optional[str] = None):
        """初始化配置管理器
        
        Args:
            config_path: 配置文件路径
        """
        self.config_path = config_path or THIRD_PARTY_CONFIG_PATH
        self._config: Dict[str, Any] = {}
        self._load_config()
    
    def _load_config(self):
        """加载配置文件"""
        import json
        import os
        
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    self._config = json.load(f)
                changed = self._merge_protocol_defaults()
                if self._normalize_storage_config_paths():
                    changed = True
                if changed:
                    self._save_config()
            except Exception as e:
                print(f"加载配置文件失败: {e}")
                self._config = {}
        else:
            self._config = self._get_default_config()
            self._save_config()

    def reload_config(self):
        """重新加载配置文件（用于运行时热更新配置）"""
        self._load_config()
    
    def _save_config(self):
        """保存配置文件"""
        import json
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self._config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存配置文件失败: {e}")
    
    def _get_default_config(self) -> Dict[str, Any]:
        """获取默认配置"""
        self._config = {
            "default_adapter": "",
            "adapters": {},
        }
        self._merge_protocol_defaults()
        return dict(self._config)

    @staticmethod
    def _get_protocol_gateway():
        from protocol.gateway import get_protocol_gateway

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
    def _resolve_binding_field_name(binding: Dict[str, Any]) -> str:
        return str(
            binding.get("config_field")
            or binding.get("field")
            or ""
        ).strip()

    @classmethod
    def _resolve_binding_default_abs_path(cls, manifest, binding: Dict[str, Any]) -> str:
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
    def _normalize_bound_path(cls, path_value: str, manifest, binding: Dict[str, Any]) -> str:
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
    def _build_manifest_default_config(cls, manifest) -> Dict[str, Any]:
        config_key = str(getattr(manifest, "config_key", "") or "").strip()
        if not config_key:
            return {}

        defaults: Dict[str, Any] = {}
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
        for manifest in cls._list_protocol_manifests():
            config_key = str(getattr(manifest, "config_key", "") or "").strip()
            media_types = {
                str(item or "").strip().lower()
                for item in (getattr(manifest, "media_types", []) or [])
                if str(item or "").strip()
            }
            if config_key and "comic" in media_types:
                return config_key

        manifests = cls._list_protocol_manifests()
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
    
    def get_adapter_config(self, adapter_name: str) -> Dict[str, Any]:
        """获取指定适配器的配置
        
        Args:
            adapter_name: 适配器名称
            
        Returns:
            适配器配置字典
        """
        return self._config.get('adapters', {}).get(adapter_name, {})
    
    def set_adapter_config(self, adapter_name: str, config: Dict[str, Any]):
        """设置适配器配置
        
        Args:
            adapter_name: 适配器名称
            config: 配置字典
        """
        if 'adapters' not in self._config:
            self._config['adapters'] = {}
        
        existing_config = self._config['adapters'].get(adapter_name, {})
        normalized_config = dict(existing_config or {})
        normalized_config.update(dict(config or {}))

        manifest = None
        for candidate in self._list_protocol_manifests():
            if str(getattr(candidate, "config_key", "") or "").strip() == str(adapter_name or "").strip():
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

        self._config['adapters'][adapter_name] = normalized_config
        self._save_config()
    
    def get_default_adapter(self) -> str:
        """获取默认适配器名称
        
        Returns:
            适配器名称
        """
        return str(self._config.get('default_adapter') or '').strip() or self._get_default_adapter_key()
    
    def set_default_adapter(self, adapter_name: str):
        """设置默认适配器
        
        Args:
            adapter_name: 适配器名称
        """
        self._config['default_adapter'] = adapter_name
        self._save_config()
    
    def get_enabled_adapters(self) -> list:
        """获取所有启用的适配器
        
        Returns:
            启用的适配器名称列表
        """
        enabled = []
        for name, config in self._config.get('adapters', {}).items():
            if config.get('enabled', True):
                enabled.append(name)
        return enabled
