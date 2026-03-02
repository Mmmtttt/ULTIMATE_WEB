from typing import List, Dict
from concurrent.futures import ThreadPoolExecutor, as_completed
from domain.author import AuthorSubscription, AuthorRepository
from infrastructure.persistence.repositories import AuthorJsonRepository
from infrastructure.common.result import ServiceResult
from infrastructure.logger import app_logger, error_logger
from core.utils import get_current_time, generate_id
from third_party import external_api


class AuthorAppService:
    def __init__(self, author_repo: AuthorRepository = None):
        self._author_repo = author_repo or AuthorJsonRepository()
    
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
                create_time=get_current_time()
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
        works = []
        try:
            result = external_api.search_albums(author_name, max_pages=1, fast_mode=True)
            albums = result.get("albums", [])
            
            for album in albums:
                works.append({
                    "id": str(album.get("album_id", "")),
                    "title": album.get("title", ""),
                    "author": author_name,
                    "cover_url": "",
                    "pages": 0
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
                    works = self._search_author_works(author.name)
                    
                    if not works:
                        continue
                    
                    latest_work = works[0]
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
                        author.update_check_info(
                            latest_work.get("id", ""),
                            latest_work.get("title", ""),
                            len(new_works)
                        )
                        self._author_repo.save(author)
                        
                        updated_authors.append({
                            "author": author.to_dict(),
                            "new_works": new_works
                        })
                        total_new_works += len(new_works)
                    else:
                        author.update_check_info(
                            latest_work.get("id", ""),
                            latest_work.get("title", ""),
                            0
                        )
                        self._author_repo.save(author)
                        
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
        try:
            author = self._author_repo.get_by_id(author_id)
            if not author:
                return ServiceResult.error("订阅不存在")
            
            works = []
            try:
                result = external_api.search_albums(author.name, max_pages=1, fast_mode=True)
                albums = result.get("albums", [])
                
                for album in albums:
                    works.append({
                        "id": str(album.get("album_id", "")),
                        "title": album.get("title", ""),
                        "author": author.name,
                        "cover_url": "",
                        "pages": 0
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
        try:
            author = self._author_repo.get_by_id(author_id)
            if not author:
                return ServiceResult.error("订阅不存在")
            
            works = []
            try:
                result = external_api.search_albums(author.name, max_pages=1, fast_mode=True)
                albums = result.get("albums", [])
                
                for album in albums:
                    works.append({
                        "id": str(album.get("album_id", "")),
                        "title": album.get("title", ""),
                        "author": author.name,
                        "cover_url": "",
                        "pages": 0,
                        "has_detail": False
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
            
            total = len(works)
            paginated_works = works[offset:offset + limit]
            has_more = offset + limit < total
            
            return ServiceResult.ok({
                "author": author.to_dict(),
                "works": paginated_works,
                "total": total,
                "offset": offset,
                "limit": limit,
                "has_more": has_more
            })
        except Exception as e:
            error_logger.error(f"获取作者作品失败: {e}")
            return ServiceResult.error("获取作者作品失败")
    
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
