"""
平台服务 - 统一管理所有平台操作
通过适配器工厂和适配器接口，提供统一的平台操作入口
"""
from typing import Dict, List, Any, Optional, Tuple, TYPE_CHECKING
from core.platform import Platform, get_platform_from_id, get_original_id, get_supported_platforms
from infrastructure.logger import app_logger, error_logger

if TYPE_CHECKING:
    from third_party.base_adapter import BaseAdapter
else:
    BaseAdapter = Any


class PlatformService:
    """平台服务 - 统一管理所有平台操作
    
    该服务封装了所有平台特定的逻辑，外部调用者只需要调用这个服务
    不需要关心具体是哪个平台，也不需要写if-elif判断
    """
    
    _instance = None
    _lock = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        self._config_manager = self._get_adapter_config_cls()()
        self._adapters: Dict[str, BaseAdapter] = {}
        self._platform_to_adapter: Dict[Platform, str] = {
            Platform.JM: 'jmcomic',
            Platform.PK: 'picacomic'
        }
        self._adapter_to_platform: Dict[str, Platform] = {
            'jmcomic': Platform.JM,
            'picacomic': Platform.PK
        }
        
        self._initialized = True
        app_logger.info("平台服务初始化完成")
    
    @staticmethod
    def _get_adapter_factory_cls():
        from third_party.adapter_factory import AdapterFactory
        return AdapterFactory

    @staticmethod
    def _get_adapter_config_cls():
        from third_party.adapter_factory import AdapterConfig
        return AdapterConfig

    def register_platform(self, platform: Platform, adapter_name: str):
        """注册新平台
        
        Args:
            platform: 平台枚举
            adapter_name: 适配器名称
        """
        self._platform_to_adapter[platform] = adapter_name
        self._adapter_to_platform[adapter_name] = platform
        app_logger.info(f"注册新平台: {platform} -> {adapter_name}")
    
    def get_adapter(self, platform: Platform) -> BaseAdapter:
        """获取平台适配器
        
        Args:
            platform: 平台枚举
            
        Returns:
            平台适配器实例
        """
        adapter_name = self._platform_to_adapter.get(platform)
        if not adapter_name:
            raise ValueError(f"未知平台: {platform}")
        
        if adapter_name not in self._adapters:
            config = self._config_manager.get_adapter_config(adapter_name)
            self._adapters[adapter_name] = self._get_adapter_factory_cls().get_adapter(adapter_name, config)
        
        return self._adapters[adapter_name]
    
    def get_adapter_by_comic_id(self, comic_id: str) -> BaseAdapter:
        """通过漫画ID获取适配器
        
        Args:
            comic_id: 漫画ID（带平台前缀）
            
        Returns:
            平台适配器实例
        """
        platform = get_platform_from_id(comic_id)
        if not platform:
            raise ValueError(f"无法从漫画ID识别平台: {comic_id}")
        
        return self.get_adapter(platform)
    
    def get_platform_prefix(self, platform: Platform) -> str:
        """获取平台ID前缀
        
        Args:
            platform: 平台枚举
            
        Returns:
            平台前缀
        """
        adapter = self.get_adapter(platform)
        return adapter.platform_prefix
    
    def get_comic_dir(
        self, 
        comic_id: str, 
        author: str = None, 
        title: str = None, 
        base_dir: str = None
    ) -> str:
        """获取漫画目录路径
        
        Args:
            comic_id: 漫画ID
            author: 作者名（可选）
            title: 标题名（可选）
            base_dir: 基础目录（可选）
            
        Returns:
            漫画目录路径
        """
        adapter = self.get_adapter_by_comic_id(comic_id)
        original_id = get_original_id(comic_id)
        return adapter.get_comic_dir(original_id, author, title, base_dir)
    
    def get_cover_url(self, comic_id: str) -> Optional[str]:
        """获取封面URL
        
        Args:
            comic_id: 漫画ID
            
        Returns:
            封面URL或None
        """
        adapter = self.get_adapter_by_comic_id(comic_id)
        original_id = get_original_id(comic_id)
        return adapter.get_cover_url(original_id)
    
    def get_image_url(self, comic_id: str, page: int) -> Optional[str]:
        """获取单张图片URL
        
        Args:
            comic_id: 漫画ID
            page: 页码
            
        Returns:
            图片URL或None
        """
        adapter = self.get_adapter_by_comic_id(comic_id)
        original_id = get_original_id(comic_id)
        return adapter.get_image_url(original_id, page)
    
    def get_preview_image_urls(self, comic_id: str, preview_pages: List[int]) -> List[str]:
        """获取预览图片URL列表
        
        Args:
            comic_id: 漫画ID
            preview_pages: 需要获取的页码列表
            
        Returns:
            预览图片URL列表
        """
        adapter = self.get_adapter_by_comic_id(comic_id)
        original_id = get_original_id(comic_id)
        return adapter.get_preview_image_urls(original_id, preview_pages)
    
    def download_album(
        self,
        comic_id: str,
        download_dir: str,
        show_progress: bool = False,
        **kwargs
    ) -> Tuple[Dict[str, Any], bool]:
        """下载漫画专辑
        
        Args:
            comic_id: 漫画ID
            download_dir: 下载目录
            show_progress: 是否显示进度
            **kwargs: 其他平台特定参数
            
        Returns:
            (下载详情字典, 是否成功)
        """
        adapter = self.get_adapter_by_comic_id(comic_id)
        original_id = get_original_id(comic_id)
        return adapter.download_album(original_id, download_dir, show_progress, **kwargs)
    
    def download_cover(
        self,
        comic_id: str,
        save_path: str,
        show_progress: bool = False
    ) -> Tuple[Dict[str, Any], bool]:
        """下载漫画封面
        
        Args:
            comic_id: 漫画ID
            save_path: 保存路径
            show_progress: 是否显示进度
            
        Returns:
            (下载详情字典, 是否成功)
        """
        adapter = self.get_adapter_by_comic_id(comic_id)
        original_id = get_original_id(comic_id)
        return adapter.download_cover(original_id, save_path, show_progress)
    
    def get_album_by_id(self, comic_id: str) -> Dict[str, Any]:
        """根据ID获取专辑信息
        
        Args:
            comic_id: 漫画ID
            
        Returns:
            元数据JSON格式
        """
        adapter = self.get_adapter_by_comic_id(comic_id)
        original_id = get_original_id(comic_id)
        return adapter.get_album_by_id(original_id)
    
    def search_albums(
        self,
        platform: Platform,
        keyword: str,
        max_pages: int = 1
    ) -> Dict[str, Any]:
        """搜索漫画专辑
        
        Args:
            platform: 平台枚举
            keyword: 搜索关键词
            max_pages: 最大搜索页数
            
        Returns:
            元数据JSON格式
        """
        adapter = self.get_adapter(platform)
        return adapter.search_albums(keyword, max_pages)
    
    def get_favorites(self, platform: Platform) -> Dict[str, Any]:
        """获取收藏夹中的所有漫画
        
        Args:
            platform: 平台枚举
            
        Returns:
            元数据JSON格式
        """
        adapter = self.get_adapter(platform)
        return adapter.get_favorites()
    
    def list_available_platforms(self) -> List[Platform]:
        """列出所有可用的平台
        
        Returns:
            平台枚举列表
        """
        return list(self._platform_to_adapter.keys())


platform_service = PlatformService()
