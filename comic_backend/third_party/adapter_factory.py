"""
适配器工厂和配置管理
支持多个第三方 API 的动态加载和切换
"""
from typing import Dict, Any, Optional, Type
from .base_adapter import BaseAdapter
from .jmcomic_adapter import JMComicAdapter
from .picacomic_adapter import PicacomicAdapter
from .javdb_adapter import JavdbAdapter
from core.constants import JM_PICTURES_DIR, PK_PICTURES_DIR, normalize_to_data_dir


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
        import os
        default_path = os.path.abspath(os.path.join(
            os.path.dirname(__file__),
            '..',
            'third_party_config.json'
        ))
        self.config_path = config_path or default_path
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
                if self._normalize_storage_config_paths():
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
        return {
            "default_adapter": "jmcomic",
            "adapters": {
                "jmcomic": {
                    "enabled": True,
                    "config_path": "JMComic-Crawler-Python/config.json",
                    "username": "",
                    "password": "",
                    "download_dir": JM_PICTURES_DIR,
                    "output_json": "comics_database.json",
                    "progress_file": "download_progress.json",
                    "favorite_list_file": "favorite_comics.txt",
                    "consecutive_hit_threshold": 10,
                    "collection_name": "我的最爱"
                },
                "picacomic": {
                    "enabled": True,
                    "account": "",
                    "password": "",
                    "base_dir": PK_PICTURES_DIR
                },
                "javdb": {
                    "enabled": True,
                    "domain_index": 0
                }
            }
        }

    def _normalize_storage_config_paths(self) -> bool:
        changed = False
        adapters = self._config.get("adapters", {})

        jm_config = adapters.get("jmcomic")
        if isinstance(jm_config, dict):
            normalized_download_dir = normalize_to_data_dir(
                jm_config.get("download_dir"),
                "pictures/JM"
            )
            if jm_config.get("download_dir") != normalized_download_dir:
                jm_config["download_dir"] = normalized_download_dir
                changed = True

        pk_config = adapters.get("picacomic")
        if isinstance(pk_config, dict):
            normalized_base_dir = normalize_to_data_dir(
                pk_config.get("base_dir"),
                "pictures/PK"
            )
            if pk_config.get("base_dir") != normalized_base_dir:
                pk_config["base_dir"] = normalized_base_dir
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
        if adapter_name == "jmcomic":
            normalized_config["download_dir"] = normalize_to_data_dir(
                normalized_config.get("download_dir"),
                "pictures/JM"
            )
        elif adapter_name == "picacomic":
            normalized_config["base_dir"] = normalize_to_data_dir(
                normalized_config.get("base_dir"),
                "pictures/PK"
            )

        self._config['adapters'][adapter_name] = normalized_config
        self._save_config()
    
    def get_default_adapter(self) -> str:
        """获取默认适配器名称
        
        Returns:
            适配器名称
        """
        return self._config.get('default_adapter', 'jmcomic')
    
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
