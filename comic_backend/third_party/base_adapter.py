"""
适配器基类和接口定义
所有第三方 API 适配器都需要继承此基类
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
import time


class BaseAdapter(ABC):
    """第三方 API 适配器基类
    
    所有适配器必须实现以下方法，以提供统一的接口
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """初始化适配器
        
        Args:
            config: 配置字典，不同 API 可能需要不同的配置
        """
        self.config = config or {}
        self._client = None
    
    @abstractmethod
    def get_album_by_id(self, album_id: str) -> Dict[str, Any]:
        """根据 ID 获取专辑信息
        
        Args:
            album_id: 漫画专辑 ID
            
        Returns:
            元数据 JSON 格式，必须包含 albums 字段
            {
                "albums": [
                    {
                        "album_id": 123456,
                        "title": "标题",
                        "author": "作者",
                        "pages": 100,
                        "cover_url": "https://...",
                        "album_url": "https://...",
                        "tags": ["标签1", "标签2"],
                        "upload_date": "2024-01-01",
                        "update_date": "2024-01-15"
                    }
                ],
                "collection_name": "收藏集名称",
                "user": "用户名",
                "total_favorites": 10,
                "last_updated": "2024-01-01"
            }
        """
        pass
    
    @abstractmethod
    def search_albums(self, keyword: str, max_pages: int = 1) -> Dict[str, Any]:
        """搜索漫画专辑
        
        Args:
            keyword: 搜索关键词
            max_pages: 最大搜索页数
            
        Returns:
            元数据 JSON 格式，必须包含 albums 字段
        """
        pass
    
    @abstractmethod
    def get_favorites(self) -> Dict[str, Any]:
        """获取收藏夹中的所有漫画
        
        Returns:
            元数据 JSON 格式，必须包含 albums 字段
        """
        pass
    
    def normalize_to_meta_format(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """将 API 返回的数据标准化为元数据格式
        
        子类可以重写此方法以处理特定的数据格式
        
        Args:
            data: API 返回的原始数据
            
        Returns:
            标准化的元数据格式
        """
        if 'albums' in data:
            return data
        
        return {
            "albums": data.get('results', []),
            "collection_name": data.get('collection_name', "导入的漫画"),
            "user": data.get('user', ""),
            "total_favorites": len(data.get('results', [])),
            "last_updated": time.strftime("%Y-%m-%d")
        }
    
    def get_config(self, key: str, default: Any = None) -> Any:
        """获取配置项
        
        Args:
            key: 配置键
            default: 默认值
            
        Returns:
            配置值
        """
        return self.config.get(key, default)
    
    def set_config(self, key: str, value: Any):
        """设置配置项
        
        Args:
            key: 配置键
            value: 配置值
        """
        self.config[key] = value
