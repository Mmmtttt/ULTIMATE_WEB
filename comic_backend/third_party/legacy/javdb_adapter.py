"""
JAVDB API 适配器实现
基于 javdb-api-scraper 库
"""
import sys
import os
import logging
import importlib.util
from typing import Dict, List, Any, Optional, Tuple
from .base_adapter import BaseAdapter
from core.platform import Platform
from core.constants import THIRD_PARTY_CONFIG_PATH

logger = logging.getLogger(__name__)
_THIRD_PARTY_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


class JavdbAdapter(BaseAdapter):
    """JAVDB API 适配器
    
    使用 javdb-api-scraper 库进行视频搜索和清单导入
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """初始化 JAVDB 适配器
        
        Args:
            config: 配置字典
        """
        super().__init__(config)
        self._javdb_api = None
        self._load_javdb_api()
    
    @property
    def platform_name(self) -> str:
        return "JAVDB"
    
    @property
    def platform_prefix(self) -> str:
        return "JAVDB"
    
    def _load_javdb_api(self):
        """动态加载 JAVDB API 模块"""
        try:
            javdb_path = os.path.join(
                _THIRD_PARTY_ROOT,
                'javdb-api-scraper'
            )
            javdb_utils_path = os.path.abspath(os.path.join(javdb_path, "utils.py"))
            logger.info(f"JAVDB API 路径: {javdb_path}")
            
            # 确保 javdb-api-scraper 路径在最前面，优先于 comic_backend/utils
            if javdb_path in sys.path:
                sys.path.remove(javdb_path)
            sys.path.insert(0, javdb_path)
            
            # 强制 `import utils` 命中 javdb-api-scraper/utils.py，避免与其他 utils 包冲突
            cached_utils = sys.modules.get('utils')
            if cached_utils is not None:
                cached_file = os.path.abspath(str(getattr(cached_utils, '__file__', '') or ''))
                if cached_file != javdb_utils_path:
                    logger.info(f"清除冲突 utils 模块: {cached_file}")
                    del sys.modules['utils']

            if os.path.exists(javdb_utils_path) and 'utils' not in sys.modules:
                spec = importlib.util.spec_from_file_location('utils', javdb_utils_path)
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    sys.modules['utils'] = module
                    logger.info(f"已绑定 javdb utils 模块: {javdb_utils_path}")
            
            from javdb_api import JavdbAPI
            domain_index = self.get_config('domain_index', 0)
            logger.info(f"初始化 JAVDB API，domain_index: {domain_index}")
            self._javdb_api = JavdbAPI(domain_index=domain_index)
            
            # 从 third_party_config.json 读取 cookies 并设置
            self._load_cookies_from_config()
                
        except ImportError as e:
            logger.error(f"JAVDB API 模块导入失败: {e}")
            raise ImportError(f"JAVDB API 模块未找到: {e}")
        except Exception as e:
            logger.error(f"JAVDB API 初始化失败: {e}")
            raise RuntimeError(f"JAVDB API 初始化失败: {e}")
    
    def _load_cookies_from_config(self):
        """从 third_party_config.json 读取并设置 cookies"""
        try:
            config_path = THIRD_PARTY_CONFIG_PATH
            
            if not os.path.exists(config_path):
                logger.warning(f"未找到配置文件: {config_path}")
                return
            
            import json
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            javdb_config = config.get('adapters', {}).get('javdb', {})
            cookies = javdb_config.get('cookies', {})
            
            if not cookies:
                logger.warning("third_party_config.json 中未找到 JAVDB cookies")
                return
            
            logger.info(f"从 third_party_config.json 读取到 JAVDB cookies")
            logger.info(f"Cookies 键: {list(cookies.keys())}")
            
            # 直接设置 cookies 到 session（不使用 domain 参数）
            for key, value in cookies.items():
                self._javdb_api.session.cookies.set(key, value)
            
            logger.info("已成功设置 JAVDB cookies 到 session")
            logger.info(f"Session cookies: {dict(self._javdb_api.session.cookies)}")
                
        except Exception as e:
            logger.error(f"加载 cookies 失败: {e}", exc_info=True)
    
    def get_album_by_id(self, album_id: str) -> Dict[str, Any]:
        """根据 ID 获取专辑信息（视频）
        
        Args:
            album_id: 视频 ID
            
        Returns:
            完整的视频详情
        """
        try:
            detail = self._javdb_api.get_video_detail(album_id)
            
            return {
                'videos': [detail]
            }
            
        except Exception as e:
            raise RuntimeError(f"获取视频 {album_id} 失败: {e}")
    
    def search_albums(self, keyword: str, page: int = 1, max_pages: int = 1, fast_mode: bool = False) -> Dict[str, Any]:
        """搜索视频
        
        Args:
            keyword: 搜索关键词
            page: 起始页码
            max_pages: 最大搜索页数
            fast_mode: 快速模式，不获取详情，速度更快
            
        Returns:
            搜索结果
        """
        try:
            result = self._javdb_api.search_videos(keyword, page=page, max_pages=max_pages)
            videos = result.get('videos', [])
            
            return self._convert_videos_to_meta_format(videos)
            
        except Exception as e:
            raise RuntimeError(f"搜索视频失败: {e}")
    
    def get_favorites(self) -> Dict[str, Any]:
        """获取收藏夹中的所有视频
        
        Returns:
            元数据 JSON 格式
        """
        try:
            all_work = []
            user_lists = self.get_user_lists()
            for list_data in user_lists.get('lists', []):
                list_id = list_data.get('list_id')
                if list_id:
                    list_detail = self.get_list_detail(list_id)
                    all_work.extend(list_detail.get('works', []))
            
            return self._convert_videos_to_meta_format(all_work)
            
        except Exception as e:
            raise RuntimeError(f"获取收藏夹失败: {e}")
    
    def get_user_lists(self) -> Dict[str, Any]:
        """获取用户的清单列表
        
        Returns:
            包含清单列表的字典
        """
        try:
            logger.info("开始调用 JAVDB API get_user_lists_all")
            lists = self._javdb_api.get_user_lists_all()
            logger.info(f"JAVDB API 返回清单数: {len(lists)}")
            if lists:
                logger.info(f"清单详情: {lists}")
            else:
                logger.warning("未获取到任何清单，请检查是否已登录 JAVDB")
            return {"lists": lists}
        except Exception as e:
            logger.error(f"获取用户清单失败: {e}", exc_info=True)
            raise RuntimeError(f"获取用户清单失败: {e}")
    
    def get_list_detail(self, list_id: str) -> Dict[str, Any]:
        """获取清单的详细内容
        
        Args:
            list_id: 清单ID
            
        Returns:
            包含清单详情和内容的字典
        """
        try:
            result = self._javdb_api.get_list_detail_all(list_id)
            return {
                "list_id": result.get('list_id', list_id),
                "list_name": result.get('list_name', ''),
                "works": result.get('works', [])
            }
        except Exception as e:
            raise RuntimeError(f"获取清单详情失败: {e}")
    
    def _convert_videos_to_meta_format(self, videos: List[Dict[str, Any]]) -> Dict[str, Any]:
        """将 JAVDB 视频格式转换为元数据格式
        
        Args:
            videos: JAVDB 返回的视频列表
            
        Returns:
            标准化的元数据格式
        """
        converted_videos = []
        
        for video in videos:
            video_id = video.get('video_id', '')
            converted = {
                "video_id": video_id,
                "code": video.get('code', ''),
                "title": video.get('title', ''),
                "date": video.get('date', ''),
                "tags": video.get('tags', []),
                "actors": video.get('actors', []),
                "cover_url": video.get('cover_url', ''),
                "rating": video.get('rating', '')
            }
            converted_videos.append(converted)
        
        return {
            "collection_name": "JAVDB 导入",
            "user": "",
            "total_favorites": len(converted_videos),
            "last_updated": "",
            "videos": converted_videos
        }
    
    def _convert_video_to_meta_format(self, videos: List[Dict[str, Any]]) -> Dict[str, Any]:
        """将 JAVDB 视频详情格式转换为元数据格式
        
        Args:
            videos: JAVDB 返回的视频详情列表
            
        Returns:
            标准化的元数据格式
        """
        return self._convert_videos_to_meta_format(videos)
    
    def download_album(
        self, 
        album_id: str, 
        download_dir: str, 
        show_progress: bool = False,
        **kwargs
    ) -> Tuple[Dict[str, Any], bool]:
        """下载视频（暂不实现）"""
        return {}, False
    
    def download_cover(
        self,
        album_id: str,
        save_path: str,
        show_progress: bool = False
    ) -> Tuple[Dict[str, Any], bool]:
        """下载封面（暂不实现）"""
        return {}, False
