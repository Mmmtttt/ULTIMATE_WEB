"""
JMComic API 适配器实现
基于 JMComic-Crawler-Python 库
"""
import sys
import os
from typing import Dict, List, Any, Optional, Tuple
from .base_adapter import BaseAdapter
from core.platform import Platform


class JMComicAdapter(BaseAdapter):
    """JMComic API 适配器
    
    使用 JMComic-Crawler-Python 库进行漫画搜索和下载
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """初始化 JMComic 适配器
        
        Args:
            config: 配置字典，包含：
                - username: 用户名
                - password: 密码
                - config_path: config.json 文件路径
        """
        super().__init__(config)
        self._jmcomic_api = None
        self._load_jmcomic_api()
    
    @property
    def platform_name(self) -> str:
        return "JMComic"
    
    @property
    def platform_prefix(self) -> str:
        return "JM"
    
    def _load_jmcomic_api(self):
        """动态加载 JMComic API 模块并写入配置"""
        try:
            jmcomic_path = os.path.join(
                os.path.dirname(__file__),
                'JMComic-Crawler-Python'
            )
            
            if jmcomic_path not in sys.path:
                sys.path.insert(0, jmcomic_path)
            
            from jmcomic_api import get_client, load_config
            import json
            
            config_path = self.get_config('config_path')
            if config_path:
                # config_path 是相对于 third_party 目录的路径
                # 例如: JMComic-Crawler-Python/config.json
                full_config_path = os.path.join(
                    os.path.dirname(__file__),
                    config_path
                )
                
                # 确保目录存在
                config_dir = os.path.dirname(full_config_path)
                if not os.path.exists(config_dir):
                    os.makedirs(config_dir, exist_ok=True)
                
                username = self.get_config('username')
                password = self.get_config('password')
                download_dir = self.get_config('download_dir', '../../data/pictures')
                output_json = self.get_config('output_json', 'comics_database.json')
                progress_file = self.get_config('progress_file', 'download_progress.json')
                favorite_list_file = self.get_config('favorite_list_file', 'favorite_comics.txt')
                consecutive_hit_threshold = self.get_config('consecutive_hit_threshold', 10)
                collection_name = self.get_config('collection_name', '我的最爱')
                
                config_data = {
                    "username": username,
                    "password": password,
                    "download_dir": download_dir,
                    "output_json": output_json,
                    "progress_file": progress_file,
                    "favorite_list_file": favorite_list_file,
                    "consecutive_hit_threshold": consecutive_hit_threshold,
                    "collection_name": collection_name
                }
                
                try:
                    with open(full_config_path, 'w', encoding='utf-8') as f:
                        json.dump(config_data, f, ensure_ascii=False, indent=2)
                except Exception as e:
                    print(f"写入 JMComic 配置文件失败: {e}")
                
                # load_config() 会自动加载 config.json，不需要传参数
                # 配置文件已经写入，直接使用即可
            
            username = self.get_config('username')
            password = self.get_config('password')
            
            if username and password:
                self._jmcomic_api = get_client(username=username, password=password)
            else:
                self._jmcomic_api = get_client()
                
        except ImportError as e:
            raise ImportError(f"JMComic API 模块未找到: {e}")
        except Exception as e:
            raise RuntimeError(f"JMComic API 初始化失败: {e}")
    
    def get_album_by_id(self, album_id: str) -> Dict[str, Any]:
        """根据 ID 获取专辑信息
        
        Args:
            album_id: 漫画专辑 ID
            
        Returns:
            元数据 JSON 格式
        """
        try:
            from jmcomic_api import get_album_detail
            
            detail = get_album_detail(int(album_id))
            
            return self._convert_to_meta_format([detail])
            
        except Exception as e:
            error_msg = str(e)
            # 检查是否是第三方API服务器错误
            if "Could not connect to mysql" in error_msg or "conn2" in error_msg:
                raise RuntimeError(f"第三方API服务器暂时不可用（数据库错误），请稍后重试。专辑ID: {album_id}")
            elif "Not legal request" in error_msg or "401" in error_msg:
                raise RuntimeError(f"第三方API拒绝请求，可能是ID无效或需要登录。专辑ID: {album_id}")
            else:
                raise RuntimeError(f"获取专辑 {album_id} 失败: {e}")
    
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
                'total_pages': 总页数,
                'albums': 漫画专辑列表,
                'collection_name': 'JMComic 导入',
                'user': 用户名,
                'total_favorites': 数量,
                'last_updated': 最后更新时间
            }
        """
        try:
            from jmcomic_api import search_comics_full, search_comics
            
            if fast_mode:
                result = search_comics(keyword, page=page, max_pages=max_pages)
                albums = result.get('results', [])
                total_pages = result.get('page_count')
                has_next = page < total_pages if total_pages else len(albums) > 0
                converted = self._convert_basic_to_meta_format(albums)
                return {
                    'page': page,
                    'has_next': has_next,
                    'total_pages': total_pages,
                    'albums': converted.get('albums', []),
                    'collection_name': 'JMComic 导入',
                    'user': self.get_config('username', ''),
                    'total_favorites': len(albums),
                    'last_updated': ''
                }
            else:
                result = search_comics_full(keyword, page=page, max_pages=max_pages)
                albums = result.get('results', [])
                total_pages = result.get('page_count')
                has_next = page < total_pages if total_pages else len(albums) > 0
                converted = self._convert_to_meta_format(albums)
                return {
                    'page': page,
                    'has_next': has_next,
                    'total_pages': total_pages,
                    'albums': converted.get('albums', []),
                    'collection_name': converted.get('collection_name', 'JMComic 导入'),
                    'user': converted.get('user', ''),
                    'total_favorites': converted.get('total_favorites', len(albums)),
                    'last_updated': converted.get('last_updated', '')
                }
            
        except Exception as e:
            error_msg = str(e)
            if "Could not connect to mysql" in error_msg or "conn2" in error_msg:
                raise RuntimeError(f"第三方API服务器暂时不可用（数据库错误），请稍后重试。关键词: {keyword}")
            else:
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
            album_id = album.get('album_id', 0)
            converted = {
                "rank": album.get('rank', 0),
                "album_id": album_id,
                "title": album.get('title', ''),
                "title_jp": '',
                "author": '',
                "pages": 0,
                "cover_url": f"https://cdn-msp3.18comic.vip/media/albums/{album_id}.jpg",
                "album_url": '',
                "tags": album.get('tags', []),
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
            from jmcomic_api import get_favorite_comics_full
            
            result = get_favorite_comics_full()
            albums = result.get('comics', [])
            
            return self._convert_to_meta_format(albums)
            
        except Exception as e:
            error_msg = str(e)
            if "Could not connect to mysql" in error_msg or "conn2" in error_msg:
                raise RuntimeError("第三方API服务器暂时不可用（数据库错误），请稍后重试。")
            else:
                raise RuntimeError(f"获取收藏夹失败: {e}")
    
    def _convert_to_meta_format(self, albums: List[Dict[str, Any]]) -> Dict[str, Any]:
        """将 JMComic 格式转换为元数据格式
        
        Args:
            albums: JMComic 返回的专辑列表
            
        Returns:
            标准化的元数据格式
        """
        converted_albums = []
        
        for album in albums:
            converted = {
                "rank": album.get('rank', 0),
                "album_id": album.get('album_id', 0),
                "title": album.get('title', ''),
                "title_jp": album.get('title_jp', ''),
                "author": album.get('author', ''),
                "pages": album.get('pages', 0),
                "cover_url": album.get('cover_url', ''),
                "album_url": album.get('album_url', ''),
                "tags": album.get('tags', []),
                "category_tags": album.get('category_tags', []),
                "upload_date": album.get('upload_date', '0'),
                "update_date": album.get('update_date', '0')
            }
            converted_albums.append(converted)
        
        return {
            "collection_name": "JMComic 导入",
            "user": self.get_config('username', ''),
            "total_favorites": len(converted_albums),
            "last_updated": "",
            "albums": converted_albums
        }
    
    def download_album(
        self, 
        album_id: str, 
        download_dir: str, 
        show_progress: bool = False,
        **kwargs
    ) -> Tuple[Dict[str, Any], bool]:
        """下载漫画专辑"""
        try:
            from jmcomic_api import download_album
            
            decode_images = kwargs.get('decode_images', True)
            
            detail, success = download_album(
                int(album_id),
                download_dir=download_dir,
                show_progress=show_progress,
                decode_images=decode_images
            )
            
            return detail, success
            
        except Exception as e:
            from infrastructure.logger import error_logger
            error_logger.error(f"下载 JM 漫画失败: {album_id}, {e}")
            return {}, False
    
    def download_cover(
        self,
        album_id: str,
        save_path: str,
        show_progress: bool = False
    ) -> Tuple[Dict[str, Any], bool]:
        """下载漫画封面"""
        try:
            import requests
            from PIL import Image
            from io import BytesIO
            
            cover_url = self.get_cover_url(album_id)
            if not cover_url:
                return {}, False
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            response = requests.get(cover_url, headers=headers, timeout=30)
            response.raise_for_status()
            
            with Image.open(BytesIO(response.content)) as img:
                if img.mode in ('RGBA', 'P'):
                    img = img.convert('RGB')
                img.save(save_path, 'JPEG', quality=95)
            
            return {'cover_url': cover_url, 'save_path': save_path}, True
            
        except Exception as e:
            from infrastructure.logger import error_logger
            error_logger.error(f"下载 JM 封面失败: {album_id}, {e}")
            return {}, False
    
    def get_comic_dir(self, album_id: str, author: str = None, title: str = None, base_dir: str = None) -> str:
        """获取漫画目录路径"""
        if base_dir:
            return os.path.join(base_dir, album_id)
        return album_id
    
    def get_cover_url(self, album_id: str) -> Optional[str]:
        """获取封面URL"""
        return f"https://cdn-msp3.18comic.vip/media/albums/{album_id}.jpg"
    
    def get_image_url(self, album_id: str, page: int) -> Optional[str]:
        """获取单张图片URL"""
        return f"https://cdn-msp.jmapinodeudzn.net/media/photos/{album_id}/{page:05d}.webp"
