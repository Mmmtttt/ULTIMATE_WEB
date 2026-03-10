from typing import List, Dict, Set
from concurrent.futures import ThreadPoolExecutor, as_completed
import os
import requests
from PIL import Image
from io import BytesIO
from domain.author import AuthorSubscription, AuthorRepository
from infrastructure.persistence.repositories import AuthorJsonRepository
from infrastructure.persistence.repositories.comic_repository_impl import ComicJsonRepository
from infrastructure.persistence.repositories.recommendation_repository_impl import RecommendationJsonRepository
from infrastructure.common.result import ServiceResult
from infrastructure.logger import app_logger, error_logger
from infrastructure.persistence.json_storage import JsonStorage
from core.utils import get_current_time, generate_id
from core.constants import JM_AUTHOR_COVER_CACHE_DIR, PK_AUTHOR_COVER_CACHE_DIR, JSON_FILE, RECOMMENDATION_JSON_FILE
from third_party import external_api
from application.base.content_app_service import BaseCreatorAppService
from core.enums import ContentType


class AuthorAppService(BaseCreatorAppService):
    _entity_name: str = "作者"
    _content_type: ContentType = ContentType.COMIC
    
    def __init__(self, author_repo: AuthorRepository = None):
        self._author_repo = author_repo or AuthorJsonRepository()
        self._comic_repo = ComicJsonRepository()
        self._recommendation_repo = RecommendationJsonRepository()
    
    def _search_works(self, creator_name: str) -> List[Dict]:
        """搜索作者作品"""
        from core.platform import get_supported_platforms
        
        works = []
        try:
            platforms_to_search = get_supported_platforms()
            platform_albums = {}
            max_result_count = 0
            
            for plat in platforms_to_search:
                try:
                    adapter_name = 'jmcomic' if plat == 'JM' else 'picacomic'
                    result = external_api.search_albums(creator_name, max_pages=3, adapter_name=adapter_name, fast_mode=True)
                    albums = result.get("albums", [])
                    
                    if albums:
                        platform_albums[plat] = albums
                        if len(albums) > max_result_count:
                            max_result_count = len(albums)
                except Exception as e:
                    error_logger.error(f"搜索作者 {creator_name} 在平台 {plat} 的作品失败: {e}")
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
                            "author": creator_name,
                            "cover_url": cover_url,
                            "pages": album.get("pages", 0),
                            "has_detail": False,
                            "is_new": True,
                            "platform": plat
                        })
                
        except Exception as e:
            error_logger.error(f"搜索作者 {creator_name} 作品失败: {e}")
        
        return works
    
    def _get_existing_content_ids(self) -> Set[str]:
        """获取已存在的漫画ID集合"""
        existing_ids = set()
        
        try:
            home_storage = JsonStorage(JSON_FILE)
            home_data = home_storage.read()
            for comic in home_data.get('comics', []):
                raw_id = comic.get('id', '')
                if raw_id.startswith('JM_'):
                    raw_id = raw_id[3:]
                existing_ids.add(raw_id)
        except Exception as e:
            error_logger.error(f"获取主页漫画ID失败: {e}")
        
        try:
            rec_storage = JsonStorage(RECOMMENDATION_JSON_FILE)
            rec_data = rec_storage.read()
            for comic in rec_data.get('recommendations', []):
                raw_id = comic.get('id', '')
                if raw_id.startswith('JM_'):
                    raw_id = raw_id[3:]
                existing_ids.add(raw_id)
        except Exception as e:
            error_logger.error(f"获取推荐页漫画ID失败: {e}")
        
        return existing_ids
    
    def _download_cover(self, content_id: str, cover_url: str, platform: str) -> str:
        """下载作者作品封面"""
        if not cover_url:
            return ""
        
        cache_dir = JM_AUTHOR_COVER_CACHE_DIR if platform == 'JM' else PK_AUTHOR_COVER_CACHE_DIR
        local_path = os.path.join(cache_dir, f"{content_id}.jpg")
        
        if os.path.exists(local_path):
            return f"/static/cover/{platform}/author_cache/{content_id}.jpg"
        
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
            
            return f"/static/cover/{platform}/author_cache/{content_id}.jpg"
        except Exception as e:
            error_logger.error(f"下载作者作品封面失败 {content_id}: {e}")
            return cover_url
    
    def _get_cache_key_prefix(self) -> str:
        """获取缓存键前缀"""
        return "author_works"
    
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
                    cache_key = f"{self._get_cache_key_prefix()}_{author.name}"
                    cached_works = self._cache_manager.get_persistent(cache_key, self._get_cache_key_prefix())
                    
                    works = self._search_works(author.name)
                    
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
                        works_for_cache = works[:20]
                        self._cache_manager.set_persistent(cache_key, works_for_cache, self._get_cache_key_prefix())
                    
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
    
    def get_author_works_paginated(self, author_id: str, offset: int = 0, limit: int = 5) -> ServiceResult:
        """分页获取作者作品"""
        try:
            author = self._author_repo.get_by_id(author_id)
            if not author:
                return ServiceResult.error("订阅不存在")
            
            result = self.get_works_paginated_impl(author, offset, limit)
            
            if result.success:
                data = result.data
                data["author"] = data.pop("creator")
            
            return result
        except Exception as e:
            error_logger.error(f"获取作者作品失败: {e}")
            return ServiceResult.error("获取作者作品失败")
    
    def search_author_works_by_name(self, author_name: str, offset: int = 0, limit: int = 5) -> ServiceResult:
        """根据作者名搜索作品（不需要订阅）"""
        return self.search_works_by_name_impl(author_name, offset, limit)
    
    def clear_author_cover_cache(self) -> ServiceResult:
        """清理作者作品封面缓存"""
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
        """清理作者作品缓存"""
        return self.clear_works_cache_impl(author_name)
    
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
