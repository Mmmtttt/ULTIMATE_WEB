"""
平台服务 - 统一管理多平台操作
提供统一的接口来处理不同平台的漫画操作
"""
from typing import Dict, List, Any, Optional, Tuple
from core.platform import Platform
from .base_adapter import BaseAdapter
from infrastructure.logger import error_logger
from protocol.compatibility import get_plugin_id_for_platform
from protocol.gateway import get_protocol_gateway


class PlatformService:
    """平台服务类
    
    提供统一的接口来处理不同平台的漫画操作，
    消除代码中对具体平台的硬编码判断
    """
    
    _instance = None
    _adapters: Dict[Platform, BaseAdapter] = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not hasattr(self, '_initialized'):
            self._gateway = get_protocol_gateway()
            self._initialized = True
    
    def get_adapter(self, platform: Platform) -> BaseAdapter:
        """获取指定平台的适配器
        
        Args:
            platform: 平台枚举
            
        Returns:
            平台适配器实例
        """
        plugin_id = get_plugin_id_for_platform(platform)
        if not plugin_id:
            raise ValueError(f"未知平台: {platform}")
        return self._gateway.get_legacy_client(plugin_id)
    
    def _get_adapter_name(self, platform: Platform) -> str:
        """根据平台获取适配器名称"""
        adapter_mapping = {
            Platform.JM: 'jmcomic',
            Platform.PK: 'picacomic',
            Platform.JAVDB: 'javdb'
        }
        return adapter_mapping.get(platform, 'jmcomic')
    
    def download_album(
        self,
        platform: Platform,
        album_id: str,
        download_dir: str,
        show_progress: bool = False,
        **kwargs
    ) -> Tuple[Dict[str, Any], bool]:
        """下载漫画专辑
        
        Args:
            platform: 平台
            album_id: 漫画专辑ID
            download_dir: 下载目录
            show_progress: 是否显示进度
            **kwargs: 其他平台特定参数
            
        Returns:
            (下载详情字典, 是否成功)
        """
        try:
            plugin_id = get_plugin_id_for_platform(platform)
            result = self._gateway.execute_plugin(
                plugin_id,
                "asset.bundle.fetch",
                params={
                    "album_id": album_id,
                    "download_dir": download_dir,
                    "show_progress": show_progress,
                    "extra": kwargs,
                },
            )
            return dict(result.get("detail") or {}), bool(result.get("success"))
        except Exception as e:
            error_logger.error(f"下载漫画失败: {platform}, {album_id}, {e}")
            return {}, False
    
    def download_cover(
        self,
        platform: Platform,
        album_id: str,
        save_path: str,
        show_progress: bool = False
    ) -> Tuple[Dict[str, Any], bool]:
        """下载漫画封面
        
        Args:
            platform: 平台
            album_id: 漫画专辑ID
            save_path: 保存路径
            show_progress: 是否显示进度
            
        Returns:
            (下载详情字典, 是否成功)
        """
        try:
            plugin_id = get_plugin_id_for_platform(platform)
            result = self._gateway.execute_plugin(
                plugin_id,
                "asset.cover.fetch",
                params={
                    "album_id": album_id,
                    "save_path": save_path,
                    "show_progress": show_progress,
                },
            )
            return dict(result.get("detail") or {}), bool(result.get("success"))
        except Exception as e:
            error_logger.error(f"下载封面失败: {platform}, {album_id}, {e}")
            return {}, False
    
    def get_comic_dir(
        self,
        platform: Platform,
        album_id: str,
        author: str = None,
        title: str = None,
        base_dir: str = None
    ) -> str:
        """获取漫画目录路径
        
        Args:
            platform: 平台
            album_id: 漫画专辑ID
            author: 作者名
            title: 标题名
            base_dir: 基础目录
            
        Returns:
            漫画目录路径
        """
        plugin_id = get_plugin_id_for_platform(platform)
        return self._gateway.execute_plugin(
            plugin_id,
            "storage.comic_dir.resolve",
            params={
                "album_id": album_id,
                "author": author,
                "title": title,
                "base_dir": base_dir,
            },
        )
    
    def get_cover_url(self, platform: Platform, album_id: str) -> Optional[str]:
        """获取封面URL
        
        Args:
            platform: 平台
            album_id: 漫画专辑ID
            
        Returns:
            封面URL或None
        """
        adapter = self.get_adapter(platform)
        return adapter.get_cover_url(album_id)
    
    def get_image_url(self, platform: Platform, album_id: str, page: int) -> Optional[str]:
        """获取单张图片URL
        
        Args:
            platform: 平台
            album_id: 漫画专辑ID
            page: 页码
            
        Returns:
            图片URL或None
        """
        adapter = self.get_adapter(platform)
        return adapter.get_image_url(album_id, page)
    
    def get_preview_image_urls(
        self,
        platform: Platform,
        album_id: str,
        preview_pages: List[int]
    ) -> List[str]:
        """获取预览图片URL列表
        
        Args:
            platform: 平台
            album_id: 漫画专辑ID
            preview_pages: 预览页码列表
            
        Returns:
            预览图片URL列表
        """
        plugin_id = get_plugin_id_for_platform(platform)
        return self._gateway.execute_plugin(
            plugin_id,
            "asset.preview.resolve",
            params={
                "album_id": album_id,
                "preview_pages": preview_pages,
            },
        )
    
    def get_album_by_id(self, platform: Platform, album_id: str) -> Dict[str, Any]:
        """根据ID获取专辑信息
        
        Args:
            platform: 平台
            album_id: 漫画专辑ID
            
        Returns:
            元数据JSON格式
        """
        plugin_id = get_plugin_id_for_platform(platform)
        return self._gateway.execute_plugin(
            plugin_id,
            "catalog.detail",
            params={"album_id": album_id},
        )
    
    def search_albums(
        self,
        platform: Platform,
        keyword: str,
        max_pages: int = 1,
        fast_mode: bool = False
    ) -> Dict[str, Any]:
        """搜索漫画专辑
        
        Args:
            platform: 平台
            keyword: 搜索关键词
            max_pages: 最大搜索页数
            fast_mode: 快速模式，不获取详情（默认False以获取完整标签）
            
        Returns:
            元数据JSON格式
        """
        plugin_id = get_plugin_id_for_platform(platform)
        return self._gateway.execute_plugin(
            plugin_id,
            "catalog.search",
            params={
                "keyword": keyword,
                "page": 1,
                "max_pages": max_pages,
                "fast_mode": fast_mode,
            },
        )
    
    def get_favorites(self, platform: Platform) -> Dict[str, Any]:
        """获取收藏夹中的所有漫画
        
        Args:
            platform: 平台
            
        Returns:
            元数据JSON格式
        """
        plugin_id = get_plugin_id_for_platform(platform)
        return self._gateway.execute_plugin(
            plugin_id,
            "collection.favorites",
            params={},
        )

    def get_favorites_basic(self, platform: Platform) -> Dict[str, Any]:
        """获取收藏夹基础信息（轻量模式）"""
        plugin_id = get_plugin_id_for_platform(platform)
        capability = "collection.favorites_basic" if platform != Platform.JAVDB else "collection.favorites"
        return self._gateway.execute_plugin(plugin_id, capability, params={})
    
    def get_user_lists(self, platform: Platform) -> Dict[str, Any]:
        """获取用户的清单列表
        
        Args:
            platform: 平台
            
        Returns:
            包含清单列表的字典
        """
        plugin_id = get_plugin_id_for_platform(platform)
        return self._gateway.execute_plugin(
            plugin_id,
            "collection.list",
            params={},
        )
    
    def get_list_detail(self, platform: Platform, list_id: str) -> Dict[str, Any]:
        """获取清单的详细内容
        
        Args:
            platform: 平台
            list_id: 清单ID
            
        Returns:
            包含清单详情和内容的字典
        """
        plugin_id = get_plugin_id_for_platform(platform)
        return self._gateway.execute_plugin(
            plugin_id,
            "collection.detail",
            params={"list_id": list_id},
        )


def get_platform_service() -> PlatformService:
    """获取平台服务单例
    
    Returns:
        PlatformService实例
    """
    return PlatformService()
