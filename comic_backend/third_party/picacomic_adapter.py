"""
Picacomic API 适配器实现
基于 Picacomic-Crawler 库
"""
import sys
import os
from typing import Dict, List, Any, Optional
from .base_adapter import BaseAdapter


class PicacomicAdapter(BaseAdapter):
    """Picacomic API 适配器
    
    使用 Picacomic-Crawler 库进行漫画搜索和下载
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """初始化 Picacomic 适配器
        
        Args:
            config: 配置字典，包含：
                - account: 邮箱账号
                - password: 密码
                - base_dir: 下载目录
        """
        super().__init__(config)
        self._picacomic_api_module = None
        self._option = None
        self._load_picacomic_api()
    
    def _load_picacomic_api(self):
        """动态加载 Picacomic API 模块"""
        try:
            picacomic_path = os.path.join(
                os.path.dirname(__file__),
                'Picacomic-Crawler'
            )
            
            if picacomic_path not in sys.path:
                sys.path.insert(0, picacomic_path)
            
            # 导入 Picacomic 统一 API 模块
            import picacomic_api as pica_api
            self._picacomic_api_module = pica_api
            
            # 设置配置并创建 option
            account = self.get_config('account')
            password = self.get_config('password')
            base_dir = self.get_config('base_dir', '../../data/pictures/PK')
            
            # 直接创建 option 而不是修改配置
            from picacomic import PicaOption
            self._option = PicaOption()
            self._option.client['account'] = account or ''
            self._option.client['password'] = password or ''
            self._option.dir_rule.base_dir = os.path.abspath(base_dir)
                
        except ImportError as e:
            raise ImportError(f"Picacomic API 模块未找到: {e}")
        except Exception as e:
            raise RuntimeError(f"Picacomic API 初始化失败: {e}")
    
    def get_album_by_id(self, album_id: str) -> Dict[str, Any]:
        """根据 ID 获取专辑信息
        
        Args:
            album_id: 漫画专辑 ID
            
        Returns:
            元数据 JSON 格式
        """
        try:
            detail = self._picacomic_api_module.get_comic_detail(album_id, option=self._option)
            
            return self._convert_to_meta_format([detail])
            
        except Exception as e:
            raise RuntimeError(f"获取专辑 {album_id} 失败: {e}")
    
    def search_albums(self, keyword: str, max_pages: int = 1, fast_mode: bool = False) -> Dict[str, Any]:
        """搜索漫画专辑
        
        Args:
            keyword: 搜索关键词
            max_pages: 最大搜索页数
            fast_mode: 快速模式，不获取详情，速度更快
            
        Returns:
            元数据 JSON 格式
        """
        try:
            if fast_mode:
                result = self._picacomic_api_module.search_comics(keyword, max_pages=max_pages, option=self._option)
                albums = result.get('results', [])
                return self._convert_basic_to_meta_format(albums)
            else:
                result = self._picacomic_api_module.search_comics_full(keyword, max_pages=max_pages, option=self._option)
                albums = result.get('results', [])
                return self._convert_to_meta_format(albums)
            
        except Exception as e:
            raise RuntimeError(f"搜索漫画失败: {e}")
    
    def _convert_basic_to_meta_format(self, albums: List[Dict[str, Any]]) -> Dict[str, Any]:
        """将基本搜索结果转换为元数据格式
        
        Args:
            albums: 基本搜索结果列表
            
        Returns:
            标准化的元数据格式
        """
        converted_albums = []
        
        for album in albums:
            album_id = album.get('comic_id', '')
            converted = {
                "rank": 0,
                "album_id": album_id,
                "title": album.get('title', ''),
                "title_jp": '',
                "author": album.get('author', ''),
                "pages": 0,
                "cover_url": '',
                "album_url": '',
                "tags": album.get('tags', []) + album.get('categories', []),
                "category_tags": [],
                "upload_date": '0',
                "update_date": '0'
            }
            converted_albums.append(converted)
        
        return {
            "total": len(converted_albums),
            "albums": converted_albums
        }
    
    def get_favorites(self) -> Dict[str, Any]:
        """获取收藏夹中的所有漫画
        
        Returns:
            元数据 JSON 格式
        """
        try:
            result = self._picacomic_api_module.get_favorite_comics_full(option=self._option)
            albums = result.get('comics', [])
            
            return self._convert_to_meta_format(albums)
            
        except Exception as e:
            raise RuntimeError(f"获取收藏夹失败: {e}")
    
    def _convert_to_meta_format(self, albums: List[Dict[str, Any]]) -> Dict[str, Any]:
        """将 Picacomic 格式转换为元数据格式
        
        Args:
            albums: Picacomic 返回的专辑列表
            
        Returns:
            标准化的元数据格式
        """
        converted_albums = []
        
        for idx, album in enumerate(albums, 1):
            comic_id = album.get('comic_id', '')
            cover_url = album.get('cover_url', '')
            
            converted = {
                "rank": idx,
                "album_id": comic_id,
                "title": album.get('title', ''),
                "title_jp": '',
                "author": album.get('author', ''),
                "pages": album.get('pages_count', 0),
                "cover_url": cover_url,
                "album_url": f"https://picaapi.picacomic.com/comics/{comic_id}" if comic_id else '',
                "tags": album.get('tags', []) + album.get('categories', []),
                "category_tags": album.get('categories', []),
                "upload_date": '0',
                "update_date": '0'
            }
            converted_albums.append(converted)
        
        return {
            "collection_name": "Picacomic 导入",
            "user": self.get_config('account', ''),
            "total_favorites": len(converted_albums),
            "last_updated": "",
            "albums": converted_albums
        }
