"""
外部 API 统一接口
使用适配器工厂模式支持多个第三方 API
"""
from typing import Dict, Any, Optional
from .adapter_factory import AdapterFactory, AdapterConfig


_config_manager = None


def get_config_manager() -> AdapterConfig:
    """获取配置管理器实例（单例）
    
    Returns:
        配置管理器实例
    """
    global _config_manager
    if _config_manager is None:
        _config_manager = AdapterConfig()
    return _config_manager

def reset_config_manager():
    """Reset cached AdapterConfig instance."""
    global _config_manager
    _config_manager = None


def get_adapter(adapter_name: Optional[str] = None):
    """获取 API 适配器实例
    
    Args:
        adapter_name: 适配器名称，None 表示使用默认适配器
        
    Returns:
        适配器实例
    """
    if adapter_name is None:
        config_manager = get_config_manager()
        adapter_name = config_manager.get_default_adapter()
    
    config_manager = get_config_manager()
    adapter_config = config_manager.get_adapter_config(adapter_name)
    
    return AdapterFactory.get_adapter(adapter_name, adapter_config)


def get_album_by_id(album_id: str, adapter_name: Optional[str] = None) -> Dict[str, Any]:
    """根据 ID 获取专辑信息
    
    Args:
        album_id: 漫画专辑 ID
        adapter_name: 适配器名称，None 表示使用默认适配器
        
    Returns:
        元数据 JSON 格式
    """
    adapter = get_adapter(adapter_name)
    return adapter.get_album_by_id(album_id)


def search_albums(keyword: str, max_pages: int = 1, adapter_name: Optional[str] = None,
                  fast_mode: bool = False) -> Dict[str, Any]:
    """搜索漫画专辑
    
    Args:
        keyword: 搜索关键词
        max_pages: 最大搜索页数
        adapter_name: 适配器名称，None 表示使用默认适配器
        fast_mode: 快速模式，不获取详情，速度更快
        
    Returns:
        元数据 JSON 格式
    """
    adapter = get_adapter(adapter_name)
    return adapter.search_albums(keyword, max_pages, fast_mode)


def get_favorites(adapter_name: Optional[str] = None) -> Dict[str, Any]:
    """获取收藏夹中的所有漫画
    
    Args:
        adapter_name: 适配器名称，None 表示使用默认适配器
        
    Returns:
        元数据 JSON 格式
    """
    adapter = get_adapter(adapter_name)
    return adapter.get_favorites()


def list_available_adapters() -> list:
    """列出所有可用的适配器
    
    Returns:
        适配器名称列表
    """
    return AdapterFactory.list_adapters()


def get_adapter_config(adapter_name: str) -> Dict[str, Any]:
    """获取指定适配器的配置
    
    Args:
        adapter_name: 适配器名称
        
    Returns:
        适配器配置字典
    """
    config_manager = get_config_manager()
    return config_manager.get_adapter_config(adapter_name)


def set_adapter_config(adapter_name: str, config: Dict[str, Any]):
    """设置适配器配置
    
    Args:
        adapter_name: 适配器名称
        config: 配置字典
    """
    config_manager = get_config_manager()
    config_manager.set_adapter_config(adapter_name, config)


def get_default_adapter() -> str:
    """获取默认适配器名称
    
    Returns:
        适配器名称
    """
    config_manager = get_config_manager()
    return config_manager.get_default_adapter()


def set_default_adapter(adapter_name: str):
    """设置默认适配器
    
    Args:
        adapter_name: 适配器名称
    """
    config_manager = get_config_manager()
    config_manager.set_default_adapter(adapter_name)


def reset_adapter(adapter_name: str):
    """重置适配器实例（用于配置更新后重新初始化）
    
    Args:
        adapter_name: 适配器名称
    """
    AdapterFactory.reset_instance(adapter_name)
    reset_config_manager()
