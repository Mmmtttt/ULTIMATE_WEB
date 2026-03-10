from typing import List, Dict, Set
from concurrent.futures import ThreadPoolExecutor, as_completed
import os
import requests
import threading
from PIL import Image
from io import BytesIO
from domain.author import AuthorSubscription, AuthorRepository
from infrastructure.persistence.repositories import AuthorJsonRepository
from infrastructure.persistence.repositories.comic_repository_impl import ComicJsonRepository
from infrastructure.persistence.repositories.recommendation_repository_impl import RecommendationJsonRepository
from infrastructure.common.result import ServiceResult
from infrastructure.logger import app_logger, error_logger
from infrastructure.persistence.json_storage import JsonStorage
from infrastructure.persistence.cache import CacheManager
from core.utils import get_current_time, generate_id
from core.constants import JM_AUTHOR_COVER_CACHE_DIR, PK_AUTHOR_COVER_CACHE_DIR
from third_party import external_api


class AuthorAppService:
    _cache_manager = CacheManager()
    
    def __init__(self, author_repo: AuthorRepository = None):
        self._author_repo = author_repo or AuthorJsonRepository()
        self._comic_repo = ComicJsonRepository()
        self._recommendation_repo = RecommendationJsonRepository()
    
    def get_all_authors(self) -> ServiceResult:
        """获取所有作者（主页+推荐页）"""
        try:
            author_set = set()
            
            comics = self._comic_repo.get_all()
            for comic in comics:
                if comic.author and comic.author.strip():
                    author_set.add(comic.author.strip())
            
            recommendations = self._recommendation_repo.get_all()
            for rec in recommendations:
                if rec.author and rec.author.strip():
                    author_set.add(rec.author.strip())
            
            subscribed_authors = self._author_repo.get_all()
            subscribed_author_names = {a.name for a in subscribed_authors}
            
            all_authors = []
            for name in sorted(author_set):
                is_subscribed = name in subscribed_author_names
                all_authors.append({
                    "name": name,
                    "is_subscribed": is_subscribed,
                    "subscription": next((a.to_dict() for a in subscribed_authors if a.name == name), None)
                })
            
            app_logger.info(f"获取所有作者成功，共 {len(all_authors)} 个")
            return ServiceResult.ok(all_authors)
        except Exception as e:
            error_logger.error(f"获取所有作者失败: {e}")
            return ServiceResult.error("获取所有作者失败")
    
    def get_subscription_list(self) -> ServiceResult:
        try:
            authors = self._author_repo.get_all()
            author_list = [a.to_dict() for a in authors]
            app_logger.info(f"获取作者订阅列表成功，共 {len(author_list)} 个")
            return ServiceResult.ok(author_list)
        except Exception as e:
            error_logger.error(f"获取作者订阅列表失败: {e}")
            return ServiceResult.error("获取作者订阅列表失败")
    
    def subscribe_author(self, name: str) -> ServiceResult:
        try:
            if not name or not name.strip():
                return ServiceResult.error("作者名称不能为空")
            
            name = name.strip()
            
            if self._author_repo.exists_by_name(name):
                return ServiceResult.error("已订阅该作者")
            
            author = AuthorSubscription(
                id=generate_id("author"),
                name=name,
                subscribe_time=get_current_time()
            )
            
            if not self._author_repo.save(author):
                return ServiceResult.error("订阅作者失败")
            
            app_logger.info(f"订阅作者成功: {name}")
            return ServiceResult.ok(author.to_dict(), "订阅成功")
        except Exception as e:
            error_logger.error(f"订阅作者失败: {e}")
            return ServiceResult.error("订阅作者失败")
    
    def unsubscribe_author(self, author_id: str) -> ServiceResult:
        try:
            author = self._author_repo.get_by_id(author_id)
            if not author:
                return ServiceResult.error("订阅不存在")
            
            if not self._author_repo.delete(author_id):
                return ServiceResult.error("取消订阅失败")
            
            app_logger.info(f"取消订阅作者成功: {author_id}")
            return ServiceResult.ok({"id": author_id}, "取消订阅成功")
        except Exception as e:
            error_logger.error(f"取消订阅作者失败: {e}")
            return ServiceResult.error("取消订阅作者失败")
    
    def _search_author_works(self, author_name: str) -> List[Dict]:
        from core.platform import get_supported_platforms
        
        works = []
        try:
            platforms_to_search = get_supported_platforms()
            platform_albums = {}
            max_result_count = 0
            
            for plat in platforms_to_search:
                try:
                    adapter_name = 'jmcomic' if plat == 'JM' else 'picacomic'
                    result = external_api.search_albums(author_name, max_pages=3, adapter_name=adapter_name, fast_mode=True)
                    albums = result.get("albums", [])
                    
                    if albums:
                        platform_albums[plat] = albums
                        if len(albums) > max_result_count:
                            max_result_count = len(albums)
                except Exception as e:
                    error_logger.error(f"搜索作者 {author_name} 在平台 {plat} 的作品失败: {e}")
                    continue
            
            for i in range(max_result_count):
                for plat in platforms_to_search:
                    if plat in platform_albums and i < len(platform_albums[plat]):
                        album = platform_albums[plat][i]
                        works.append({
                            "id": str(album.get("album_id", "")),
                            "title": album.get("title", ""),
                            "author": author_name,
                            "cover_url": album.get("cover_url", ""),
                            "pages": album.get("pages", 0),
                            "platform": plat
                        })
                
        except Exception as e:
            error_logger.error(f"搜索作者 {author_name} 作品失败: {e}")
        
        return works
    
    def check_author_updates(self, author_id: str = None) -> ServiceResult:
        try:
            if author_id:
                authors = [self._author_repo.get_by_id(author_id)]
                authors = [a for a in authors if a]
            else:
                authors = self._author_repo.get_all()
            
            if not authors:
                return ServiceResult.ok({"updated_authors": [], "total_new_works": 0})
            
            updated_authors = []
            total_new_works = 0
            
            for author in authors:
                try:
                    cache_key = f"author_works_{author.name}"
                    cached_works = self._cache_manager.get_persistent(cache_key, 'author_works')
                    
                    works = self._search_author_works(author.name)
                    
                    if not works:
                        continue
                    
                    latest_work = works[0]
                    latest_work_id = latest_work.get("id", "")
                    latest_work_title = latest_work.get("title", "")
                    
                    cached_latest_id = None
                    if cached_works:
                        first_cached = cached_works[0] if isinstance(cached_works, list) and cached_works else None
                        if first_cached:
                            cached_latest_id = first_cached.get("id", "")
                    
                    has_update = cached_latest_id is None or cached_latest_id != latest_work_id
                    new_count = 0
                    
                    if has_update:
                        new_count = 1
                        # 只在检测到更新时刷新本地缓存最近作品列表（例如前20个）
                        works_for_cache = works[:20]
                        self._cache_manager.set_persistent(cache_key, works_for_cache, 'author_works')
                    
                    author.update_check_info(
                        latest_work_id,
                        latest_work_title,
                        new_count
                    )
                    self._author_repo.save(author)
                    
                    if has_update:
                        updated_authors.append({
                            "author": author.to_dict(),
                            "new_works": [latest_work]
                        })
                        total_new_works += new_count
                        
                except Exception as e:
                    error_logger.error(f"检查作者 {author.name} 更新失败: {e}")
                    continue
            
            app_logger.info(f"检查作者更新完成，{len(updated_authors)} 个作者有更新，共 {total_new_works} 个新作品")
            return ServiceResult.ok({
                "updated_authors": updated_authors,
                "total_new_works": total_new_works
            })
        except Exception as e:
            error_logger.error(f"检查作者更新失败: {e}")
            return ServiceResult.error("检查作者更新失败")
    
    def get_author_new_works(self, author_id: str) -> ServiceResult:
        from core.platform import get_supported_platforms
        
        try:
            author = self._author_repo.get_by_id(author_id)
            if not author:
                return ServiceResult.error("订阅不存在")
            
            works = []
            try:
                platforms_to_search = get_supported_platforms()
                platform_albums = {}
                max_result_count = 0
                
                for plat in platforms_to_search:
                    try:
                        adapter_name = 'jmcomic' if plat == 'JM' else 'picacomic'
                        result = external_api.search_albums(author.name, max_pages=3, adapter_name=adapter_name, fast_mode=True)
                        albums = result.get("albums", [])
                        
                        if albums:
                            platform_albums[plat] = albums
                            if len(albums) > max_result_count:
                                max_result_count = len(albums)
                    except Exception as e:
                        error_logger.error(f"搜索作者 {author.name} 在平台 {plat} 的作品失败: {e}")
                        continue
                
                for i in range(max_result_count):
                    for plat in platforms_to_search:
                        if plat in platform_albums and i < len(platform_albums[plat]):
                            album = platform_albums[plat][i]
                            works.append({
                                "id": str(album.get("album_id", "")),
                                "title": album.get("title", ""),
                                "author": author.name,
                                "cover_url": album.get("cover_url", ""),
                                "pages": album.get("pages", 0),
                                "platform": plat
                            })
                
            except Exception as e:
                error_logger.error(f"搜索作者 {author.name} 作品失败: {e}")
            
            if not works:
                return ServiceResult.ok({"author": author.to_dict(), "new_works": []})
            
            new_works = []
            if not author.last_work_id:
                new_works = works[:5]
            else:
                found_last = False
                for work in works:
                    if work.get("id") == author.last_work_id:
                        found_last = True
                        break
                    new_works.append(work)
                
                if not found_last:
                    new_works = works[:5]
            
            if new_works:
                try:
                    for work in new_works:
                        try:
                            from third_party import external_api
                            detail = external_api.get_album_by_id(work["id"])
                            if detail and detail.get("albums"):
                                album = detail["albums"][0]
                                work["author"] = album.get("author", author.name)
                                work["cover_url"] = album.get("cover_url", "")
                                work["pages"] = album.get("pages", 0)
                        except Exception as e:
                            error_logger.error(f"获取作品 {work['id']} 详情失败: {e}")
                except Exception as e:
                    error_logger.error(f"获取作品详情失败: {e}")
            
            return ServiceResult.ok({
                "author": author.to_dict(),
                "new_works": new_works
            })
        except Exception as e:
            error_logger.error(f"获取作者新作品失败: {e}")
            return ServiceResult.error("获取作者新作品失败")
    
    def clear_author_new_count(self, author_id: str) -> ServiceResult:
        try:
            author = self._author_repo.get_by_id(author_id)
            if not author:
                return ServiceResult.error("订阅不存在")
            
            author.clear_new_count()
            self._author_repo.save(author)
            
            return ServiceResult.ok({"id": author_id}, "已清除")
        except Exception as e:
            error_logger.error(f"清除新作品计数失败: {e}")
            return ServiceResult.error("清除新作品计数失败")
    
    def _download_author_cover(self, album_id: str, cover_url: str, platform: str = 'JM') -> str:
        """下载作者作品封面到缓存目录
        
        Args:
            album_id: 作品ID
            cover_url: 封面URL
            platform: 平台名称
            
        Returns:
            本地封面路径，失败返回空字符串
        """
        if not cover_url:
            return ""
        
        cache_dir = JM_AUTHOR_COVER_CACHE_DIR if platform == 'JM' else PK_AUTHOR_COVER_CACHE_DIR
        local_path = os.path.join(cache_dir, f"{album_id}.jpg")
        
        if os.path.exists(local_path):
            return f"/static/cover/{platform}/author_cache/{album_id}.jpg"
        
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            response = requests.get(cover_url, headers=headers, timeout=10)
            response.raise_for_status()
            
            os.makedirs(cache_dir, exist_ok=True)
            
            with Image.open(BytesIO(response.content)) as img:
                if img.mode in ('RGBA', 'P'):
                    img = img.convert('RGB')
                img.save(local_path, 'JPEG', quality=85)
            
            return f"/static/cover/{platform}/author_cache/{album_id}.jpg"
        except Exception as e:
            error_logger.error(f"下载作者作品封面失败 {album_id}: {e}")
            return cover_url
    
    def _get_existing_comic_ids(self) -> Set[str]:
        """获取已有漫画ID集合"""
        existing_ids = set()
        
        try:
            home_storage = JsonStorage('data/meta_data/comics_database.json')
            home_data = home_storage.read()
            for comic in home_data.get('comics', []):
                raw_id = comic.get('id', '')
                if raw_id.startswith('JM_'):
                    raw_id = raw_id[3:]
                existing_ids.add(raw_id)
        except Exception as e:
            error_logger.error(f"获取主页漫画ID失败: {e}")
        
        try:
            rec_storage = JsonStorage('data/meta_data/recommendations_database.json')
            rec_data = rec_storage.read()
            for comic in rec_data.get('recommendations', []):
                raw_id = comic.get('id', '')
                if raw_id.startswith('JM_'):
                    raw_id = raw_id[3:]
                existing_ids.add(raw_id)
        except Exception as e:
            error_logger.error(f"获取推荐页漫画ID失败: {e}")
        
        return existing_ids
    
    def get_author_works_paginated(self, author_id: str, offset: int = 0, limit: int = 5) -> ServiceResult:
        from core.platform import get_supported_platforms
        
        try:
            author = self._author_repo.get_by_id(author_id)
            if not author:
                return ServiceResult.error("订阅不存在")
            
            cache_key = f"author_works_{author.name}"
            
            # 无论offset是多少，都先尝试从缓存读取，但只作为第一页的快速展示
            # 当需要加载更多或者缓存中没有足够数据时，总是去重新搜索
            cached_all_works = self._cache_manager.get_persistent(cache_key, 'author_works')
            
            # 如果是第一页且缓存有数据，先尝试用缓存
            if offset == 0 and cached_all_works is not None:
                existing_ids = self._get_existing_comic_ids()
                filtered_works = [w for w in cached_all_works if w.get('id') not in existing_ids]
                total = len(filtered_works)
                paginated_works = filtered_works[offset:offset + limit]
                
                # 如果缓存中有足够的数据（达到limit），可以先显示缓存，但设置has_more为true，允许用户点击加载更多
                has_more = True
                
                app_logger.info(f"[Cache] 从持久化缓存读取作者 {author.name} 作品，共 {total} 个")
                
                def download_covers_async():
                    for work in paginated_works:
                        if work.get("cover_url"):
                            try:
                                platform = work.get("platform", "JM")
                                self._download_author_cover(work["id"], work["cover_url"], platform)
                            except Exception as e:
                                error_logger.error(f"异步下载封面失败 {work['id']}: {e}")
                threading.Thread(target=download_covers_async, daemon=True).start()
                
                return ServiceResult.ok({
                    "author": author.to_dict(),
                    "works": paginated_works,
                    "total": total,
                    "offset": offset,
                    "limit": limit,
                    "has_more": has_more,
                    "from_cache": True
                })
            
            # 否则，总是重新搜索，确保获取完整数据
            works = []
            try:
                platforms_to_search = get_supported_platforms()
                platform_albums = {}
                max_result_count = 0
                
                for plat in platforms_to_search:
                    try:
                        adapter_name = 'jmcomic' if plat == 'JM' else 'picacomic'
                        result = external_api.search_albums(author.name, max_pages=3, adapter_name=adapter_name, fast_mode=True)
                        albums = result.get("albums", [])
                        
                        if albums:
                            platform_albums[plat] = albums
                            if len(albums) > max_result_count:
                                max_result_count = len(albums)
                    except Exception as e:
                        error_logger.error(f"搜索作者 {author.name} 在平台 {plat} 的作品失败: {e}")
                        continue
                
                for i in range(max_result_count):
                    for plat in platforms_to_search:
                        if plat in platform_albums and i < len(platform_albums[plat]):
                            album = platform_albums[plat][i]
                            work_id = str(album.get("album_id", ""))
                            cover_url = album.get("cover_url", "")
                            if os.path.exists(f"static/cover/{plat}/author_cache/{work_id}.jpg"):
                                cover_url = f"/static/cover/{plat}/author_cache/{work_id}.jpg"
                            
                            works.append({
                                "id": work_id,
                                "title": album.get("title", ""),
                                "author": author.name,
                                "cover_url": cover_url,
                                "pages": album.get("pages", 0),
                                "has_detail": False,
                                "is_new": True,
                                "platform": plat
                            })
                
            except Exception as e:
                error_logger.error(f"搜索作者 {author.name} 作品失败: {e}")
                return ServiceResult.ok({
                    "author": author.to_dict(),
                    "works": [],
                    "total": 0,
                    "offset": offset,
                    "limit": limit,
                    "has_more": False
                })
            
            # 仅在持久化缓存中保存最近的一批作品（例如前20个），用于进入作者页时的快速展示
            works_for_cache = works[:20]
            self._cache_manager.set_persistent(cache_key, works_for_cache, 'author_works')
            
            existing_ids = self._get_existing_comic_ids()
            filtered_works = [w for w in works if w.get('id') not in existing_ids]
            total = len(filtered_works)
            paginated_works = filtered_works[offset:offset + limit]
            
            has_more = offset + limit < total
            
            result = ServiceResult.ok({
                "author": author.to_dict(),
                "works": paginated_works,
                "total": total,
                "offset": offset,
                "limit": limit,
                "has_more": has_more,
                "from_cache": False
            })
            
            def download_covers_async():
                for work in paginated_works:
                    if work.get("cover_url"):
                        try:
                            platform = work.get("platform", "JM")
                            self._download_author_cover(work["id"], work["cover_url"], platform)
                        except Exception as e:
                            error_logger.error(f"异步下载封面失败 {work['id']}: {e}")
            
            threading.Thread(target=download_covers_async, daemon=True).start()
            
            return result
        except Exception as e:
            error_logger.error(f"获取作者作品失败: {e}")
            return ServiceResult.error("获取作者作品失败")
    
    def search_author_works_by_name(self, author_name: str, offset: int = 0, limit: int = 5) -> ServiceResult:
        """根据作者名搜索作品（不需要订阅）"""
        cache_key = f"author_works_{author_name}"
        
        cached_all_works = self._cache_manager.get_persistent(cache_key, 'author_works')
        if offset == 0 and cached_all_works is not None:
            existing_ids = self._get_existing_comic_ids()
            filtered_works = [w for w in cached_all_works if w.get('id') not in existing_ids]
            total = len(filtered_works)
            paginated_works = filtered_works[offset:offset + limit]
            
            # 设置has_more为true，允许用户点击加载更多
            has_more = True
            
            app_logger.info(f"[Cache] 从持久化缓存读取作者 {author_name} 作品，共 {total} 个")
            
            def download_covers_async():
                for work in paginated_works:
                    if work.get("cover_url"):
                        try:
                            platform = work.get("platform", "JM")
                            self._download_author_cover(work["id"], work["cover_url"], platform)
                        except Exception as e:
                            error_logger.error(f"异步下载封面失败 {work['id']}: {e}")
            threading.Thread(target=download_covers_async, daemon=True).start()
            
            return ServiceResult.ok({
                "author_name": author_name,
                "works": paginated_works,
                "total": total,
                "offset": offset,
                "limit": limit,
                "has_more": has_more,
                "from_cache": True
            })
        
        from core.platform import get_supported_platforms
        
        try:
            works = []
            try:
                platforms_to_search = get_supported_platforms()
                platform_albums = {}
                max_result_count = 0
                
                for plat in platforms_to_search:
                    try:
                        adapter_name = 'jmcomic' if plat == 'JM' else 'picacomic'
                        result = external_api.search_albums(author_name, max_pages=3, adapter_name=adapter_name, fast_mode=True)
                        albums = result.get("albums", [])
                        
                        if albums:
                            platform_albums[plat] = albums
                            if len(albums) > max_result_count:
                                max_result_count = len(albums)
                    except Exception as e:
                        error_logger.error(f"搜索作者 {author_name} 在平台 {plat} 的作品失败: {e}")
                        continue
                
                for i in range(max_result_count):
                    for plat in platforms_to_search:
                        if plat in platform_albums and i < len(platform_albums[plat]):
                            album = platform_albums[plat][i]
                            work_id = str(album.get("album_id", ""))
                            cover_url = album.get("cover_url", "")
                            local_cover = f"/static/cover/{plat}/author_cache/{work_id}.jpg"
                            if os.path.exists(f"static/cover/{plat}/author_cache/{work_id}.jpg"):
                                cover_url = local_cover
                            
                            works.append({
                                "id": work_id,
                                "title": album.get("title", ""),
                                "author": author_name,
                                "cover_url": cover_url,
                                "pages": album.get("pages", 0),
                                "has_detail": False,
                                "is_new": True,
                                "platform": plat
                            })
                
            except Exception as e:
                error_logger.error(f"搜索作者 {author_name} 作品失败: {e}")
                return ServiceResult.ok({
                    "author_name": author_name,
                    "works": [],
                    "total": 0,
                    "offset": offset,
                    "limit": limit,
                    "has_more": False
                })
            
            self._cache_manager.set_persistent(cache_key, works, 'author_works')
            
            existing_ids = self._get_existing_comic_ids()
            filtered_works = [w for w in works if w.get('id') not in existing_ids]
            total = len(filtered_works)
            paginated_works = filtered_works[offset:offset + limit]
            
            has_more = offset + limit < total
            
            result = ServiceResult.ok({
                "author_name": author_name,
                "works": paginated_works,
                "total": total,
                "offset": offset,
                "limit": limit,
                "has_more": has_more,
                "from_cache": False
            })
            
            def download_covers_async():
                for work in paginated_works:
                    if work.get("cover_url"):
                        try:
                            platform = work.get("platform", "JM")
                            self._download_author_cover(work["id"], work["cover_url"], platform)
                        except Exception as e:
                            error_logger.error(f"异步下载封面失败 {work['id']}: {e}")
            
            threading.Thread(target=download_covers_async, daemon=True).start()
            
            return result
        except Exception as e:
            error_logger.error(f"搜索作者作品失败: {e}")
            return ServiceResult.error("搜索作者作品失败")
    
    def clear_author_cover_cache(self) -> ServiceResult:
        """清理作者作品封面缓存
        
        Returns:
            清理结果
        """
        import shutil
        
        cleared_count = 0
        freed_size = 0
        
        try:
            for cache_dir in [JM_AUTHOR_COVER_CACHE_DIR, PK_AUTHOR_COVER_CACHE_DIR]:
                if os.path.exists(cache_dir):
                    for filename in os.listdir(cache_dir):
                        filepath = os.path.join(cache_dir, filename)
                        try:
                            if os.path.isfile(filepath):
                                file_size = os.path.getsize(filepath)
                                os.remove(filepath)
                                cleared_count += 1
                                freed_size += file_size
                        except Exception as e:
                            error_logger.error(f"删除文件失败 {filepath}: {e}")
            
            app_logger.info(f"清理作者封面缓存完成: 清理 {cleared_count} 个文件, 释放 {freed_size} 字节")
            return ServiceResult.ok({
                "cleared_count": cleared_count,
                "freed_size_bytes": freed_size,
                "freed_size_mb": round(freed_size / (1024 * 1024), 2)
            })
        except Exception as e:
            error_logger.error(f"清理作者封面缓存失败: {e}")
            return ServiceResult.error("清理作者封面缓存失败")
    
    def clear_author_works_cache(self, author_name: str = None) -> ServiceResult:
        """清理作者作品缓存
        
        Args:
            author_name: 作者名称，如果为None则清理所有作者作品缓存
            
        Returns:
            清理结果
        """
        try:
            if author_name:
                cache_key = f"author_works_{author_name}"
                deleted = self._cache_manager.delete_persistent(cache_key, 'author_works')
                return ServiceResult.ok({
                    "cleared_count": 1 if deleted else 0,
                    "author_name": author_name
                })
            else:
                count = self._cache_manager.clear_persistent_category('author_works')
                return ServiceResult.ok({
                    "cleared_count": count
                })
        except Exception as e:
            error_logger.error(f"清理作者作品缓存失败: {e}")
            return ServiceResult.error("清理作者作品缓存失败")
    
    def get_works_batch_detail(self, ids: List[str]) -> ServiceResult:
        try:
            works = []
            
            def fetch_single_detail(work_id):
                try:
                    detail = external_api.get_album_by_id(work_id)
                    if detail and detail.get("albums"):
                        album = detail["albums"][0]
                        return {
                            "id": str(album.get("album_id", "")),
                            "title": album.get("title", ""),
                            "author": album.get("author", ""),
                            "cover_url": album.get("cover_url", ""),
                            "pages": album.get("pages", 0),
                            "has_detail": True
                        }
                except Exception as e:
                    error_logger.error(f"获取作品 {work_id} 详情失败: {e}")
                
                return {
                    "id": work_id,
                    "title": "获取失败",
                    "author": "",
                    "cover_url": "",
                    "pages": 0,
                    "has_detail": False
                }
            
            with ThreadPoolExecutor(max_workers=5) as executor:
                future_to_id = {executor.submit(fetch_single_detail, work_id): work_id for work_id in ids}
                results = {}
                for future in as_completed(future_to_id):
                    work_id = future_to_id[future]
                    try:
                        results[work_id] = future.result()
                    except Exception as e:
                        error_logger.error(f"获取作品 {work_id} 详情失败: {e}")
                        results[work_id] = {
                            "id": work_id,
                            "title": "获取失败",
                            "author": "",
                            "cover_url": "",
                            "pages": 0,
                            "has_detail": False
                        }
                
                for work_id in ids:
                    works.append(results.get(work_id, {
                        "id": work_id,
                        "title": "获取失败",
                        "author": "",
                        "cover_url": "",
                        "pages": 0,
                        "has_detail": False
                    }))
            
            return ServiceResult.ok({"works": works})
        except Exception as e:
            error_logger.error(f"批量获取作品详情失败: {e}")
            return ServiceResult.error("批量获取作品详情失败")
