"""
适配器基类和接口定义
所有第三方 API 适配器都需要继承此基类
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Tuple
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
    
    @property
    @abstractmethod
    def platform_name(self) -> str:
        """平台名称（如 'JM', 'PK'）"""
        pass
    
    @property
    @abstractmethod
    def platform_prefix(self) -> str:
        """平台ID前缀（如 'JM', 'PK'）"""
        pass
    
    @abstractmethod
    def get_album_by_id(self, album_id: str) -> Dict[str, Any]:
        """根据 ID 获取专辑信息
        
        Args:
            album_id: 漫画专辑 ID
            
        Returns:
            元数据 JSON 格式，必须包含 albums 字段
        """
        pass
    
    @abstractmethod
    def search_albums(self, keyword: str, page: int = 1, max_pages: int = 1, fast_mode: bool = False) -> Dict[str, Any]:
        """搜索漫画专辑
        
        Args:
            keyword: 搜索关键词
            page: 起始页码
            max_pages: 最大搜索页数
            fast_mode: 快速模式，不获取详情，速度更快
            
        Returns:
            {
                'page': 当前页码,
                'has_next': 是否有下一页,
                'total_pages': 总页数（如果知道）,
                'albums': 漫画专辑列表
            }
        """
        pass
    
    @abstractmethod
    def get_favorites(self) -> Dict[str, Any]:
        """获取收藏夹中的所有漫画
        
        Returns:
            元数据 JSON 格式，必须包含 albums 字段
        """
        pass
    
    @abstractmethod
    def download_album(
        self, 
        album_id: str, 
        download_dir: str, 
        show_progress: bool = False,
        **kwargs
    ) -> Tuple[Dict[str, Any], bool]:
        """下载漫画专辑
        
        Args:
            album_id: 漫画专辑 ID
            download_dir: 下载目录
            show_progress: 是否显示进度
            **kwargs: 其他平台特定参数
            
        Returns:
            (下载详情字典, 是否成功)
        """
        pass
    
    @abstractmethod
    def download_cover(
        self,
        album_id: str,
        save_path: str,
        show_progress: bool = False
    ) -> Tuple[Dict[str, Any], bool]:
        """下载漫画封面
        
        Args:
            album_id: 漫画专辑 ID
            save_path: 保存路径
            show_progress: 是否显示进度
            
        Returns:
            (下载详情字典, 是否成功)
        """
        pass
    
    def get_preview_image_urls(self, album_id: str, preview_pages: List[int]) -> List[str]:
        """获取预览图片 URL 列表
        
        Args:
            album_id: 漫画专辑 ID
            preview_pages: 需要获取的页码列表
            
        Returns:
            预览图片 URL 列表
        """
        return []
    
    def get_comic_dir(self, album_id: str, author: str = None, title: str = None, base_dir: str = None) -> str:
        """获取漫画目录路径
        
        Args:
            album_id: 漫画专辑 ID
            author: 作者名（可选）
            title: 标题名（可选）
            base_dir: 基础目录（可选）
            
        Returns:
            漫画目录路径
        """
        if base_dir:
            return os.path.join(base_dir, album_id)
        return album_id
    
    def get_cover_url(self, album_id: str) -> Optional[str]:
        """获取封面 URL
        
        Args:
            album_id: 漫画专辑 ID
            
        Returns:
            封面 URL 或 None
        """
        return None
    
    def get_image_url(self, album_id: str, page: int) -> Optional[str]:
        """获取单张图片 URL
        
        Args:
            album_id: 漫画专辑 ID
            page: 页码
            
        Returns:
            图片 URL 或 None
        """
        return None
    
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
    
    def get_user_lists(self) -> Dict[str, Any]:
        """获取用户的清单列表
        
        Returns:
            包含清单列表的字典
        """
        return {"lists": []}
    
    def get_list_detail(self, list_id: str) -> Dict[str, Any]:
        """获取清单的详细内容
        
        Args:
            list_id: 清单ID
            
        Returns:
            包含清单详情和内容的字典
        """
        return {"list_id": list_id, "list_name": "", "works": []}
