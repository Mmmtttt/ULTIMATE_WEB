"""
JMComic API 适配器实现
基于 JMComic-Crawler-Python 库
"""
import sys
import os
from typing import Dict, List, Any, Optional, Tuple
from .base_adapter import BaseAdapter
from core.constants import JM_PICTURES_DIR
from core.platform import Platform
from infrastructure.logger import app_logger, error_logger

_THIRD_PARTY_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


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

    @staticmethod
    def _mask_username(username: str) -> str:
        username = '' if username is None else str(username)
        if not username:
            return ""
        if len(username) <= 2:
            return "*" * len(username)
        return f"{username[:1]}***{username[-1:]}"

    def _get_login_credentials(self) -> Tuple[str, str]:
        username = self.get_config('username', '')
        password = self.get_config('password', '')
        username = '' if username is None else str(username).strip()
        password = '' if password is None else str(password).strip()
        return username, password
    
    def _load_jmcomic_api(self):
        """动态加载 JMComic API 模块并写入配置"""
        try:
            jmcomic_path = os.path.join(
                _THIRD_PARTY_ROOT,
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
                    _THIRD_PARTY_ROOT,
                    config_path
                )
                
                # 确保目录存在
                config_dir = os.path.dirname(full_config_path)
                if not os.path.exists(config_dir):
                    os.makedirs(config_dir, exist_ok=True)
                
                username = self.get_config('username')
                password = self.get_config('password')
                download_dir = self.get_config('download_dir', JM_PICTURES_DIR)
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
                try:
                    self._jmcomic_api = get_client(username=username, password=password)
                    app_logger.info(
                        f"JM adapter init login success, user={self._mask_username(username)}"
                    )
                except Exception as e:
                    error_logger.error(
                        f"JM adapter init login failed, fallback to guest. "
                        f"user={self._mask_username(username)}, error={e}"
                    )
                    self._jmcomic_api = get_client(username='', password='')
            else:
                app_logger.info("JM adapter init in guest mode (no credentials configured)")
                self._jmcomic_api = get_client(username='', password='')
                
        except ImportError as e:
            raise ImportError(f"JMComic API 模块未找到: {e}")
        except Exception as e:
            raise RuntimeError(f"JMComic API 初始化失败: {e}")

    def _get_search_client(self) -> Tuple[Any, bool]:
        """
        Build search client in strict API-login mode.
        Search should always run with logged-in API session.
        Returns:
            (client, is_logged_in_search)
        """
        from jmcomic_api import get_client

        username, password = self._get_login_credentials()

        if not username or not password:
            raise RuntimeError(
                "JM 账号或密码未配置。当前搜索仅支持 API 登录态，请检查 "
                "third_party_config.json -> adapters -> jmcomic"
            )

        try:
            client = get_client(username=username, password=password)
            client_key = getattr(client, 'client_key', type(client).__name__)
            app_logger.info(
                f"JM search api login success, user={self._mask_username(username)}, client={client_key}"
            )
        except Exception as e:
            error_logger.error(
                f"JM search api login failed, user={self._mask_username(username)}, error={e}"
            )
            raise RuntimeError(
                "JM API 登录失败，无法执行登录态搜索。请检查账号密码或网络后重试。"
            ) from e

        if getattr(client, 'client_key', '') != 'api':
            error_logger.error(
                f"JM search requires api client, got={getattr(client, 'client_key', type(client).__name__)}"
            )
            raise RuntimeError("JM 搜索客户端异常：未获取到 API 客户端。")

        if not self._is_login_session_valid(client, username):
            error_logger.error(
                f"JM search api login invalid session, user={self._mask_username(username)}"
            )
            raise RuntimeError("JM 登录态校验失败，无法执行登录态搜索。")

        app_logger.info(
            f"JM search api login verified, user={self._mask_username(username)}"
        )
        return client, True

    def _build_html_search_client(self, username: str, password: str) -> Optional[Any]:
        """
        Build a login session using JM html client (web endpoint semantics).
        Fallback to api client when html client cannot be used.
        """
        try:
            import jmcomic

            option = jmcomic.JmOption.construct({
                'download': {
                    'dir': self.get_config('download_dir', JM_PICTURES_DIR),
                    'image': {
                        'suffix': '.jpg'
                    }
                },
                'dir_rule': {
                    'base_dir': self.get_config('download_dir', JM_PICTURES_DIR),
                    'rule': 'Bd_Aid_Pindex'
                },
                'client': {
                    'impl': 'html',
                    # Prefer the same host family as browser search URL.
                    'domain': ['18comic.vip'],
                }
            })
            client = option.build_jm_client()
            client.login(username, password)

            client_key = getattr(client, 'client_key', type(client).__name__)
            app_logger.info(
                f"JM search html login success, user={self._mask_username(username)}, client={client_key}"
            )

            if not self._is_login_session_valid(client, username):
                error_logger.error(
                    f"JM search html login invalid session, fallback to api. "
                    f"user={self._mask_username(username)}"
                )
                return None

            if not self._is_search_endpoint_valid(client):
                error_logger.error(
                    f"JM search html endpoint probe failed, fallback to api. "
                    f"user={self._mask_username(username)}"
                )
                return None

            app_logger.info(
                f"JM search html login verified, user={self._mask_username(username)}"
            )
            return client
        except Exception as e:
            app_logger.info(
                f"JM search html login unavailable, keep api path. "
                f"user={self._mask_username(username)}, error={e}"
            )
            return None

    def _is_login_session_valid(self, client: Any, username: str) -> bool:
        """
        Validate that the JM session is truly authenticated.
        We probe a login-required endpoint; success means the session is usable.
        """
        try:
            kwargs = {
                'page': 1,
                'folder_id': '0',
            }
            if username:
                kwargs['username'] = username

            favorite_page = client.favorite_folder(**kwargs)
            total = getattr(favorite_page, 'total', None)
            app_logger.info(
                f"JM search login probe passed, user={self._mask_username(username)}, favorites_total={total}"
            )
            return True
        except Exception as e:
            error_logger.error(
                f"JM search login probe failed, user={self._mask_username(username)}, error={e}"
            )
            return False

    def _is_search_endpoint_valid(self, client: Any) -> bool:
        """
        Probe search endpoint availability (especially useful for html client anti-bot issues).
        """
        try:
            probe_page = client.search_site(search_query='jmcomic', page=1)
            total = getattr(probe_page, 'total', None)
            app_logger.info(f"JM search endpoint probe passed, total={total}")
            return True
        except Exception as e:
            error_logger.error(f"JM search endpoint probe failed, error={e}")
            return False
    
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
            search_client, is_logged_in_search = self._get_search_client()
            search_user, _ = self._get_login_credentials()
            if not is_logged_in_search:
                search_user = ''
            client_key = getattr(search_client, 'client_key', type(search_client).__name__)
            app_logger.info(
                f"JM search start: mode={'login' if is_logged_in_search else 'guest'}, "
                f"keyword={keyword}, keyword_repr={keyword!r}, page={page}, "
                f"max_pages={max_pages}, fast_mode={fast_mode}, client={client_key}"
            )
            
            if fast_mode:
                result = search_comics(
                    keyword,
                    page=page,
                    max_pages=max_pages,
                    client=search_client,
                    enable_query_fallback=False
                )
                albums = result.get('results', [])
                total_pages = result.get('page_count')
                total = result.get('total')
                effective_query = result.get('query', keyword)
                has_next = page < total_pages if total_pages else len(albums) > 0
                converted = self._convert_basic_to_meta_format(albums)
                if effective_query != keyword:
                    app_logger.info(
                        f"JM search query adjusted: original={keyword!r}, effective={effective_query!r}"
                    )
                app_logger.info(
                    f"JM search done: mode={'login' if is_logged_in_search else 'guest'}, "
                    f"count={len(albums)}, total={total}, total_pages={total_pages}, has_next={has_next}"
                )
                return {
                    'page': page,
                    'has_next': has_next,
                    'total_pages': total_pages,
                    'albums': converted.get('albums', []),
                    'collection_name': 'JMComic 导入',
                    'user': search_user,
                    'total_favorites': len(albums),
                    'last_updated': ''
                }
            else:
                result = search_comics_full(
                    keyword,
                    page=page,
                    max_pages=max_pages,
                    client=search_client,
                    enable_query_fallback=False
                )
                albums = result.get('results', [])
                total_pages = result.get('page_count')
                total = result.get('total')
                effective_query = result.get('query', keyword)
                has_next = page < total_pages if total_pages else len(albums) > 0
                converted = self._convert_to_meta_format(albums)
                if effective_query != keyword:
                    app_logger.info(
                        f"JM search query adjusted: original={keyword!r}, effective={effective_query!r}"
                    )
                app_logger.info(
                    f"JM search done: mode={'login' if is_logged_in_search else 'guest'}, "
                    f"count={len(albums)}, total={total}, total_pages={total_pages}, has_next={has_next}"
                )
                return {
                    'page': page,
                    'has_next': has_next,
                    'total_pages': total_pages,
                    'albums': converted.get('albums', []),
                    'collection_name': converted.get('collection_name', 'JMComic 导入'),
                    'user': search_user,
                    'total_favorites': converted.get('total_favorites', len(albums)),
                    'last_updated': converted.get('last_updated', '')
                }
            
        except Exception as e:
            error_logger.error(
                f"JM search failed: keyword={keyword}, page={page}, "
                f"max_pages={max_pages}, fast_mode={fast_mode}, error={e}"
            )
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
            raw_author = album.get('author', '')
            if isinstance(raw_author, list):
                author = ''
                for item in raw_author:
                    text = str(item or '').strip()
                    if text:
                        author = text
                        break
            else:
                author = str(raw_author or '').strip()

            raw_tags = album.get('tags', [])
            tags = raw_tags if isinstance(raw_tags, list) else []

            converted = {
                "rank": album.get('rank', 0),
                "album_id": album_id,
                "title": album.get('title', ''),
                "title_jp": '',
                "author": author,
                "pages": 0,
                "cover_url": f"https://cdn-msp3.18comic.vip/media/albums/{album_id}.jpg",
                "album_url": '',
                "tags": tags,
                "category_tags": [],
                "upload_date": '0',
                "update_date": '0'
            }
            converted_albums.append(converted)
        
        return {
            "total": len(converted_albums),
            "albums": converted_albums
        }

    def get_favorites_basic(self) -> Dict[str, Any]:
        """获取收藏夹基础信息（不逐个拉详情，速度更快）"""
        try:
            from jmcomic_api import get_favorite_comics, get_client

            username = self.get_config('username')
            password = self.get_config('password')
            if not username or not password:
                raise RuntimeError("JM 账号或密码未配置，请检查 third_party_config.json -> adapters -> jmcomic")

            get_client(username=username, password=password)
            result = get_favorite_comics(username=username, password=password)
            basic_albums = result.get('comics', [])
            converted = self._convert_basic_to_meta_format(basic_albums)

            return {
                "collection_name": "JMComic 导入",
                "user": username,
                "total_favorites": converted.get("total", len(converted.get("albums", []))),
                "last_updated": "",
                "albums": converted.get("albums", [])
            }
        except Exception as e:
            error_msg = str(e)
            if "請先登入會員" in error_msg or '"code":401' in error_msg:
                raise RuntimeError("JM 登录状态失效，请检查账号密码后重试。")
            raise RuntimeError(f"获取收藏夹失败: {e}")
    
    def get_favorites(self) -> Dict[str, Any]:
        """获取收藏夹中的所有漫画
        
        Returns:
            元数据 JSON 格式
        """
        try:
            from jmcomic_api import get_favorite_comics_full, get_client

            username = self.get_config('username')
            password = self.get_config('password')
            if not username or not password:
                raise RuntimeError("JM 账号或密码未配置，请检查 third_party_config.json -> adapters -> jmcomic")

            # 每次收藏请求前用配置账号刷新登录态，避免会话过期导致 401
            get_client(username=username, password=password)
            result = get_favorite_comics_full(username=username, password=password)
            albums = result.get('comics', [])
            
            return self._convert_to_meta_format(albums)
            
        except Exception as e:
            error_msg = str(e)
            if "Could not connect to mysql" in error_msg or "conn2" in error_msg:
                raise RuntimeError("第三方API服务器暂时不可用（数据库错误），请稍后重试。")
            elif "請先登入會員" in error_msg or '"code":401' in error_msg:
                raise RuntimeError("JM 登录状态失效，请检查账号密码后重试。")
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
